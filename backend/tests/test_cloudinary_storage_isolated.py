"""Cloudinary tests are mocked and never upload candidate media."""

import datetime
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from starlette.requests import Request

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import BadRequestException, SkillSphereException
from app.database.base import Base
from app.models.proctoring import ProctoringSession
from app.routers.proctoring import (
    ensure_recording_upload_allowed,
    persist_recording_storage_metadata,
    recruiter_view_recording,
    admin_view_recording,
    recruiter_recording_playback_url,
    admin_recording_playback_url,
    get_assignment_for_recruiter,
    recruiter_router,
    admin_router,
    create_recording_playback_link,
    recording_metadata_matches,
)
from app.core.dependencies import get_current_admin, get_current_recruiter
from app.services.storage_service import StorageService


@pytest.fixture
def fake_cloudinary(monkeypatch):
    calls = {"config": [], "upload": [], "delete": [], "signed": [], "resource": [], "assets": {}}
    package = types.ModuleType("cloudinary")
    package.__path__ = []
    package.config = lambda **kwargs: calls["config"].append(kwargs) or SimpleNamespace(**kwargs)
    uploader = types.ModuleType("cloudinary.uploader")
    def upload_large(file, **kwargs):
        calls["upload"].append((file, kwargs))
        result = {
            "asset_id": "asset-id-test",
            "public_id": kwargs["public_id"],
            "version": 123,
            "format": "webm",
            "resource_type": "video",
            "bytes": Path(file).stat().st_size,
            "type": "authenticated",
            "context": {"custom": kwargs["context"]},
            "secure_url": "https://public-url-must-not-be-persisted.invalid/video",
        }
        calls["assets"][kwargs["public_id"]] = result
        return result
    uploader.upload_large = upload_large
    uploader.destroy = lambda public_id, **kwargs: calls["delete"].append((public_id, kwargs)) or {"result": "ok"}
    utils = types.ModuleType("cloudinary.utils")
    utils.private_download_url = lambda public_id, file_format, **kwargs: calls["signed"].append((public_id, file_format, kwargs)) or "https://api.cloudinary.test/signed-expiring"
    api = types.ModuleType("cloudinary.api")
    exceptions = types.ModuleType("cloudinary.exceptions")
    class NotFound(Exception):
        pass
    def resource(public_id, **kwargs):
        calls["resource"].append((public_id, kwargs))
        if public_id not in calls["assets"]:
            raise NotFound("not found")
        return calls["assets"][public_id]
    api.resource = resource
    api.ping = lambda: {"status": "ok"}
    exceptions.NotFound = NotFound
    package.uploader = uploader
    package.utils = utils
    package.api = api
    monkeypatch.setitem(sys.modules, "cloudinary", package)
    monkeypatch.setitem(sys.modules, "cloudinary.uploader", uploader)
    monkeypatch.setitem(sys.modules, "cloudinary.utils", utils)
    monkeypatch.setitem(sys.modules, "cloudinary.api", api)
    monkeypatch.setitem(sys.modules, "cloudinary.exceptions", exceptions)
    return calls


@pytest.fixture
def cloudinary_settings(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_BACKEND", "cloudinary")
    monkeypatch.setattr(settings, "CLOUDINARY_CLOUD_NAME", "test-cloud")
    monkeypatch.setattr(settings, "CLOUDINARY_API_KEY", "test-key")
    monkeypatch.setattr(settings, "CLOUDINARY_API_SECRET", "test-secret")
    return settings


def test_cloudinary_configuration_and_chunked_authenticated_upload(tmp_path, fake_cloudinary, cloudinary_settings):
    source = tmp_path / "recording.webm"
    source.write_bytes(bytes.fromhex("1A45DFA30102030405060708"))

    stored = StorageService.save_recording_with_metadata(source, "unique-upload.webm", "video/webm")

    assert stored["provider"] == "cloudinary"
    assert stored["asset_id"] == "asset-id-test"
    assert stored["public_id"] == "skillsphere/proctoring/unique-upload"
    assert "secure_url" not in stored
    upload_options = fake_cloudinary["upload"][0][1]
    assert upload_options["type"] == "authenticated"
    assert upload_options["resource_type"] == "video"
    assert upload_options["chunk_size"] == 6 * 1024 * 1024
    assert upload_options["overwrite"] is False


def test_official_cloudinary_not_found_without_status_attributes_allows_first_upload(tmp_path, fake_cloudinary, cloudinary_settings):
    source = tmp_path / "first-upload.webm"
    source.write_bytes(bytes.fromhex("1A45DFA30102030405060708"))

    stored = StorageService.save_recording_with_metadata(source, "first-upload.webm", "video/webm")

    assert stored["provider"] == "cloudinary"
    assert stored["asset_id"] == "asset-id-test"
    assert len(fake_cloudinary["upload"]) == 1


def test_cloudinary_upload_failure_is_not_reported_as_success(tmp_path, fake_cloudinary, cloudinary_settings, monkeypatch):
    source = tmp_path / "recording.webm"
    source.write_bytes(bytes.fromhex("1A45DFA30102030405060708"))
    monkeypatch.setattr(sys.modules["cloudinary.uploader"], "upload_large", Mock(side_effect=RuntimeError("permission denied")))

    with pytest.raises(SkillSphereException) as error:
        StorageService.save_recording_with_metadata(source, "failed.webm", "video/webm")
    assert error.value.status_code == 502
    assert "upload failed" in str(error.value).lower()


def test_cloudinary_reconciliation_authentication_failure_does_not_upload(tmp_path, fake_cloudinary, cloudinary_settings, monkeypatch):
    source = tmp_path / "recording.webm"
    source.write_bytes(bytes.fromhex("1A45DFA30102030405060708"))
    monkeypatch.setattr(sys.modules["cloudinary.api"], "resource", Mock(side_effect=RuntimeError("401 unauthorized")))

    with pytest.raises(SkillSphereException) as error:
        StorageService.save_recording_with_metadata(source, "auth-failed.webm", "video/webm")

    assert error.value.status_code == 502
    assert fake_cloudinary["upload"] == []


def test_ambiguous_upload_timeout_recovers_matching_authenticated_asset(tmp_path, fake_cloudinary, cloudinary_settings, monkeypatch):
    import hashlib
    source = tmp_path / "recording.webm"
    payload = bytes.fromhex("1A45DFA30102030405060708")
    source.write_bytes(payload)
    public_id = "skillsphere/proctoring/assessment-73"
    fake_cloudinary["assets"][public_id] = {
        "asset_id": "asset-recovered",
        "public_id": public_id,
        "version": 123,
        "format": "webm",
        "resource_type": "video",
        "bytes": len(payload),
        "type": "authenticated",
        "context": {"custom": {"session_id": "assessment-73", "sha256": hashlib.sha256(payload).hexdigest()}},
    }
    monkeypatch.setattr(sys.modules["cloudinary.uploader"], "upload_large", Mock(side_effect=TimeoutError("response lost")))

    recovered = StorageService.save_recording_with_metadata(
        source, "random-stage-name.webm", "video/webm", "assessment-73", hashlib.sha256(payload).hexdigest()
    )

    assert recovered["asset_id"] == "asset-recovered"
    assert recovered["storage_reference"] == f"cloudinary://{public_id}"
    assert len(fake_cloudinary["upload"]) == 0
    assert all(call[1]["context"] is True for call in fake_cloudinary["resource"])


def test_retry_reconciles_same_asset_without_duplicate_upload(tmp_path, fake_cloudinary, cloudinary_settings):
    import hashlib
    source = tmp_path / "recording.webm"
    payload = bytes.fromhex("1A45DFA30102030405060708")
    source.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()

    first = StorageService.save_recording_with_metadata(source, "stage-one.webm", "video/webm", "assessment-74", digest)
    second = StorageService.save_recording_with_metadata(source, "stage-two.webm", "video/webm", "assessment-74", digest)

    assert first["asset_id"] == second["asset_id"]
    assert len(fake_cloudinary["upload"]) == 1


def test_database_commit_failure_leaves_asset_for_safe_retry_without_duplicate(tmp_path, fake_cloudinary, cloudinary_settings):
    import hashlib
    source = tmp_path / "recording.webm"
    payload = bytes.fromhex("1A45DFA30102030405060708")
    source.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    key = "assessment-commit-failure"
    metadata = StorageService.save_recording_with_metadata(source, "stage.webm", "video/webm", key, digest)

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    row = ProctoringSession(
        assignment_id=1, candidate_id=1, recording_started_at=datetime.datetime.utcnow(),
        session_status="RECORDING",
    )
    persist_recording_storage_metadata(row, metadata)
    db.add(row)

    def fail_commit(session):
        event.remove(session, "before_commit", fail_commit)
        raise RuntimeError("synthetic commit failure")

    event.listen(db, "before_commit", fail_commit)
    with pytest.raises(RuntimeError, match="synthetic commit failure"):
        db.commit()
    db.rollback()
    assert db.query(ProctoringSession).count() == 0

    recovered = StorageService.save_recording_with_metadata(source, "retry-stage.webm", "video/webm", key, digest)
    assert recovered["asset_id"] == metadata["asset_id"]
    assert len(fake_cloudinary["upload"]) == 1
    db.close()
    engine.dispose()


def test_reconciliation_rejects_mismatched_asset_without_overwrite(tmp_path, fake_cloudinary, cloudinary_settings):
    import hashlib
    source = tmp_path / "recording.webm"
    payload = bytes.fromhex("1A45DFA30102030405060708")
    source.write_bytes(payload)
    public_id = "skillsphere/proctoring/assessment-75"
    fake_cloudinary["assets"][public_id] = {
        "asset_id": "other-asset", "public_id": public_id, "type": "authenticated",
        "context": {"custom": {"session_id": "assessment-75", "sha256": "different"}},
    }

    with pytest.raises(SkillSphereException) as error:
        StorageService.save_recording_with_metadata(source, "stage.webm", "video/webm", "assessment-75", hashlib.sha256(payload).hexdigest())
    assert error.value.status_code == 409
    assert fake_cloudinary["upload"] == []


def test_cloudinary_playback_url_is_signed_and_capped_at_ten_minutes(fake_cloudinary, cloudinary_settings):
    url = StorageService.get_access_url("cloudinary://skillsphere/proctoring/example", 3600, "webm")
    assert url == "https://api.cloudinary.test/signed-expiring"
    _, _, options = fake_cloudinary["signed"][0]
    assert options["type"] == "authenticated"
    assert options["resource_type"] == "video"
    assert options["attachment"] is False
    assert options["expires_at"] <= int(datetime.datetime.now(datetime.timezone.utc).timestamp()) + 601


def test_metadata_persists_asset_identifiers_and_duplicate_upload_is_rejected():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    session = ProctoringSession(
        assignment_id=1,
        candidate_id=1,
        session_status="RECORDING",
        recording_started_at=datetime.datetime.utcnow(),
    )
    db.add(session)
    db.commit()

    metadata = {
        "storage_reference": "cloudinary://skillsphere/proctoring/example",
        "provider": "cloudinary",
        "asset_id": "asset-id-test",
        "public_id": "skillsphere/proctoring/example",
        "version": "123",
        "format": "webm",
        "resource_type": "video",
        "delivery_type": "authenticated",
    }
    persist_recording_storage_metadata(session, metadata)
    db.commit()
    db.refresh(session)

    assert session.recording_path == metadata["storage_reference"]
    assert session.recording_provider == "cloudinary"
    assert session.cloudinary_asset_id == "asset-id-test"
    assert session.cloudinary_public_id == "skillsphere/proctoring/example"
    assert session.cloudinary_version == "123"
    assert session.cloudinary_format == "webm"
    assert session.cloudinary_resource_type == "video"
    assert session.cloudinary_delivery_type == "authenticated"
    assert session.recording_path != "https://public-url-must-not-be-persisted.invalid/video"

    with pytest.raises(BadRequestException, match="already been uploaded"):
        ensure_recording_upload_allowed(session)
    db.close()
    engine.dispose()


def test_ambiguous_database_commit_requires_complete_persisted_metadata():
    metadata = {
        "storage_reference": "cloudinary://skillsphere/proctoring/assessment-1",
        "provider": "cloudinary", "asset_id": "asset-1", "public_id": "skillsphere/proctoring/assessment-1",
        "version": "123", "format": "webm", "resource_type": "video", "delivery_type": "authenticated",
    }
    persisted = SimpleNamespace(
        session_status="COMPLETED", recording_completed_at=datetime.datetime.utcnow(),
        recording_path=metadata["storage_reference"], recording_provider="cloudinary",
        cloudinary_asset_id="asset-1", cloudinary_public_id=metadata["public_id"],
        cloudinary_version="123", cloudinary_format="webm", cloudinary_resource_type="video",
        cloudinary_delivery_type="authenticated", recording_mime_type="video/webm",
        recording_size_bytes=100, delete_after=None,
        recording_deleted_at=None,
    )

    assert recording_metadata_matches(persisted, metadata, "video/webm", 100)
    submitted_at = datetime.datetime.utcnow()
    persisted.delete_after = submitted_at + datetime.timedelta(days=15)
    assert recording_metadata_matches(
        persisted,
        metadata,
        "video/webm",
        100,
        assessment_submitted_at=submitted_at,
    )
    persisted.cloudinary_asset_id = None
    assert not recording_metadata_matches(
        persisted,
        metadata,
        "video/webm",
        100,
        assessment_submitted_at=submitted_at,
    )


def test_cloudinary_destroy_reports_provider_failure_without_claiming_success(fake_cloudinary, cloudinary_settings, monkeypatch):
    monkeypatch.setattr(sys.modules["cloudinary.uploader"], "destroy", Mock(side_effect=RuntimeError("provider unavailable")))
    assert StorageService.delete_recording("cloudinary://skillsphere/proctoring/example") is False


def test_local_storage_remains_available_without_cloudinary(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr("app.services.storage_service.PRIVATE_RECORDING_DIR", tmp_path / "private")
    source = tmp_path / "local-test.webm"
    source.write_bytes(bytes.fromhex("1A45DFA30102030405060708"))

    reference = StorageService.save_recording_file(source, "local-test.webm", "video/webm")
    assert Path(reference).read_bytes() == source.read_bytes()
    assert StorageService.delete_recording(reference) is True


def test_recruiter_cannot_access_recording_for_another_recruiters_job():
    recruiter = SimpleNamespace(id=17)
    assignment = SimpleNamespace(job=SimpleNamespace(recruiter_id=18))

    class Query:
        def filter(self, *_args):
            return self

        def first(self):
            return assignment

    db = SimpleNamespace(query=lambda *_args: Query())
    with pytest.raises(Exception) as error:
        get_assignment_for_recruiter(42, recruiter, db)
    assert getattr(error.value, "status_code", None) == 403


def test_playback_url_routes_require_recruiter_or_admin_dependencies():
    recruiter_route = next(route for route in recruiter_router.routes if route.path.endswith("/recording-url"))
    admin_route = next(route for route in admin_router.routes if route.path.endswith("/recording-url"))
    recruiter_dependencies = {dependency.call for dependency in recruiter_route.dependant.dependencies}
    admin_dependencies = {dependency.call for dependency in admin_route.dependant.dependencies}
    from app.routers.proctoring import get_recording_recruiter, get_recording_admin
    assert get_recording_recruiter in recruiter_dependencies
    assert get_recording_admin in admin_dependencies


@pytest.mark.parametrize("view_function,actor", [
    (recruiter_view_recording, SimpleNamespace(id=9, user_id=91)),
    (admin_view_recording, SimpleNamespace(id=92)),
])
def test_authorized_recruiter_and_admin_playback_are_signed_and_audited(monkeypatch, view_function, actor):
    audit_rows = []
    db = SimpleNamespace(add=audit_rows.append, commit=lambda: None)
    session = SimpleNamespace(
        id=18,
        recording_path="cloudinary://skillsphere/proctoring/authorized",
        recording_completed_at=datetime.datetime.utcnow(),
        recording_deleted_at=None,
        recording_provider="cloudinary",
        cloudinary_format="webm",
        recording_mime_type="video/webm",
        recording_filename="recording.webm",
    )
    monkeypatch.setattr("app.routers.proctoring.get_authorized_recording", lambda *_args: (session, session.recording_path))
    monkeypatch.setattr("app.routers.proctoring.is_recording_expired", lambda *_args: False)
    monkeypatch.setattr("app.routers.proctoring.get_assignment_for_recruiter", lambda *_args: None)
    signed = Mock(return_value="https://api.cloudinary.test/signed-expiring")
    monkeypatch.setattr(StorageService, "get_access_url", signed)
    request = Request({"type": "http", "method": "GET", "path": "/recording", "headers": [], "client": ("127.0.0.1", 1234)})

    response = view_function(assignment_id=42, request=request, **({"recruiter": actor} if view_function is recruiter_view_recording else {"admin": actor}), db=db)

    assert response.status_code == 307
    assert response.headers["location"] == "https://api.cloudinary.test/signed-expiring"
    signed.assert_called_once_with(session.recording_path, expires_in_seconds=600, asset_format="webm")
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "PROCTORING_RECORDING_ACCESSED"
    assert audit_rows[0].details["outcome"] == "success"
    assert audit_rows[0].details["recording_session_id"] is None or audit_rows[0].details["recording_session_id"] == getattr(session, "id", None)


@pytest.mark.parametrize("view_function,actor,role_kw", [
    (recruiter_recording_playback_url, SimpleNamespace(id=9, user_id=91), "recruiter"),
    (admin_recording_playback_url, SimpleNamespace(id=92), "admin"),
])
def test_playback_url_endpoint_is_authorized_audited_and_short_lived(monkeypatch, view_function, actor, role_kw):
    audit_rows = []
    db = SimpleNamespace(add=audit_rows.append, commit=lambda: None)
    session = SimpleNamespace(
        id=19,
        recording_path="cloudinary://skillsphere/proctoring/authorized",
        recording_completed_at=datetime.datetime.utcnow(),
        recording_deleted_at=None,
        recording_provider="cloudinary",
        cloudinary_format="webm",
        recording_mime_type="video/webm",
    )
    monkeypatch.setattr("app.routers.proctoring.get_authorized_recording", lambda *_args: (session, session.recording_path))
    monkeypatch.setattr("app.routers.proctoring.is_recording_expired", lambda *_args: False)
    monkeypatch.setattr("app.routers.proctoring.get_assignment_for_recruiter", lambda *_args: None)
    signed = Mock(return_value="https://api.cloudinary.test/signed-expiring")
    monkeypatch.setattr(StorageService, "get_access_url", signed)
    request = Request({"type": "http", "method": "GET", "path": "/recording-url", "headers": [], "client": ("127.0.0.1", 1234)})

    response = view_function(assignment_id=42, request=request, **{role_kw: actor}, db=db)

    assert response["url"] == "https://api.cloudinary.test/signed-expiring"
    assert response["expires_in_seconds"] == 600
    signed.assert_called_once_with(session.recording_path, expires_in_seconds=600, asset_format="webm", attachment=False)
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "PROCTORING_RECORDING_SIGNED_URL_GENERATED"
    assert audit_rows[0].details["outcome"] == "success"


def test_invalid_or_expired_playback_request_is_audited(monkeypatch):
    from fastapi import HTTPException
    audit_rows = []
    class Query:
        def filter(self, *_args): return self
        def scalar(self): return 404
    db = SimpleNamespace(add=audit_rows.append, commit=lambda: None, rollback=lambda: None, query=lambda *_args: Query())
    monkeypatch.setattr("app.routers.proctoring.get_authorized_recording", Mock(side_effect=HTTPException(404, "not found")))
    request = Request({"type": "http", "method": "GET", "path": "/recording-url", "headers": [], "client": ("127.0.0.1", 1234)})

    with pytest.raises(HTTPException):
        create_recording_playback_link(404, request, 91, "ADMIN", db)

    assert audit_rows[0].action == "PROCTORING_RECORDING_ACCESS_FAILED"
    assert audit_rows[0].details == {
        "role": "ADMIN", "outcome": "failed", "recording_session_id": 404,
        "timestamp": audit_rows[0].details["timestamp"], "status_code": 404,
    }


def test_failed_signed_link_generation_is_audited_without_url_or_secret(monkeypatch):
    from app.core.exceptions import SkillSphereException
    audit_rows = []
    db = SimpleNamespace(add=audit_rows.append, commit=lambda: None)
    session = SimpleNamespace(
        id=19, recording_path="cloudinary://skillsphere/proctoring/private",
        recording_provider="cloudinary", cloudinary_format="webm", recording_mime_type="video/webm",
    )
    monkeypatch.setattr("app.routers.proctoring.get_authorized_recording", lambda *_args: (session, session.recording_path))
    monkeypatch.setattr(StorageService, "get_access_url", Mock(side_effect=SkillSphereException(500, "signing failed")))
    request = Request({"type": "http", "method": "GET", "path": "/recording-url", "headers": [], "client": ("127.0.0.1", 1234)})

    with pytest.raises(SkillSphereException):
        create_recording_playback_link(42, request, 91, "RECRUITER", db)

    assert audit_rows[0].action == "PROCTORING_RECORDING_SIGNED_URL_GENERATION_FAILED"
    assert audit_rows[0].details["recording_session_id"] == 19
    assert audit_rows[0].details["outcome"] == "failed"
    assert "url" not in str(audit_rows[0].details).lower()
    assert "secret" not in str(audit_rows[0].details).lower()


def test_recruiter_job_ownership_denial_is_audited(monkeypatch):
    from fastapi import HTTPException
    audit_rows = []
    class Query:
        def filter(self, *_args): return self
        def scalar(self): return 55
    db = SimpleNamespace(add=audit_rows.append, commit=lambda: None, rollback=lambda: None, query=lambda *_args: Query())
    actor = SimpleNamespace(id=9, user_id=91)
    monkeypatch.setattr("app.routers.proctoring.get_assignment_for_recruiter", Mock(side_effect=HTTPException(403, "foreign job")))
    request = Request({"type": "http", "method": "GET", "path": "/recording-url", "headers": [], "client": ("127.0.0.1", 1234)})

    with pytest.raises(HTTPException):
        recruiter_recording_playback_url(42, request, False, actor, db)

    assert audit_rows[0].action == "PROCTORING_RECORDING_ACCESS_DENIED"
    assert audit_rows[0].user_id == actor.user_id
    assert audit_rows[0].details["role"] == "RECRUITER"
    assert audit_rows[0].details["outcome"] == "denied"


def test_authentication_role_denial_is_audited(monkeypatch):
    from fastapi import HTTPException
    audit_rows = []
    class Query:
        def filter(self, *_args): return self
        def scalar(self): return None
    db = SimpleNamespace(add=audit_rows.append, commit=lambda: None, rollback=lambda: None, query=lambda *_args: Query())
    monkeypatch.setattr("app.routers.proctoring.get_current_user", Mock(side_effect=HTTPException(401, "bad token")))
    request = Request({"type": "http", "method": "GET", "path": "/admin/proctoring/assignments/42/recording-url", "path_params": {"assignment_id": "42"}, "headers": [], "client": ("127.0.0.1", 1234)})

    from app.routers.proctoring import get_recording_actor
    with pytest.raises(HTTPException):
        get_recording_actor(request, db, "opaque-token-never-logged", "ADMIN")

    assert audit_rows[0].action == "PROCTORING_RECORDING_ACCESS_FAILED"
    assert audit_rows[0].user_id is None
    assert audit_rows[0].entity_id == 42
    assert "opaque-token" not in str(audit_rows[0].details)


def test_authenticated_wrong_role_is_audited(monkeypatch):
    from fastapi import HTTPException
    audit_rows = []
    class Query:
        def filter(self, *_args): return self
        def scalar(self): return 88
    db = SimpleNamespace(add=audit_rows.append, commit=lambda: None, rollback=lambda: None, query=lambda *_args: Query())
    monkeypatch.setattr(
        "app.routers.proctoring.get_current_user",
        Mock(return_value=SimpleNamespace(id=72, role=SimpleNamespace(value="CANDIDATE"))),
    )
    request = Request({"type": "http", "method": "GET", "path": "/admin/proctoring/assignments/88/recording-url", "path_params": {"assignment_id": "88"}, "headers": [], "client": ("127.0.0.1", 1234)})

    from app.routers.proctoring import get_recording_actor
    with pytest.raises(HTTPException) as error:
        get_recording_actor(request, db, "test-token", "ADMIN")

    assert error.value.status_code == 403
    assert audit_rows[0].action == "PROCTORING_RECORDING_ACCESS_DENIED"
    assert audit_rows[0].user_id == 72
    assert audit_rows[0].details["role"] == "CANDIDATE"
