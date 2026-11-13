from typing import List, Optional
import datetime
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.dependencies import get_current_user, get_current_candidate
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
    ConflictException,
)
from app.models.user import User, UserRole
from app.models.candidate import Candidate
from app.models.job import Job, JobStatusEnum
from app.models.resume import Resume
from app.models.application import (
    Application,
    ApplicationStatusHistory,
    ApplicationStatusEnum,
)
from app.models.notification import Notification
from app.schemas.application import (
    ApplicationCreate,
    ApplicationResponse,
    StatusHistoryItem,
)
from app.services.matching_service import MatchingService

router = APIRouter(prefix="/applications", tags=["Applications"])

@router.post("/jobs/{job_id}/apply", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def apply_for_job(
    job_id: int,
    req: ApplicationCreate,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Apply for a job with a resume and cover letter.
    Prevents duplicate active applications.
    Computes match analysis upon application.
    """
    # 1. Validate Job
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise NotFoundException("Job")

    if job.status != JobStatusEnum.PUBLISHED:
        raise BadRequestException("This job posting is no longer accepting applications.")

    # 2. Prevent duplicate application
    existing_app = db.query(Application).filter(
        Application.job_id == job_id,
        Application.candidate_id == candidate.id
    ).first()

    if existing_app:
        if existing_app.current_status != ApplicationStatusEnum.WITHDRAWN:
            raise ConflictException("You already have an active application submitted for this position.")
        else:
            # Re-activating withdrawn application
            existing_app.current_status = ApplicationStatusEnum.APPLIED
            existing_app.cover_letter = req.cover_letter
            existing_app.updated_at = datetime.datetime.utcnow()
            app_record = existing_app
    else:
        # 3. Resolve Resume
        resume_id = req.resume_id
        if not resume_id:
            # Find candidate's primary resume
            primary_resume = db.query(Resume).filter(
                Resume.candidate_id == candidate.id,
                Resume.is_primary == True
            ).first()
            if not primary_resume:
                # Find any resume
                primary_resume = db.query(Resume).filter(
                    Resume.candidate_id == candidate.id
                ).order_by(Resume.upload_date.desc()).first()

            if primary_resume:
                resume_id = primary_resume.id

        app_record = Application(
            job_id=job.id,
            candidate_id=candidate.id,
            resume_id=resume_id,
            cover_letter=req.cover_letter,
            current_status=ApplicationStatusEnum.APPLIED
        )
        db.add(app_record)

    db.commit()
    db.refresh(app_record)

    # 4. Status history record
    history = ApplicationStatusHistory(
        application_id=app_record.id,
        status=ApplicationStatusEnum.APPLIED,
        notes="Application submitted by candidate.",
        changed_by_id=current_user.id
    )
    db.add(history)

    # 5. In-app notifications
    cand_notif = Notification(
        user_id=current_user.id,
        title="Application Submitted",
        message=f"You successfully applied for '{job.title}' at {job.company.name if job.company else 'SkillSphere'}.",
        type="APPLICATION",
        link=f"/candidate/applications/{app_record.id}"
    )
    db.add(cand_notif)

    # Recruiter notification
    if job.recruiter and job.recruiter.user_id:
        rec_notif = Notification(
            user_id=job.recruiter.user_id,
            title="New Job Applicant",
            message=f"{current_user.full_name} has applied for '{job.title}'.",
            type="APPLICATION",
            link=f"/recruiter/applicants"
        )
        db.add(rec_notif)

    # Run resume-job match analysis if resume available
    if app_record.resume_id:
        try:
            MatchingService.analyze_resume_for_job(db, app_record.resume_id, job.id)
        except Exception:
            pass

    db.commit()

    return app_record

@router.get("", response_model=List[ApplicationResponse])
def get_my_applications(
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Retrieve all job applications submitted by the logged-in candidate."""
    apps = db.query(Application).filter(
        Application.candidate_id == candidate.id
    ).order_by(Application.applied_at.desc()).all()
    return apps

@router.get("/{app_id}", response_model=ApplicationResponse)
def get_application_detail(
    app_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Get single application details with complete status audit history."""
    app_record = db.query(Application).filter(
        Application.id == app_id,
        Application.candidate_id == candidate.id
    ).first()
    if not app_record:
        raise NotFoundException("Application")
    return app_record

@router.put("/{app_id}/withdraw")
def withdraw_application(
    app_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Withdraw a submitted application."""
    app_record = db.query(Application).filter(
        Application.id == app_id,
        Application.candidate_id == candidate.id
    ).first()
    if not app_record:
        raise NotFoundException("Application")

    if app_record.current_status in [ApplicationStatusEnum.SELECTED, ApplicationStatusEnum.REJECTED]:
        raise BadRequestException(f"Cannot withdraw an application that is already marked {app_record.current_status.value}.")

    app_record.current_status = ApplicationStatusEnum.WITHDRAWN
    history = ApplicationStatusHistory(
        application_id=app_record.id,
        status=ApplicationStatusEnum.WITHDRAWN,
        notes="Application withdrawn by candidate.",
        changed_by_id=current_user.id
    )
    db.add(history)
    db.commit()

    return {"message": "Application withdrawn successfully."}
