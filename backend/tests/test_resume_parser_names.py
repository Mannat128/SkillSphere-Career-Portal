from app.services.resume_parser import ResumeParser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models import Candidate, OCRStatusEnum, Resume, ResumeOCRResult, User, UserRole
from app.routers.resumes import confirm_and_save_profile
from app.schemas.resume import ResumeConfirmRequest


def test_resume_parser_skips_professional_summary_heading_and_finds_name():
    raw = """Ishi Sharma
ishi@example.test
Pune
PROFESSIONAL SUMMARY
Experienced software engineer with a focus on backend services.
"""

    extracted, _ = ResumeParser.parse(raw)

    assert extracted["full_name"] == "Ishi Sharma"


def test_resume_parser_does_not_treat_section_heading_as_candidate_name():
    extracted, _ = ResumeParser.parse("PROFESSIONAL SUMMARY\nExperienced software engineer")

    assert extracted["full_name"] is None
    assert not ResumeParser.is_probable_person_name("PROFESSIONAL SUMMARY")


def test_resume_parser_accepts_labelled_full_name():
    extracted, _ = ResumeParser.parse("Full Name: Aisha Khan\nEmail: aisha@example.test")

    assert extracted["full_name"] == "Aisha Khan"


def test_confirmed_legacy_ocr_heading_does_not_replace_candidate_name():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    user = User(
        id=95201, email="synthetic-resume-name@example.test",
        full_name="Synthetic Account Name", hashed_password="synthetic-only",
        role=UserRole.CANDIDATE,
    )
    candidate = Candidate(id=95202, user=user, profile_percentage=0)
    resume = Resume(
        id=95203, candidate=candidate, file_name="synthetic.pdf",
        original_filename="synthetic.pdf", file_path="C:/synthetic.pdf",
        file_size=10, mime_type="application/pdf",
    )
    resume.ocr_result = ResumeOCRResult(
        status=OCRStatusEnum.COMPLETED,
        raw_text="Ishi Sharma\nishi@example.test\nPROFESSIONAL SUMMARY\nSoftware engineer.",
        extracted_data={
            "full_name": "PROFESSIONAL SUMMARY", "skills": [],
            "educations": [], "experiences": [], "projects": [],
        },
    )
    db.add_all([user, candidate, resume])
    db.commit()

    confirm_and_save_profile(
        resume.id, ResumeConfirmRequest(apply_to_profile=True), candidate, user, db,
    )

    assert user.full_name == "Ishi Sharma"
    assert resume.ocr_result.extracted_data["full_name"] == "Ishi Sharma"
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()
