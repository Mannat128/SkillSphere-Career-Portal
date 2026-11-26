import datetime
from types import SimpleNamespace

import pytest

from app.core.exceptions import BadRequestException
from app.routers.candidate_assessments import (
    assessment_availability,
    as_utc_naive,
    ensure_assessment_available,
    get_assessment_instructions,
    start_or_resume_assessment,
)
from app.routers import candidate_assessments


def test_assessment_availability_accepts_active_utc_window():
    now = datetime.datetime(2026, 11, 21, 12, 0, 0)
    ensure_assessment_available(
        {
            "available_from": "2026-11-21T11:00:00Z",
            "available_until": "2026-11-21T13:00:00Z",
        },
        now,
    )
    assert assessment_availability(
        {
            "available_from": "2026-11-21T11:00:00Z",
            "available_until": "2026-11-21T13:00:00Z",
        },
        now,
    ) == (True, "available")


def test_assessment_availability_rejects_future_window():
    now = datetime.datetime(2026, 11, 21, 12, 0, 0)
    with pytest.raises(BadRequestException, match="not available yet"):
        ensure_assessment_available(
            {"available_from": "2026-11-21T12:00:01Z"}, now
        )
    assert assessment_availability(
        {"available_from": "2026-11-21T12:00:01Z"}, now
    ) == (False, "future")


@pytest.mark.parametrize(
    "end_time",
    ["2026-11-21T11:59:59Z", "2026-11-21T12:00:00Z"],
)
def test_assessment_availability_rejects_expired_and_exact_end(end_time):
    now = datetime.datetime(2026, 11, 21, 12, 0, 0)
    with pytest.raises(BadRequestException, match="window has ended"):
        ensure_assessment_available({"available_until": end_time}, now)


def test_assessment_availability_normalizes_offsets_to_utc():
    assert as_utc_naive("2026-11-21T17:30:00+05:30") == datetime.datetime(
        2026, 11, 21, 12, 0, 0
    )
    # Legacy naive availability values remain interpreted as UTC.
    assert as_utc_naive("2026-11-21T12:00:00") == datetime.datetime(
        2026, 11, 21, 12, 0, 0
    )


def test_assessment_availability_reports_expired_state_for_candidate_ui():
    now = datetime.datetime(2026, 11, 21, 12, 0, 0)

    assert assessment_availability(
        {"available_until": "2026-11-21T12:00:00Z"}, now
    ) == (False, "expired")


def test_direct_start_rejects_expired_window_without_creating_attempt(monkeypatch):
    now = datetime.datetime.utcnow()
    assignment = SimpleNamespace(
        id=41,
        config_snapshot={"available_until": (now - datetime.timedelta(seconds=1)).isoformat() + "Z"},
        attempt=None,
        status="ASSIGNED",
        assigned_questions=[],
    )
    candidate = SimpleNamespace(id=72)
    writes = []
    db = SimpleNamespace(add=lambda value: writes.append(("add", value)), commit=lambda: writes.append(("commit", None)))
    monkeypatch.setattr(candidate_assessments, "get_owned_assignment", lambda *_args: assignment)
    monkeypatch.setattr(candidate_assessments, "require_proctoring_consent", lambda *_args: object())

    with pytest.raises(BadRequestException, match="window has ended"):
        start_or_resume_assessment(41, candidate, db)

    assert writes == []


def test_existing_unexpired_attempt_cannot_resume_after_start_window_closes(monkeypatch):
    now = datetime.datetime.utcnow()
    question = {
        "id": 17,
        "question_text": "Synthetic resume test question",
        "category": "Synthetic",
        "difficulty": "Easy",
        "option_a": "A",
        "option_b": "B",
        "option_c": "C",
        "option_d": "D",
        "marks": 1.0,
    }
    attempt = SimpleNamespace(
        id=901,
        candidate_id=72,
        is_submitted=False,
        expires_at=now + datetime.timedelta(minutes=5),
        started_at=now - datetime.timedelta(minutes=5),
        saved_answers={"17": "B"},
        marked_for_review=[17],
    )
    assignment = SimpleNamespace(
        id=41,
        config_snapshot={"available_until": (now - datetime.timedelta(seconds=1)).isoformat() + "Z", "duration_minutes": 10},
        attempt=attempt,
        status="IN_PROGRESS",
        assigned_questions=[question],
    )
    candidate = SimpleNamespace(id=72)
    writes = []
    db = SimpleNamespace(add=lambda value: writes.append(("add", value)), commit=lambda: writes.append(("commit", None)))
    monkeypatch.setattr(candidate_assessments, "get_owned_assignment", lambda *_args: assignment)
    monkeypatch.setattr(candidate_assessments, "require_proctoring_consent", lambda *_args: object())

    with pytest.raises(BadRequestException, match="window has ended"):
        start_or_resume_assessment(41, candidate, db)
    assert writes == []


def test_valid_existing_attempt_remains_resumable_inside_window(monkeypatch):
    now = datetime.datetime.utcnow()
    attempt = SimpleNamespace(
        is_submitted=False,
        expires_at=now + datetime.timedelta(minutes=3),
    )
    assignment = SimpleNamespace(
        id=42,
        job=None,
        config_snapshot={"available_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z"},
        status="IN_PROGRESS",
        attempt=attempt,
    )
    monkeypatch.setattr(candidate_assessments, "get_owned_assignment", lambda *_args: assignment)

    response = get_assessment_instructions(42, SimpleNamespace(id=72), SimpleNamespace())

    assert response["assignment_id"] == 42
    assert response["availability_status"] == "available"
    assert response["can_start"] is False
    assert response["can_resume"] is True
    assert response["can_access_camera"] is True

    assignment.attempt = None
    assignment.status = "ASSIGNED"
    response = get_assessment_instructions(42, SimpleNamespace(id=72), SimpleNamespace())
    assert response["can_start"] is True
    assert response["can_resume"] is False
    assert response["can_access_camera"] is True


def test_expired_instructions_disable_camera_for_assignment_id(monkeypatch):
    now = datetime.datetime.utcnow()
    assignment = SimpleNamespace(
        id=42,
        job=None,
        config_snapshot={"available_until": (now - datetime.timedelta(seconds=1)).isoformat() + "Z"},
        status="IN_PROGRESS",
        attempt=SimpleNamespace(
            is_submitted=False,
            expires_at=now + datetime.timedelta(minutes=3),
        ),
    )
    monkeypatch.setattr(candidate_assessments, "get_owned_assignment", lambda *_args: assignment)

    response = get_assessment_instructions(42, SimpleNamespace(id=72), SimpleNamespace())

    assert response["is_available"] is False
    assert response["assignment_id"] == 42
    assert response["availability_status"] == "expired"
    assert response["can_start"] is False
    assert response["can_resume"] is False
    assert response["can_access_camera"] is False
    assert response["availability_message"] == "The assessment availability window has ended."

    assignment.attempt.expires_at = now - datetime.timedelta(seconds=1)
    response = get_assessment_instructions(42, SimpleNamespace(id=72), SimpleNamespace())
    assert response["can_resume"] is False
    assert response["can_access_camera"] is False

    assignment.attempt.expires_at = now + datetime.timedelta(minutes=3)
    assignment.status = "EXPIRED"
    response = get_assessment_instructions(42, SimpleNamespace(id=72), SimpleNamespace())
    assert response["can_resume"] is False
    assert response["can_access_camera"] is False


def test_expired_attempt_start_request_is_rejected_even_when_attempt_exists(monkeypatch):
    now = datetime.datetime.utcnow()
    assignment = SimpleNamespace(
        id=44,
        config_snapshot={"available_until": (now - datetime.timedelta(seconds=1)).isoformat() + "Z"},
        attempt=SimpleNamespace(
            id=903,
            candidate_id=72,
            is_submitted=False,
            expires_at=now + datetime.timedelta(minutes=2),
        ),
        status="IN_PROGRESS",
        assigned_questions=[],
    )
    writes = []
    monkeypatch.setattr(candidate_assessments, "get_owned_assignment", lambda *_args: assignment)
    with pytest.raises(BadRequestException, match="window has ended"):
        start_or_resume_assessment(
            44,
            SimpleNamespace(id=72),
            SimpleNamespace(add=lambda value: writes.append(value), commit=lambda: writes.append("commit")),
        )
    assert writes == []


def test_terminal_assignment_rejects_even_an_unexpired_attempt(monkeypatch):
    now = datetime.datetime.utcnow()
    assignment = SimpleNamespace(
        id=43,
        config_snapshot={"duration_minutes": 10},
        attempt=SimpleNamespace(
            id=902,
            candidate_id=72,
            is_submitted=False,
            expires_at=now + datetime.timedelta(minutes=3),
        ),
        status="EXPIRED",
    )
    writes = []
    monkeypatch.setattr(candidate_assessments, "get_owned_assignment", lambda *_args: assignment)
    with pytest.raises(BadRequestException, match="no longer available"):
        start_or_resume_assessment(
            43,
            SimpleNamespace(id=72),
            SimpleNamespace(add=lambda value: writes.append(value), commit=lambda: writes.append("commit")),
        )
    assert writes == []
