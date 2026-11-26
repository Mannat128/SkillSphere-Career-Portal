import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models import Candidate, User, UserRole
from app.routers.candidate import update_profile
from app.schemas.candidate import CandidateProfileUpdate


def test_candidate_profile_accepts_and_normalizes_full_name():
    request = CandidateProfileUpdate(full_name="  Ishi   Sharma  ")

    assert request.full_name == "Ishi Sharma"


@pytest.mark.parametrize(
    "value",
    ["PROFESSIONAL SUMMARY", "Skills", "Experience", "   "],
)
def test_candidate_profile_rejects_resume_headings_as_full_name(value):
    with pytest.raises(ValidationError):
        CandidateProfileUpdate(full_name=value)


def test_candidate_profile_save_updates_user_name_in_isolated_database():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    user = User(
        id=98301,
        email="synthetic-profile-name@example.test",
        full_name="PROFESSIONAL SUMMARY",
        hashed_password="synthetic-only",
        role=UserRole.CANDIDATE,
    )
    candidate = Candidate(id=98302, user=user, profile_percentage=0)
    db.add_all([user, candidate])
    db.commit()

    response = update_profile(
        CandidateProfileUpdate(full_name="Ishi Sharma"), candidate, user, db
    )

    assert user.full_name == "Ishi Sharma"
    assert response["full_name"] == "Ishi Sharma"

    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()
