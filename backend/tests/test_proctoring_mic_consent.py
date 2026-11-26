from types import SimpleNamespace

import pytest

from app.core.exceptions import BadRequestException
from app.routers.candidate_assessments import require_proctoring_consent


class SessionQuery:
    def __init__(self, session):
        self.session = session

    def filter(self, *_conditions):
        return self

    def first(self):
        return self.session


def test_assessment_start_rejects_missing_microphone_permission():
    session = SimpleNamespace(
        consent_given=True,
        camera_permission_granted=True,
        microphone_permission_granted=False,
    )
    db = SimpleNamespace(query=lambda *_models: SessionQuery(session))

    with pytest.raises(BadRequestException, match="Microphone permission"):
        require_proctoring_consent(
            SimpleNamespace(id=11),
            SimpleNamespace(id=22),
            db,
        )


def test_assessment_start_accepts_explicit_microphone_permission():
    session = SimpleNamespace(
        consent_given=True,
        camera_permission_granted=True,
        microphone_permission_granted=True,
    )
    db = SimpleNamespace(query=lambda *_models: SessionQuery(session))

    assert require_proctoring_consent(
        SimpleNamespace(id=11),
        SimpleNamespace(id=22),
        db,
    ) is session
