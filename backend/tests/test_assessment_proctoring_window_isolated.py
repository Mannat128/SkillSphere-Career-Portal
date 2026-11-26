"""Regression tests for server-side proctoring access-window enforcement."""

import datetime
from types import SimpleNamespace

import pytest

from app.core.exceptions import BadRequestException
from app.routers import proctoring


@pytest.mark.parametrize("window", ["expired", "future"])
def test_consent_api_rejects_assessment_outside_configured_window(
    monkeypatch, window
):
    now = datetime.datetime.utcnow()
    timestamp = (
        now - datetime.timedelta(seconds=1)
        if window == "expired"
        else now + datetime.timedelta(minutes=5)
    )
    field = "available_until" if window == "expired" else "available_from"
    assignment = SimpleNamespace(
        id=51,
        config_snapshot={field: timestamp.isoformat() + "Z"},
        attempt=None,
    )
    writes = []
    monkeypatch.setattr(
        proctoring,
        "get_candidate_assignment",
        lambda *_args: assignment,
    )

    with pytest.raises(BadRequestException):
        proctoring.save_proctoring_consent(
            51,
            proctoring.ProctoringConsentRequest(
                consent_given=True,
                camera_permission_granted=True,
                microphone_permission_granted=True,
            ),
            SimpleNamespace(id=72),
            SimpleNamespace(add=lambda value: writes.append(value)),
        )

    assert writes == []


@pytest.mark.parametrize("window", ["expired", "future"])
def test_recording_start_rejects_assessment_outside_configured_window(
    monkeypatch, window
):
    now = datetime.datetime.utcnow()
    timestamp = (
        now - datetime.timedelta(seconds=1)
        if window == "expired"
        else now + datetime.timedelta(minutes=5)
    )
    field = "available_until" if window == "expired" else "available_from"
    assignment = SimpleNamespace(
        id=52,
        config_snapshot={field: timestamp.isoformat() + "Z"},
        attempt=SimpleNamespace(
            is_submitted=False,
            expires_at=now + datetime.timedelta(minutes=10),
        ),
    )
    monkeypatch.setattr(
        proctoring,
        "get_candidate_assignment",
        lambda *_args: assignment,
    )
    monkeypatch.setattr(
        proctoring,
        "get_proctoring_session",
        lambda *_args, **_kwargs: pytest.fail(
            "The proctoring session must not be reached outside availability."
        ),
    )

    with pytest.raises(BadRequestException):
        proctoring.start_recording(
            52,
            SimpleNamespace(id=72),
            SimpleNamespace(),
        )


def test_recording_start_rejects_expired_attempt(monkeypatch):
    now = datetime.datetime.utcnow()
    assignment = SimpleNamespace(
        id=53,
        config_snapshot={},
        attempt=SimpleNamespace(
            is_submitted=False,
            expires_at=now - datetime.timedelta(seconds=1),
        ),
    )
    monkeypatch.setattr(
        proctoring,
        "get_candidate_assignment",
        lambda *_args: assignment,
    )
    monkeypatch.setattr(
        proctoring,
        "get_proctoring_session",
        lambda *_args, **_kwargs: pytest.fail(
            "The proctoring session must not be reached after attempt expiry."
        ),
    )

    with pytest.raises(BadRequestException, match="duration has expired"):
        proctoring.start_recording(
            53,
            SimpleNamespace(id=72),
            SimpleNamespace(),
        )
