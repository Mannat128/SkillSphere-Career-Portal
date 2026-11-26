import datetime
import logging
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core.security import get_password_hash, verify_password
from app.database.base import Base
from app.models.audit import AuditLog
from app.models.user import PasswordResetToken, User, UserRole
from app.routers import auth
from app.schemas.auth import ForgotPasswordRequest, LoginRequest, ResetPasswordRequest
from app.services.email_service import EmailService


@pytest.fixture
def reset_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[User.__table__, PasswordResetToken.__table__, AuditLog.__table__])
    with Session(engine) as db:
        yield db
    engine.dispose()


def request_from(address=None):
    return Request({"type": "http", "method": "POST", "path": "/auth/forgot-password", "headers": [], "client": (address or f"test-{uuid.uuid4().hex}", 1234)})


def test_reset_request_is_generic_and_stores_only_token_hash(reset_db, monkeypatch):
    user = User(email="reset@example.com", full_name="Reset Test", hashed_password=get_password_hash("OldPass123"), role=UserRole.CANDIDATE, is_active=True)
    reset_db.add(user)
    reset_db.commit()
    sent = []
    monkeypatch.setattr(EmailService, "send_password_reset_email", lambda email, token: sent.append((email, token)) or True)

    existing = auth.forgot_password(ForgotPasswordRequest(email=user.email), request_from(), reset_db)
    missing = auth.forgot_password(ForgotPasswordRequest(email="missing@example.com"), request_from(), reset_db)

    assert existing == missing
    assert len(sent) == 1
    stored = reset_db.query(PasswordResetToken).one()
    assert stored.token != sent[0][1]
    assert stored.token == auth._password_reset_fingerprint(sent[0][1])
    assert len(sent[0][1]) >= 40


def test_reset_is_single_use_invalidates_other_links_and_updates_password(reset_db, monkeypatch):
    user = User(email="reset-flow@example.com", full_name="Reset Flow", hashed_password=get_password_hash("OldPass123"), role=UserRole.CANDIDATE, is_active=True)
    reset_db.add(user)
    reset_db.commit()
    sent = []
    monkeypatch.setattr(EmailService, "send_password_reset_email", lambda email, token: sent.append(token) or True)

    auth.forgot_password(ForgotPasswordRequest(email=user.email), request_from(), reset_db)
    auth.forgot_password(ForgotPasswordRequest(email=user.email), request_from(), reset_db)
    auth.reset_password(ResetPasswordRequest(token=sent[0], new_password="NewPassword123"), reset_db)

    reset_db.refresh(user)
    assert verify_password("NewPassword123", user.hashed_password)
    login = auth.login(LoginRequest(email=user.email, password="NewPassword123"), reset_db)
    assert login["token_type"] == "bearer"
    assert login["user"]["id"] == user.id
    tokens = reset_db.query(PasswordResetToken).all()
    assert all(item.is_used for item in tokens)
    with pytest.raises(Exception):
        auth.reset_password(ResetPasswordRequest(token=sent[1], new_password="AnotherPass123"), reset_db)


def test_expired_reset_token_is_rejected(reset_db):
    user = User(email="expired@example.com", full_name="Expired Test", hashed_password=get_password_hash("OldPass123"), role=UserRole.CANDIDATE, is_active=True)
    reset_db.add(user)
    reset_db.flush()
    raw = "synthetic-expired-reset-token"
    reset_db.add(PasswordResetToken(user_id=user.id, token=auth._password_reset_fingerprint(raw), expires_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=1)))
    reset_db.commit()

    with pytest.raises(Exception):
        auth.reset_password(ResetPasswordRequest(token=raw, new_password="NewPassword123"), reset_db)


def test_reset_request_ip_rate_limit_is_bounded():
    address = f"rate-{uuid.uuid4().hex}"
    for _ in range(auth._RESET_RATE_MAX_REQUESTS):
        auth._enforce_password_reset_rate_limit(request_from(address))
    with pytest.raises(Exception) as error:
        auth._enforce_password_reset_rate_limit(request_from(address))
    assert getattr(error.value, "status_code", None) == 429


def test_new_password_validation_requires_letter_and_number():
    with pytest.raises(Exception):
        ResetPasswordRequest(token="synthetic-token-value-that-is-long-enough", new_password="onlyletters")


def test_development_email_omits_reset_token_from_logs(monkeypatch, caplog):
    from app.core.config import settings
    token = "synthetic-reset-secret-never-log"
    monkeypatch.setattr(settings, "EMAIL_MODE", "development")
    monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173")
    with caplog.at_level(logging.INFO, logger="SkillSphere.Email"):
        EmailService.send_password_reset_email("reset@example.com", token)
    assert token not in caplog.text
    assert "Body omitted" in caplog.text
