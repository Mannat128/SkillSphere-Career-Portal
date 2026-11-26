import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.dependencies import require_role
from app.core.exceptions import ForbiddenException, NotFoundException
from app.database.base import Base
from app.models.candidate import Candidate
from app.models.resume import Resume, ResumeOCRResult
from app.models.recruiter import Company, Recruiter
from app.models.job import Job, JobStatusEnum
from app.models.application import Application
from app.models.user import User, UserRole
from app.routers.matching import compare_multi_jobs, analyze_resume
from app.routers.resumes import (
    _authorize_resume_read,
    get_resume_detail,
    get_ocr_status,
    get_extracted_data,
    download_resume,
)
from app.routers.recruiter import get_applicant_pipeline
from app.routers.question_bank import router as question_bank_router
from app.schemas.resume import MultiJobMatchRequest


@pytest.fixture
def isolated_db():
    """Use an in-memory DB so access-control tests never touch app data."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = sessions()

    owner = User(
        id=1001,
        email="resume-owner@example.test",
        hashed_password="unused",
        full_name="Resume Owner",
        role=UserRole.CANDIDATE,
    )
    other_user = User(
        id=1002,
        email="other-candidate@example.test",
        hashed_password="unused",
        full_name="Other Candidate",
        role=UserRole.CANDIDATE,
    )
    owner_candidate = Candidate(id=1001, user_id=owner.id, profile_percentage=20)
    other_candidate = Candidate(id=1002, user_id=other_user.id, profile_percentage=20)
    foreign_resume = Resume(
        id=1001,
        candidate_id=other_candidate.id,
        file_name="private.pdf",
        original_filename="private.pdf",
        file_path="/not-read-by-test/private.pdf",
        file_size=1,
        mime_type="application/pdf",
    )
    db.add_all([owner, other_user, owner_candidate, other_candidate, foreign_resume])
    db.commit()

    try:
        yield db, owner_candidate, foreign_resume
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_matching_endpoints_do_not_access_another_candidates_resume(isolated_db):
    db, candidate, foreign_resume = isolated_db

    with pytest.raises(NotFoundException):
        analyze_resume(
            resume_id=foreign_resume.id,
            job_id=1,
            candidate=candidate,
            db=db,
        )

    with pytest.raises(NotFoundException):
        compare_multi_jobs(
            req=MultiJobMatchRequest(resume_id=foreign_resume.id, job_ids=[1]),
            candidate=candidate,
            db=db,
        )


def test_admin_is_denied_from_recruiter_question_bank():
    admin = User(
        id=1003,
        email="admin@example.test",
        hashed_password="unused",
        full_name="Admin",
        role=UserRole.ADMIN,
    )
    recruiter_only = question_bank_router.dependencies[0].dependency

    with pytest.raises(ForbiddenException):
        recruiter_only(current_user=admin)


def test_matching_role_guard_rejects_admin():
    admin = User(
        id=1004,
        email="matching-admin@example.test",
        hashed_password="unused",
        full_name="Admin",
        role=UserRole.ADMIN,
    )
    candidate_only = require_role(UserRole.CANDIDATE)

    with pytest.raises(ForbiddenException):
        candidate_only(current_user=admin)


def test_resume_read_endpoints_block_another_candidate(isolated_db):
    db, owner_candidate, foreign_resume = isolated_db
    db.add(ResumeOCRResult(resume_id=foreign_resume.id, status="COMPLETED", extracted_data={"skills": ["Python"]}))
    db.commit()

    with pytest.raises(ForbiddenException):
        get_resume_detail(foreign_resume.id, owner_candidate.user, db)
    with pytest.raises(ForbiddenException):
        get_ocr_status(foreign_resume.id, owner_candidate.user, db)
    with pytest.raises(ForbiddenException):
        get_extracted_data(foreign_resume.id, owner_candidate.user, db)
    with pytest.raises(ForbiddenException):
        download_resume(foreign_resume.id, owner_candidate.user, db)


def test_recruiter_resume_access_requires_application_to_owned_job(isolated_db):
    db, _owner_candidate, foreign_resume = isolated_db
    recruiter_user = User(
        email="synthetic-recruiter@example.test",
        hashed_password="unused",
        full_name="Synthetic Recruiter",
        role=UserRole.RECRUITER,
    )
    company = Company(name="Synthetic Applicant Review Co")
    db.add_all([recruiter_user, company])
    db.flush()
    recruiter = Recruiter(user_id=recruiter_user.id, company_id=company.id)
    db.add(recruiter)
    db.flush()
    job = Job(
        recruiter_id=recruiter.id,
        company_id=company.id,
        title="Synthetic Job",
        description="Synthetic application access test.",
        location="Remote",
        status=JobStatusEnum.PUBLISHED,
    )
    db.add(job)
    db.commit()

    with pytest.raises(ForbiddenException):
        _authorize_resume_read(recruiter_user, foreign_resume, db)

    db.add(Application(
        job_id=job.id,
        candidate_id=foreign_resume.candidate_id,
        resume_id=foreign_resume.id,
    ))
    db.commit()
    _authorize_resume_read(recruiter_user, foreign_resume, db)


def test_recruiter_pipeline_resume_links_and_download_for_multiple_applicants(isolated_db, tmp_path):
    db, _owner_candidate, _foreign_resume = isolated_db
    recruiter_user = User(
        email="pipeline-recruiter@example.test",
        hashed_password="unused",
        full_name="Pipeline Recruiter",
        role=UserRole.RECRUITER,
    )
    company = Company(name="Synthetic Resume Review Company")
    db.add_all([recruiter_user, company])
    db.flush()
    recruiter = Recruiter(user_id=recruiter_user.id, company_id=company.id)
    db.add(recruiter)
    db.flush()
    job = Job(
        recruiter_id=recruiter.id,
        company_id=company.id,
        title="Synthetic Resume Review Role",
        description="Synthetic data used only to verify private resume viewing.",
        location="Remote",
        status=JobStatusEnum.PUBLISHED,
    )
    db.add(job)
    db.flush()

    synthetic_applicants = []
    for index, name in enumerate(("Anjali Synthetic", "Deepali Synthetic"), start=1):
        user = User(
            email=f"resume-candidate-{index}@example.test",
            hashed_password="unused",
            full_name=name,
            role=UserRole.CANDIDATE,
        )
        db.add(user)
        db.flush()
        candidate = Candidate(user_id=user.id, profile_percentage=20)
        db.add(candidate)
        db.flush()

        file_path = tmp_path / f"synthetic-{index}.pdf"
        file_path.write_bytes(b"%PDF-1.4 synthetic resume fixture")
        resume = Resume(
            candidate_id=candidate.id,
            file_name=f"synthetic-{index}.pdf",
            original_filename=f"{name}.pdf",
            file_path=str(file_path),
            file_size=file_path.stat().st_size,
            mime_type="application/pdf",
        )
        db.add(resume)
        db.flush()
        application = Application(
            job_id=job.id,
            candidate_id=candidate.id,
            resume_id=resume.id,
        )
        db.add(application)
        synthetic_applicants.append((candidate, resume, file_path))

    db.commit()

    pipeline = get_applicant_pipeline(None, recruiter, db)
    rows = pipeline["APPLIED"]
    assert {row["candidate_name"] for row in rows} == {
        "Anjali Synthetic",
        "Deepali Synthetic",
    }
    for candidate, resume, file_path in synthetic_applicants:
        row = next(item for item in rows if item["candidate_id"] == candidate.id)
        assert row["resume_id"] == resume.id
        assert row["resume_url"] == f"/resumes/{resume.id}/download"
        response = download_resume(resume.id, recruiter_user, db)
        assert response.path == str(file_path)
        assert response.media_type == "application/pdf"

    missing_path = tmp_path / "missing-resume.pdf"
    missing_resume = Resume(
        candidate_id=synthetic_applicants[0][0].id,
        file_name="missing-resume.pdf",
        original_filename="Missing Resume.pdf",
        file_path=str(missing_path),
        file_size=20,
        mime_type="application/pdf",
    )
    missing_job = Job(
        recruiter_id=recruiter.id,
        company_id=company.id,
        title="Synthetic Missing Resume Role",
        description="Synthetic missing-file error test.",
        location="Remote",
        status=JobStatusEnum.PUBLISHED,
    )
    db.add(missing_job)
    db.flush()
    db.add(missing_resume)
    db.flush()
    db.add(Application(
        job_id=missing_job.id,
        candidate_id=synthetic_applicants[0][0].id,
        resume_id=missing_resume.id,
    ))
    db.commit()
    with pytest.raises(NotFoundException, match="Resume file"):
        download_resume(missing_resume.id, recruiter_user, db)

    other_user = User(
        email="another-recruiter@example.test",
        hashed_password="unused",
        full_name="Another Recruiter",
        role=UserRole.RECRUITER,
    )
    db.add(other_user)
    db.flush()
    other_recruiter = Recruiter(user_id=other_user.id)
    db.add(other_recruiter)
    db.commit()

    with pytest.raises(ForbiddenException):
        download_resume(synthetic_applicants[0][1].id, other_user, db)


def test_admin_and_resume_owner_can_read_resume(isolated_db):
    db, owner_candidate, foreign_resume = isolated_db
    admin = User(
        email="synthetic-admin@example.test",
        hashed_password="unused",
        full_name="Synthetic Admin",
        role=UserRole.ADMIN,
    )
    db.add(admin)
    db.commit()

    _authorize_resume_read(admin, foreign_resume, db)
    _authorize_resume_read(foreign_resume.candidate.user, foreign_resume, db)
