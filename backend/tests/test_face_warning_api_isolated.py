from types import SimpleNamespace

import pytest

from app.routers import proctoring


@pytest.mark.parametrize(
    "violation_type",
    ["AI_NO_FACE_DETECTED", "AI_LOOKING_AWAY_DETECTED"],
)
def test_face_review_signals_are_accepted_and_audited(monkeypatch, violation_type):
    assignment = SimpleNamespace(id=14, attempt=None)
    session = SimpleNamespace(
        id=23,
        consent_given=True,
        camera_permission_granted=True,
        microphone_permission_granted=True,
        session_status="RECORDING",
        warning_count=0,
        is_flagged_for_review=False,
        last_violation_type=None,
        last_violation_at=None,
        updated_at=None,
    )
    candidate = SimpleNamespace(id=9)
    captured = []
    db = SimpleNamespace(add=captured.append, commit=lambda: None)

    monkeypatch.setattr(
        proctoring,
        "get_candidate_assignment",
        lambda *_args: assignment,
    )
    monkeypatch.setattr(
        proctoring,
        "get_proctoring_session",
        lambda *_args: session,
    )

    result = proctoring.record_proctoring_violation(
        assignment_id=assignment.id,
        request=proctoring.ProctoringViolationRequest(
            violation_type=violation_type
        ),
        candidate=candidate,
        db=db,
    )

    assert result["warning_count"] == 1
    assert session.last_violation_type == violation_type
    assert len(captured) == 1
    assert captured[0].violation_type == violation_type
    assert captured[0].details == {"source": "BROWSER_PROCTORING"}
