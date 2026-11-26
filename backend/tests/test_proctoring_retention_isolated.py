"""Assessment-submission-anchored recording retention tests (SQLite only)."""

import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.database.base import Base
from app.models.proctoring import ProctoringSession
from app.models.recruiter_assessment import (
    AssessmentAssignment,
    CandidateAssessmentAttempt,
)
from app.routers.proctoring import is_recording_expired
from app.services.proctoring_cleanup import cleanup_expired_recordings
from app.services.recording_retention import (
    sync_recording_expiry,
)


@pytest.fixture
def retention_db(monkeypatch):
    monkeypatch.setattr(settings, "RECORDING_RETENTION_DAYS", 15)
    engine = create_engine("sqlite:///:memory:")
    assert engine.dialect.name == "sqlite"
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def add_recording(db, assignment_id, *, submitted_at, uploaded_at, path, status="COMPLETED"):
    assignment = AssessmentAssignment(
        id=assignment_id,
        application_id=assignment_id,
        job_id=assignment_id,
        candidate_id=assignment_id,
        job_assessment_id=assignment_id,
        status="SUBMITTED" if submitted_at else "IN_PROGRESS",
        config_snapshot={},
        assigned_questions=[],
        private_answer_key={},
    )
    attempt = CandidateAssessmentAttempt(
        assignment_id=assignment_id,
        candidate_id=assignment_id,
        started_at=uploaded_at - datetime.timedelta(minutes=20),
        expires_at=uploaded_at + datetime.timedelta(hours=1),
        submitted_at=submitted_at,
        is_submitted=submitted_at is not None,
        saved_answers={},
        marked_for_review=[],
    )
    recording = ProctoringSession(
        assignment_id=assignment_id,
        candidate_id=assignment_id,
        session_status=status,
        recording_path=path,
        recording_completed_at=uploaded_at,
        delete_after=None,
    )
    db.add_all([assignment, attempt, recording])
    db.flush()
    return assignment, attempt, recording


def test_upload_before_submission_uses_submission_time_and_sets_deadline_later(retention_db):
    now = datetime.datetime.utcnow()
    upload_at = now - datetime.timedelta(days=10)
    _, attempt, recording = add_recording(
        retention_db,
        1,
        submitted_at=None,
        uploaded_at=upload_at,
        path="recording-before-submit",
    )

    # Until submission is authoritative, there is no expiry timestamp.
    sync_recording_expiry(recording, attempt)
    assert recording.delete_after is None
    assert is_recording_expired(recording, now) is True

    attempt.is_submitted = True
    attempt.submitted_at = now
    deadline = sync_recording_expiry(recording, attempt)
    assert deadline == now + datetime.timedelta(days=15)
    assert recording.delete_after == deadline
    assert is_recording_expired(recording, now + datetime.timedelta(days=14)) is False
    assert is_recording_expired(recording, deadline) is True
    assert deadline != upload_at + datetime.timedelta(days=15)


def test_upload_after_submission_uses_original_submission_timestamp(retention_db):
    submitted_at = datetime.datetime.utcnow() - datetime.timedelta(days=4)
    upload_at = submitted_at + datetime.timedelta(hours=1)
    _, attempt, recording = add_recording(
        retention_db,
        2,
        submitted_at=submitted_at,
        uploaded_at=upload_at,
        path="recording-after-submit",
    )

    deadline = sync_recording_expiry(recording, attempt)
    assert deadline == submitted_at + datetime.timedelta(days=15)
    assert deadline < upload_at + datetime.timedelta(days=15)
    assert is_recording_expired(recording, deadline) is True


def test_missing_submission_timestamp_fails_closed_without_upload_time_fallback(retention_db):
    upload_at = datetime.datetime.utcnow() - datetime.timedelta(days=60)
    _, attempt, recording = add_recording(
        retention_db,
        3,
        submitted_at=None,
        uploaded_at=upload_at,
        path="missing-submission",
    )
    # Simulate stale legacy metadata that was calculated from recording upload.
    recording.delete_after = upload_at + datetime.timedelta(days=15)
    attempt.is_submitted = True
    attempt.submitted_at = None

    assert sync_recording_expiry(recording, attempt) is None
    assert recording.delete_after is None
    assert is_recording_expired(recording) is True


def test_cleanup_uses_submission_deadline_repairs_date_and_is_idempotent(retention_db, monkeypatch):
    now = datetime.datetime.utcnow()
    _, expired_attempt, expired = add_recording(
        retention_db,
        4,
        submitted_at=now - datetime.timedelta(days=16),
        uploaded_at=now - datetime.timedelta(days=16),
        path="expired-by-submission",
    )
    # Deliberately stale later deadline from an upload-anchored/legacy policy.
    expired.delete_after = now + datetime.timedelta(days=14)
    _, recent_attempt, recent = add_recording(
        retention_db,
        5,
        submitted_at=now - datetime.timedelta(days=14),
        uploaded_at=now - datetime.timedelta(days=30),
        path="recent-submission-old-upload",
    )
    _, missing_attempt, missing = add_recording(
        retention_db,
        6,
        submitted_at=None,
        uploaded_at=now - datetime.timedelta(days=60),
        path="missing-submission-must-be-preserved",
    )
    missing.delete_after = now - datetime.timedelta(days=45)
    _, incomplete_attempt, incomplete = add_recording(
        retention_db,
        7,
        submitted_at=now - datetime.timedelta(days=30),
        uploaded_at=now - datetime.timedelta(days=30),
        path="not-completed-session",
        status="RECORDING",
    )
    retention_db.commit()

    removed = []
    monkeypatch.setattr(
        "app.services.storage_service.StorageService.delete_recording",
        lambda ref: removed.append(ref) or True,
    )

    assert cleanup_expired_recordings(retention_db) == 1
    assert removed == ["expired-by-submission"]
    retention_db.refresh(expired)
    retention_db.refresh(recent)
    retention_db.refresh(missing)
    assert expired.recording_path is None
    assert expired.recording_deleted_at is not None
    assert recent.recording_path == "recent-submission-old-upload"
    assert recent.delete_after == recent_attempt.submitted_at + datetime.timedelta(days=15)
    assert missing.recording_path == "missing-submission-must-be-preserved"
    assert missing.delete_after is None
    assert incomplete.recording_path == "not-completed-session"
    assert cleanup_expired_recordings(retention_db) == 0
    assert removed == ["expired-by-submission"]


def test_cleanup_failure_preserves_recording_metadata(retention_db, monkeypatch):
    submitted_at = datetime.datetime.utcnow() - datetime.timedelta(days=16)
    _, attempt, recording = add_recording(
        retention_db,
        8,
        submitted_at=submitted_at,
        uploaded_at=submitted_at,
        path="provider-delete-failure",
    )
    sync_recording_expiry(recording, attempt)
    deadline = submitted_at + datetime.timedelta(days=15)
    retention_db.commit()
    monkeypatch.setattr(
        "app.services.storage_service.StorageService.delete_recording",
        lambda _ref: False,
    )

    assert cleanup_expired_recordings(retention_db) == 0
    retention_db.refresh(recording)
    assert recording.recording_path == "provider-delete-failure"
    assert recording.recording_deleted_at is None
    assert recording.delete_after == deadline


def test_duplicate_submission_keeps_original_deadline(retention_db, monkeypatch):
    from types import SimpleNamespace

    from app.routers import candidate_assessments
    submitted_at = datetime.datetime.utcnow() - datetime.timedelta(days=2)
    _, attempt, recording = add_recording(
        retention_db,
        9,
        submitted_at=submitted_at,
        uploaded_at=submitted_at - datetime.timedelta(minutes=5),
        path="duplicate-submit",
    )
    first_deadline = sync_recording_expiry(recording, attempt)
    assignment = SimpleNamespace(id=9, attempt=attempt)
    monkeypatch.setattr(
        candidate_assessments,
        "get_owned_assignment",
        lambda *_args: assignment,
    )

    # Exercise the actual duplicate HTTP handler's logic: it returns the
    # original submission before evaluation or retention timestamps are touched.
    response = candidate_assessments.submit_assessment(
        assignment_id=9,
        req=None,
        candidate=SimpleNamespace(id=9),
        db=SimpleNamespace(),
    )
    assert response["submitted_at"] == submitted_at
    assert recording.delete_after == first_deadline
    assert attempt.submitted_at == submitted_at
