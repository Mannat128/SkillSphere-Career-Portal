"""Isolated HTTP integration coverage for the SkillSphere Assistant.

The module sets synthetic settings before importing the FastAPI application.
Every request uses a temporary SQLite database through the common get_db
override; application startup/lifespan initialization is deliberately skipped.
"""

import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Override all configuration needed by application imports with synthetic
# values. The unreachable MySQL URL is a guard against accidental default
# dependency use; no test opens it.
_ISOLATED_TEST_ROOT = tempfile.mkdtemp(
    prefix=".skillsphere-assistant-http-",

)
_ISOLATED_UPLOAD_DIR = str(Path(_ISOLATED_TEST_ROOT) / "uploads")
os.environ.update({
    "DATABASE_HOST": "127.0.0.1",
    "DATABASE_PORT": "1",
    "DATABASE_NAME": "skillsphere_assistant_http_isolated",
    "DATABASE_USER": "synthetic_test_user",
    "DATABASE_PASSWORD": "synthetic_test_password_only",
    "SECRET_KEY": "phase6-isolated-test-secret-not-for-production",
    "ADMIN_NAME": "Synthetic Test Admin",
    "ADMIN_EMAIL": "phase6-admin@example.test",
    "ADMIN_PASSWORD": "synthetic-admin-password-only",
    "UPLOAD_DIR": _ISOLATED_UPLOAD_DIR,
    "EMAIL_MODE": "development",
    "ENABLE_RECORDING_CLEANUP": "false",
})

from app.core.security import create_access_token
from app.core.dependencies import get_db
from app.core.config import settings
from app.database.base import Base
from app.models import User, UserRole
from app.models.sphera import AssistantFeedback, SpheraConversation, SpheraMessage

# Another isolated test module may have instantiated the settings singleton
# first. Reassert the synthetic values directly before importing the app,
# whose module import creates its upload/private directories.
settings.DATABASE_HOST = "127.0.0.1"
settings.DATABASE_PORT = 1
settings.DATABASE_NAME = "skillsphere_assistant_http_isolated"
settings.DATABASE_USER = "synthetic_test_user"
settings.DATABASE_PASSWORD = "synthetic_test_password_only"
settings.SECRET_KEY = "phase6-isolated-test-secret-not-for-production"
settings.ADMIN_NAME = "Synthetic Test Admin"
settings.ADMIN_EMAIL = "phase6-admin@example.test"
settings.ADMIN_PASSWORD = "synthetic-admin-password-only"
settings.UPLOAD_DIR = _ISOLATED_UPLOAD_DIR
settings.EMAIL_MODE = "development"
settings.SMTP_HOST = "localhost"
settings.SMTP_USER = "synthetic_test_user"
settings.SMTP_PASSWORD = "synthetic_test_password_only"
settings.AI_API_KEY = None
settings.GEMINI_API_KEY = None
settings.CLOUDINARY_CLOUD_NAME = None
settings.CLOUDINARY_API_KEY = None
settings.CLOUDINARY_API_SECRET = None
settings.STORAGE_BACKEND = "local"
settings.ENABLE_RECORDING_CLEANUP = False

from app.main import app


@asynccontextmanager
async def _disabled_lifespan(_app):
    """Do not run init_db or the recording cleanup scheduler in tests."""
    yield


app.router.lifespan_context = _disabled_lifespan


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(
        subject=user.email,
        role=user.role.value,
        user_id=user.id,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def isolated_http():
    """Create a fresh SQLite database and client for each HTTP test."""
    db_path = Path(tempfile.mkdtemp(
        prefix=".skillsphere-assistant-db-",

    )) / "assistant.sqlite"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 20},
    )
    assert engine.dialect.name == "sqlite"
    assert "skillsphere_assistant_http_isolated" not in str(engine.url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    suffix = uuid4().hex
    with factory() as db:
        candidate = User(
            email=f"candidate-{suffix}@example.test",
            full_name="Synthetic Candidate",
            hashed_password="not-a-real-password-hash",
            role=UserRole.CANDIDATE,
            is_active=True,
        )
        other_candidate = User(
            email=f"other-candidate-{suffix}@example.test",
            full_name="Synthetic Other Candidate",
            hashed_password="not-a-real-password-hash",
            role=UserRole.CANDIDATE,
            is_active=True,
        )
        recruiter = User(
            email=f"recruiter-{suffix}@example.test",
            full_name="Synthetic Recruiter",
            hashed_password="not-a-real-password-hash",
            role=UserRole.RECRUITER,
            is_active=True,
        )
        admin = User(
            email=f"admin-{suffix}@example.test",
            full_name="Synthetic Admin",
            hashed_password="not-a-real-password-hash",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add_all([candidate, other_candidate, recruiter, admin])
        db.commit()
        for actor in [candidate, other_candidate, recruiter, admin]:
            db.refresh(actor)
        actors = {
            "candidate": candidate,
            "other_candidate": other_candidate,
            "recruiter": recruiter,
            "admin": admin,
        }

    # On Windows, Python's Proactor loop needs socket.socketpair() for its
    # self-pipe. This Python build has no AF_UNIX, so socketpair falls back to
    # loopback TCP; in restricted Windows runners that fallback can block in
    # accept(). Starlette supports Trio as a TestClient backend, avoiding that
    # Proactor initialization path while still exercising the real ASGI app.
    client = TestClient(app, backend="trio")
    try:
        with client:
            yield client, actors, factory, engine
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()
        shutil.rmtree(db_path.parent, ignore_errors=True)


def _guest_session(client: TestClient) -> str:
    response = client.post("/api/v1/assistant/guest-session")
    assert response.status_code == 200, response.text
    token = response.json()["session_token"]
    assert token
    return token


def _chat(client, message, *, session=None, headers=None):
    request_headers = dict(headers or {})
    if session:
        request_headers["X-Assistant-Session"] = session
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": message},
        headers=request_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_isolated_database_identity_and_guest_session_validation(isolated_http):
    client, _actors, _factory, _engine = isolated_http
    from app.database.connection import engine as configured_engine

    # The application's configured engine was constructed only from synthetic
    # process settings, and request data is written to isolated SQLite.
    assert settings.DATABASE_NAME == "skillsphere_assistant_http_isolated"
    assert configured_engine.url.host == "127.0.0.1"
    assert configured_engine.url.port == 1
    assert configured_engine.url.database == "skillsphere_assistant_http_isolated"
    guest = _guest_session(client)
    own_history = client.get(
        "/api/v1/assistant/conversations",
        headers={"X-Assistant-Session": guest},
    )
    assert own_history.status_code == 200
    assert own_history.json() == []
    invalid = client.get(
        "/api/v1/assistant/conversations",
        headers={"X-Assistant-Session": "not-a-valid-token"},
    )
    assert invalid.status_code == 403


def test_chat_request_validation_and_invalid_language_errors(isolated_http):
    client, _actors, _factory, _engine = isolated_http
    guest = _guest_session(client)
    headers = {"X-Assistant-Session": guest}

    empty = client.post("/api/v1/assistant/chat", json={"message": ""}, headers=headers)
    too_long = client.post(
        "/api/v1/assistant/chat",
        json={"message": "x" * 2001},
        headers=headers,
    )
    unsupported_language = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Hello assistant", "language": "unsupported"},
        headers=headers,
    )
    assert empty.status_code == 422
    assert too_long.status_code == 422
    assert unsupported_language.status_code == 400


def test_guest_conversation_history_is_owned_and_private(isolated_http):
    client, _actors, _factory, _engine = isolated_http
    guest_a = _guest_session(client)
    guest_b = _guest_session(client)
    chat = _chat(client, "How do I browse jobs?", session=guest_a)
    path = f"/api/v1/assistant/conversations/{chat['conversation_id']}"

    own = client.get(path, headers={"X-Assistant-Session": guest_a})
    foreign = client.get(path, headers={"X-Assistant-Session": guest_b})
    missing = client.get(path)
    assert own.status_code == 200 and len(own.json()["messages"]) == 2
    assert foreign.status_code == 404
    assert missing.status_code == 403


def test_candidate_and_recruiter_conversation_ownership_and_role_guidance(isolated_http):
    client, actors, _factory, _engine = isolated_http
    candidate_headers = _auth_header(actors["candidate"])
    other_headers = _auth_header(actors["other_candidate"])
    recruiter_headers = _auth_header(actors["recruiter"])

    candidate_chat = _chat(client, "How do I create a question bank?", headers=candidate_headers)
    recruiter_chat = _chat(client, "How do I create a question bank?", headers=recruiter_headers)
    candidate_path = f"/api/v1/assistant/conversations/{candidate_chat['conversation_id']}"
    recruiter_path = f"/api/v1/assistant/conversations/{recruiter_chat['conversation_id']}"
    assert client.get(candidate_path, headers=candidate_headers).status_code == 200
    assert client.get(candidate_path, headers=other_headers).status_code == 404
    assert client.get(candidate_path, headers=recruiter_headers).status_code == 404
    assert client.get(recruiter_path, headers=recruiter_headers).status_code == 200
    assert client.get(recruiter_path, headers=candidate_headers).status_code == 404

    candidate_options = client.get("/api/v1/assistant/options", headers=candidate_headers).json()
    recruiter_options = client.get("/api/v1/assistant/options", headers=recruiter_headers).json()
    assert candidate_options["role"] == "candidate"
    assert "Question Bank" not in candidate_options["quick_actions"]
    assert recruiter_options["role"] == "recruiter"
    assert "Question Bank" in recruiter_options["quick_actions"]
    assert "/recruiter/question-bank" in str(recruiter_chat["actions"])
    assert "/recruiter/question-bank" not in str(candidate_chat["actions"])


def test_support_ticket_requires_auth_and_accepts_synthetic_authenticated_request(isolated_http):
    client, actors, _factory, _engine = isolated_http
    ticket_form = {
        "subject": "Synthetic integration test issue",
        "description": "Synthetic test ticket; no real user data.",
        "category": "TECHNICAL",
        "priority": "LOW",
    }
    anonymous = client.post("/api/v1/support-tickets", data=ticket_form)
    assert anonymous.status_code == 401

    authenticated = client.post(
        "/api/v1/support-tickets",
        data=ticket_form,
        headers=_auth_header(actors["candidate"]),
    )
    assert authenticated.status_code == 200, authenticated.text
    payload = authenticated.json()["ticket"]
    assert payload["subject"] == ticket_form["subject"]
    assert payload["created_by_id"] == actors["candidate"].id


def test_guest_feedback_is_redacted_and_duplicate_submission_is_rejected(isolated_http):
    client, actors, factory, _engine = isolated_http
    guest = _guest_session(client)
    chat = _chat(client, "How do I sign in? email alice@example.test password: SecretTestPass9", session=guest)
    assert chat["intent"] == "login"
    with factory() as db:
        stored = db.query(SpheraMessage).filter_by(
            conversation_id=chat["conversation_id"], role="user"
        ).one()
        assert "alice@example.test" not in stored.text
        assert "SecretTestPass9" not in stored.text
        assert "sign in" in stored.text.lower()

    feedback_body = {
        "message_id": chat["message_id"],
        "rating": "not_helpful",
        "category": "incomplete",
        "comment": "Contact alice@example.test, password: AnotherSecret9",
    }
    headers = {"X-Assistant-Session": guest}
    submitted = client.post("/api/v1/assistant/feedback", json=feedback_body, headers=headers)
    duplicate = client.post("/api/v1/assistant/feedback", json=feedback_body, headers=headers)
    assert submitted.status_code == 200, submitted.text
    assert duplicate.status_code == 400
    with factory() as db:
        stored_feedback = db.query(AssistantFeedback).one()
        assert "alice@example.test" not in stored_feedback.comment
        assert "AnotherSecret9" not in stored_feedback.comment
        assert db.query(AssistantFeedback).count() == 1

    # Authenticated feedback is also one submission per user/message.
    candidate_headers = _auth_header(actors["candidate"])
    candidate_chat = _chat(client, "How can I edit my candidate profile?", headers=candidate_headers)
    authenticated_body = {"message_id": candidate_chat["message_id"], "rating": "helpful"}
    first = client.post("/api/v1/assistant/feedback", json=authenticated_body, headers=candidate_headers)
    second = client.post("/api/v1/assistant/feedback", json=authenticated_body, headers=candidate_headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 400
    with factory() as db:
        assert db.query(AssistantFeedback).filter_by(user_id=actors["candidate"].id).count() == 1
        assert db.query(AssistantFeedback).count() == 2


def test_concurrent_guest_feedback_http_submissions_create_one_record(isolated_http):
    client, _actors, factory, _engine = isolated_http
    guest = _guest_session(client)
    chat = _chat(client, "Explain how profile editing works.", session=guest)
    body = {"message_id": chat["message_id"], "rating": "helpful"}
    headers = {"X-Assistant-Session": guest}

    def submit_once(_):
        return client.post("/api/v1/assistant/feedback", json=body, headers=headers)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(submit_once, range(2)))
    assert sorted(response.status_code for response in responses) == [200, 400]
    with factory() as db:
        assert db.query(AssistantFeedback).count() == 1


def test_admin_feedback_and_moderation_history_are_admin_only(isolated_http):
    client, actors, _factory, _engine = isolated_http
    guest = _guest_session(client)
    chat = _chat(client, "Tell me about SkillSphere.", session=guest)
    submitted = client.post(
        "/api/v1/assistant/feedback",
        json={"message_id": chat["message_id"], "rating": "not_helpful", "category": "incomplete"},
        headers={"X-Assistant-Session": guest},
    )
    assert submitted.status_code == 200
    feedback_id = submitted.json()["feedback_id"]
    feedback_url = "/api/v1/assistant/admin/feedback"
    analytics_url = "/api/v1/assistant/admin/analytics"
    history_url = f"/api/v1/assistant/admin/feedback/{feedback_id}/history"
    assert client.get(feedback_url).status_code == 401
    assert client.get(feedback_url, headers=_auth_header(actors["candidate"])).status_code == 403
    assert client.get(analytics_url, headers=_auth_header(actors["candidate"])).status_code == 403
    assert client.get(history_url, headers=_auth_header(actors["recruiter"])).status_code == 403
    admin_headers = _auth_header(actors["admin"])
    assert client.get(analytics_url, headers=admin_headers).status_code == 200
    assert client.get("/api/v1/assistant/admin/unanswered", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/assistant/admin/knowledge-suggestions", headers=admin_headers).status_code == 200
    admin_feedback = client.get(feedback_url, headers=admin_headers)
    assert admin_feedback.status_code == 200
    assert "Tell me about SkillSphere" not in str(admin_feedback.json())
    assert client.patch(
        f"/api/v1/assistant/admin/feedback/{feedback_id}",
        json={"status": "RESOLVED"},
        headers=_auth_header(actors["candidate"]),
    ).status_code == 403

    update = client.patch(
        f"/api/v1/assistant/admin/feedback/{feedback_id}",
        json={"status": "IN_PROGRESS", "priority": "HIGH", "admin_notes": "Synthetic moderation note"},
        headers=admin_headers,
    )
    assert update.status_code == 200, update.text
    history = client.get(history_url, headers=admin_headers)
    assert history.status_code == 200
    assert history.json()[0]["changes"]["status"] == {"from": "OPEN", "to": "IN_PROGRESS"}
    assert history.json()[0]["changes"]["priority"] == {"from": "MEDIUM", "to": "HIGH"}
    serialized_history = str(history.json())
    assert "Tell me about SkillSphere" not in serialized_history


def test_chat_http_path_never_invokes_external_llm(isolated_http, monkeypatch):
    from app.services.ai_service import AIService

    monkeypatch.setattr(
        AIService,
        "_request_text",
        staticmethod(lambda *args, **kwargs: pytest.fail("Assistant HTTP route invoked an external AI provider")),
    )
    client, _actors, _factory, _engine = isolated_http
    guest = _guest_session(client)
    response = _chat(client, "How do I upload my resume?", session=guest)
    assert response["reply"]
    assert response["actions"]


@pytest.fixture(scope="session", autouse=True)
def _cleanup_import_side_effect_directories():
    yield
    shutil.rmtree(_ISOLATED_TEST_ROOT, ignore_errors=True)
