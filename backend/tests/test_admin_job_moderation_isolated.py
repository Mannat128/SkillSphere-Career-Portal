import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.core.exceptions import ForbiddenException
from app.database.base import Base
from app.models import Company, Job, JobStatusEnum, Recruiter, User, UserRole
from app.models.audit import AuditLog
from app.routers import admin


@pytest.fixture
def moderation_data(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = Session(engine)

    # Approval must not dispatch email or create unrelated alert records in tests.
    from app.services.job_alert_service import JobAlertService

    monkeypatch.setattr(
        JobAlertService,
        "dispatch_job_alerts",
        classmethod(lambda cls, db, job: {"dispatched": 0}),
    )

    company = Company(name="Synthetic Moderation Co")
    admin_user = User(
        email="synthetic-admin@example.test",
        full_name="Synthetic Admin",
        hashed_password="unused-test-hash",
        role=UserRole.ADMIN,
        is_active=True,
    )
    recruiter_user = User(
        email="synthetic-recruiter@example.test",
        full_name="Synthetic Recruiter",
        hashed_password="unused-test-hash",
        role=UserRole.RECRUITER,
        is_active=True,
    )
    db.add_all([company, admin_user, recruiter_user])
    db.flush()
    recruiter = Recruiter(user_id=recruiter_user.id, company_id=company.id)
    db.add(recruiter)
    db.flush()
    job = Job(
        recruiter_id=recruiter.id,
        company_id=company.id,
        title="Synthetic QA Engineer",
        description="Synthetic job used only by isolated tests.",
        location="Remote",
        employment_type="Full-time",
        experience_level="Mid-Level",
        status=JobStatusEnum.MODERATION_PENDING,
    )
    db.add(job)
    db.commit()

    yield {"db": db, "admin": admin_user, "recruiter": recruiter_user, "job": job}
    db.close()
    engine.dispose()


def test_admin_approval_publishes_job_removes_from_pending_and_audits(moderation_data):
    db, admin_user, job = (
        moderation_data["db"], moderation_data["admin"], moderation_data["job"]
    )
    request = admin.JobModerationRequest(new_status=JobStatusEnum.PUBLISHED)

    response = admin.moderate_job(job.id, request, admin_user, db)

    assert response["new_status"] == "PUBLISHED"
    assert job.status == JobStatusEnum.PUBLISHED
    pending = admin.get_all_jobs_moderation(
        status=JobStatusEnum.MODERATION_PENDING, admin_user=admin_user, db=db
    )
    assert all(item["id"] != job.id for item in pending)
    audit = db.query(AuditLog).filter_by(
        action="JOB_MODERATED", entity_id=job.id
    ).one()
    assert audit.details["previous_status"] == "MODERATION_PENDING"
    assert audit.details["new_status"] == "PUBLISHED"


def test_rejection_requires_reason_and_records_reason(moderation_data):
    db, admin_user, job = (
        moderation_data["db"], moderation_data["admin"], moderation_data["job"]
    )
    with pytest.raises(Exception) as missing_reason:
        admin.moderate_job(
            job.id,
            admin.JobModerationRequest(new_status=JobStatusEnum.MODERATION_REJECTED),
            admin_user,
            db,
        )
    assert getattr(missing_reason.value, "status_code", None) == 400

    response = admin.moderate_job(
        job.id,
        admin.JobModerationRequest(
            new_status=JobStatusEnum.MODERATION_REJECTED,
            notes="Synthetic rejection reason",
        ),
        admin_user,
        db,
    )
    assert response["new_status"] == "MODERATION_REJECTED"
    assert job.status == JobStatusEnum.MODERATION_REJECTED
    assert job.moderation_notes == "Synthetic rejection reason"


def test_non_admin_is_denied_and_invalid_payload_has_validation_details(moderation_data):
    admin_checker = require_role(UserRole.ADMIN)
    with pytest.raises(ForbiddenException):
        admin_checker(moderation_data["recruiter"])

    with pytest.raises(ValidationError) as error:
        admin.JobModerationRequest(new_status="NOT_A_VALID_STATUS")
    assert error.value.errors()
