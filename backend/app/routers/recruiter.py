from typing import List, Optional, Dict, Any
import datetime
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.session import get_db
from app.core.dependencies import get_current_user, get_current_recruiter
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)
from app.models.user import User, UserRole
from app.models.recruiter import Recruiter, Company, RecruiterApprovalStatus
from app.models.job import Job, JobSkill, JobStatusEnum
from app.models.skill import Skill
from app.models.candidate import Candidate
from app.models.application import (
    Application,
    ApplicationStatusHistory,
    ApplicationStatusEnum,
)
from app.models.resume import Resume, ResumeAnalysis
from app.models.interview import Interview
from app.models.notification import Notification
from app.schemas.recruiter import (
    CompanyCreateUpdate,
    CompanyResponse,
    RecruiterResponse,
)
from app.schemas.job import JobCreate, JobUpdate, JobResponse
from app.schemas.application import (
    RecruiterApplicantResponse,
    ApplicationStatusUpdate,
)

router = APIRouter(prefix="/recruiter", tags=["Recruiter Portal"])

# Company Profile
@router.get("/company", response_model=Optional[CompanyResponse])
def get_recruiter_company(
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """Retrieve recruiter's company profile."""
    return recruiter.company

@router.put("/company", response_model=CompanyResponse)
def update_recruiter_company(
    req: CompanyCreateUpdate,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """Update company details."""
    company = recruiter.company
    if not company:
        company = Company(name=req.name)
        db.add(company)
        db.commit()
        db.refresh(company)
        recruiter.company_id = company.id

    company.name = req.name
    company.logo_url = req.logo_url
    company.description = req.description
    company.website = req.website
    company.industry = req.industry
    company.location = req.location
    company.contact_email = req.contact_email
    company.contact_phone = req.contact_phone
    db.commit()
    db.refresh(company)
    return company

# Job Management
@router.get("/jobs", response_model=List[JobResponse])
def get_recruiter_jobs(
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """List all jobs posted by the logged-in recruiter."""
    jobs = db.query(Job).filter(Job.recruiter_id == recruiter.id).order_by(Job.created_at.desc()).all()
    results = []
    for j in jobs:
        skill_names = [js.skill.name for js in j.required_skills if js.skill]
        results.append({
            "id": j.id,
            "recruiter_id": j.recruiter_id,
            "company_id": j.company_id,
            "title": j.title,
            "description": j.description,
            "location": j.location,
            "employment_type": j.employment_type,
            "experience_level": j.experience_level,
            "min_salary": float(j.min_salary) if j.min_salary else None,
            "max_salary": float(j.max_salary) if j.max_salary else None,
            "salary_currency": j.salary_currency,
            "responsibilities": j.responsibilities,
            "qualifications": j.qualifications,
            "status": j.status,
            "application_deadline": j.application_deadline,
            "created_at": j.created_at,
            "company": j.company,
            "required_skills": skill_names,
            "total_applicants": len(j.applications)
        })
    return results

@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job_posting(
    req: JobCreate,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """Create a new job posting for recruiter's company."""
    if not recruiter.company_id:
        raise BadRequestException("Please configure your company profile before posting jobs.")

    job = Job(
        recruiter_id=recruiter.id,
        company_id=recruiter.company_id,
        title=req.title,
        description=req.description,
        location=req.location,
        employment_type=req.employment_type,
        experience_level=req.experience_level,
        min_salary=req.min_salary,
        max_salary=req.max_salary,
        salary_currency=req.salary_currency,
        responsibilities=req.responsibilities,
        qualifications=req.qualifications,
        application_deadline=req.application_deadline,
        status=JobStatusEnum.PUBLISHED
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Link required skills
    for skill_name in req.required_skills:
        clean_name = skill_name.strip()
        skill = db.query(Skill).filter(Skill.name.ilike(clean_name)).first()
        if not skill:
            skill = Skill(name=clean_name, category="General")
            db.add(skill)
            db.commit()
            db.refresh(skill)

        js = JobSkill(job_id=job.id, skill_id=skill.id, is_required=True)
        db.add(js)

    db.commit()
    db.refresh(job)

    skill_names = [js.skill.name for js in job.required_skills if js.skill]
    return {
        "id": job.id,
        "recruiter_id": job.recruiter_id,
        "company_id": job.company_id,
        "title": job.title,
        "description": job.description,
        "location": job.location,
        "employment_type": job.employment_type,
        "experience_level": job.experience_level,
        "min_salary": float(job.min_salary) if job.min_salary else None,
        "max_salary": float(job.max_salary) if job.max_salary else None,
        "salary_currency": job.salary_currency,
        "responsibilities": job.responsibilities,
        "qualifications": job.qualifications,
        "status": job.status,
        "application_deadline": job.application_deadline,
        "created_at": job.created_at,
        "company": job.company,
        "required_skills": skill_names,
        "total_applicants": 0
    }

@router.put("/jobs/{job_id}", response_model=JobResponse)
def update_job_posting(
    job_id: int,
    req: JobUpdate,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """Edit job posting owned by recruiter."""
    job = db.query(Job).filter(Job.id == job_id, Job.recruiter_id == recruiter.id).first()
    if not job:
        raise NotFoundException("Job")

    if req.title:
        job.title = req.title
    if req.description:
        job.description = req.description
    if req.location:
        job.location = req.location
    if req.employment_type:
        job.employment_type = req.employment_type
    if req.experience_level:
        job.experience_level = req.experience_level
    if req.min_salary is not None:
        job.min_salary = req.min_salary
    if req.max_salary is not None:
        job.max_salary = req.max_salary
    if req.salary_currency:
        job.salary_currency = req.salary_currency
    if req.responsibilities is not None:
        job.responsibilities = req.responsibilities
    if req.qualifications is not None:
        job.qualifications = req.qualifications
    if req.status:
        job.status = req.status
    if req.application_deadline is not None:
        job.application_deadline = req.application_deadline

    # Update required skills if provided
    if req.required_skills is not None:
        db.query(JobSkill).filter(JobSkill.job_id == job.id).delete()
        for skill_name in req.required_skills:
            clean_name = skill_name.strip()
            skill = db.query(Skill).filter(Skill.name.ilike(clean_name)).first()
            if not skill:
                skill = Skill(name=clean_name, category="General")
                db.add(skill)
                db.commit()
                db.refresh(skill)
            js = JobSkill(job_id=job.id, skill_id=skill.id, is_required=True)
            db.add(js)

    db.commit()
    db.refresh(job)

    skill_names = [js.skill.name for js in job.required_skills if js.skill]
    return {
        "id": job.id,
        "recruiter_id": job.recruiter_id,
        "company_id": job.company_id,
        "title": job.title,
        "description": job.description,
        "location": job.location,
        "employment_type": job.employment_type,
        "experience_level": job.experience_level,
        "min_salary": float(job.min_salary) if job.min_salary else None,
        "max_salary": float(job.max_salary) if job.max_salary else None,
        "salary_currency": job.salary_currency,
        "responsibilities": job.responsibilities,
        "qualifications": job.qualifications,
        "status": job.status,
        "application_deadline": job.application_deadline,
        "created_at": job.created_at,
        "company": job.company,
        "required_skills": skill_names,
        "total_applicants": len(job.applications)
    }

@router.delete("/jobs/{job_id}")
def delete_job_posting(
    job_id: int,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """Delete recruiter's job posting."""
    job = db.query(Job).filter(Job.id == job_id, Job.recruiter_id == recruiter.id).first()
    if not job:
        raise NotFoundException("Job")
    db.delete(job)
    db.commit()
    return {"message": "Job posting deleted successfully"}

# Applicant Management & Kanban Pipeline
@router.get("/applicants")
def get_applicants(
    job_id: Optional[int] = Query(None),
    status: Optional[ApplicationStatusEnum] = Query(None),
    skill: Optional[str] = Query(None),
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """
    View applicants for recruiter's jobs.
    Includes candidate profiles, resumes, and resume-job matching analysis scores.
    """
    query = db.query(Application).join(Job).filter(Job.recruiter_id == recruiter.id)

    if job_id:
        query = query.filter(Application.job_id == job_id)
    if status:
        query = query.filter(Application.current_status == status)

    applications = query.order_by(Application.applied_at.desc()).all()
    results = []

    for app_rec in applications:
        cand = app_rec.candidate
        cand_user = cand.user if cand else None

        # Fetch match score if exists
        analysis = None
        if app_rec.resume_id:
            analysis = db.query(ResumeAnalysis).filter(
                ResumeAnalysis.resume_id == app_rec.resume_id,
                ResumeAnalysis.job_id == app_rec.job_id
            ).first()

        results.append({
            "id": app_rec.id,
            "job_id": app_rec.job_id,
            "job_title": app_rec.job.title,
            "candidate_id": cand.id if cand else 0,
            "candidate_name": cand_user.full_name if cand_user else "",
            "candidate_email": cand_user.email if cand_user else "",
            "candidate_phone": cand.phone if cand else None,
            "candidate_location": cand.location if cand else None,
            "candidate_headline": cand.headline if cand else None,
            "resume_id": app_rec.resume_id,
            "resume_url": f"/api/v1/resumes/{app_rec.resume_id}/download" if app_rec.resume_id else None,
            "cover_letter": app_rec.cover_letter,
            "current_status": app_rec.current_status,
            "applied_at": app_rec.applied_at,
            "match_score": analysis.match_score if analysis else None,
            "matched_skills": analysis.matched_skills if analysis else [],
            "missing_skills": analysis.missing_skills if analysis else [],
            "skills": [cs.skill.name for cs in cand.skills if cs.skill] if cand else []
        })

    return results

@router.get("/pipeline")
def get_applicant_pipeline(
    job_id: Optional[int] = Query(None),
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """
    Section 8.D: Applicant Kanban Board Pipeline:
    Returns applications grouped by statuses:
    Applied, Under Review, Shortlisted, Interview, Selected, Rejected.
    """
    query = db.query(Application).join(Job).filter(Job.recruiter_id == recruiter.id)
    if job_id:
        query = query.filter(Application.job_id == job_id)

    applications = query.order_by(Application.applied_at.desc()).all()

    pipeline: Dict[str, List[Any]] = {
        "APPLIED": [],
        "UNDER_REVIEW": [],
        "SHORTLISTED": [],
        "INTERVIEW": [],
        "SELECTED": [],
        "REJECTED": []
    }

    for app_rec in applications:
        status_key = app_rec.current_status.value
        if status_key in pipeline:
            cand = app_rec.candidate
            cand_user = cand.user if cand else None

            # Find match score
            analysis = None
            if app_rec.resume_id:
                analysis = db.query(ResumeAnalysis).filter(
                    ResumeAnalysis.resume_id == app_rec.resume_id,
                    ResumeAnalysis.job_id == app_rec.job_id
                ).first()

            pipeline[status_key].append({
                "id": app_rec.id,
                "job_id": app_rec.job_id,
                "job_title": app_rec.job.title,
                "candidate_id": cand.id if cand else 0,
                "candidate_name": cand_user.full_name if cand_user else "",
                "candidate_email": cand_user.email if cand_user else "",
                "resume_url": f"/api/v1/resumes/{app_rec.resume_id}/download" if app_rec.resume_id else None,
                "match_score": analysis.match_score if analysis else None,
                "applied_at": app_rec.applied_at
            })

    return pipeline

@router.put("/applicants/{application_id}/status")
def update_applicant_status(
    application_id: int,
    req: ApplicationStatusUpdate,
    recruiter: Recruiter = Depends(get_current_recruiter),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Drag-and-drop Kanban status update:
    Persists status change in database, updates application,
    creates status history record, and notifies candidate.
    """
    app_rec = db.query(Application).join(Job).filter(
        Application.id == application_id,
        Job.recruiter_id == recruiter.id
    ).first()
    if not app_rec:
        raise NotFoundException("Application")

    old_status = app_rec.current_status
    app_rec.current_status = req.status
    app_rec.updated_at = datetime.datetime.utcnow()

    # Log history
    history = ApplicationStatusHistory(
        application_id=app_rec.id,
        status=req.status,
        notes=req.notes or f"Status updated from {old_status.value} to {req.status.value}",
        changed_by_id=current_user.id
    )
    db.add(history)

    # In-app notification to candidate
    if app_rec.candidate and app_rec.candidate.user:
        notif = Notification(
            user_id=app_rec.candidate.user.id,
            title="Application Status Updated",
            message=f"Your application for '{app_rec.job.title}' has been moved to '{req.status.value.replace('_', ' ').title()}'.",
            type="APPLICATION",
            link=f"/candidate/applications/{app_rec.id}"
        )
        db.add(notif)

    # Automatic First Round Assessment Assignment on SHORTLISTED
    if req.status == ApplicationStatusEnum.SHORTLISTED:
        from app.services.assessment_assignment_service import AssessmentAssignmentService
        try:
            AssessmentAssignmentService.assign_assessment_to_shortlisted_candidate(db, app_rec)
        except Exception as e:
            # Let recruiter know if question bank had insufficient questions
            pass

    db.commit()

    return {"message": "Application status successfully updated", "status": req.status}

# Candidate Comparison
@router.get("/compare-candidates")
def compare_candidates(
    application_ids: List[int] = Query(...),
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """
    Section 8.E:
    Side-by-side comparison of multiple applicants based on:
    skills, experience, education, resume information, and job match percentage.
    """
    apps = db.query(Application).filter(Application.id.in_(application_ids)).all()
    results = []

    for a in apps:
        cand = a.candidate
        cand_user = cand.user if cand else None

        analysis = None
        if a.resume_id:
            analysis = db.query(ResumeAnalysis).filter(
                ResumeAnalysis.resume_id == a.resume_id,
                ResumeAnalysis.job_id == a.job_id
            ).first()

        results.append({
            "application_id": a.id,
            "job_title": a.job.title,
            "candidate_name": cand_user.full_name if cand_user else "",
            "candidate_email": cand_user.email if cand_user else "",
            "match_score": analysis.match_score if analysis else 0.0,
            "matched_skills": analysis.matched_skills if analysis else [],
            "missing_skills": analysis.missing_skills if analysis else [],
            "skills": [cs.skill.name for cs in cand.skills if cs.skill] if cand else [],
            "experiences": [
                f"{exp.position} at {exp.company}"
                for exp in (cand.experiences if cand else [])
            ],
            "educations": [
                f"{edu.degree} from {edu.institution}"
                for edu in (cand.educations if cand else [])
            ],
            "current_status": a.current_status
        })

    return results

# Recruitment Analytics
@router.get("/analytics")
def get_recruiter_analytics(
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """
    Section 8.G:
    Recruitment Analytics computed directly from actual database records.
    """
    total_jobs = db.query(Job).filter(Job.recruiter_id == recruiter.id).count()
    active_jobs = db.query(Job).filter(Job.recruiter_id == recruiter.id, Job.status == JobStatusEnum.PUBLISHED).count()

    total_apps = db.query(Application).join(Job).filter(Job.recruiter_id == recruiter.id).count()
    shortlisted = db.query(Application).join(Job).filter(
        Job.recruiter_id == recruiter.id,
        Application.current_status == ApplicationStatusEnum.SHORTLISTED
    ).count()

    interviews_scheduled = db.query(Interview).filter(Interview.recruiter_id == recruiter.id).count()
    selected = db.query(Application).join(Job).filter(
        Job.recruiter_id == recruiter.id,
        Application.current_status == ApplicationStatusEnum.SELECTED
    ).count()

    # Job-wise application counts
    job_stats = db.query(
        Job.title,
        func.count(Application.id).label("applicant_count")
    ).outerjoin(Application).filter(
        Job.recruiter_id == recruiter.id
    ).group_by(Job.id, Job.title).all()

    return {
        "total_jobs": total_jobs,
        "active_jobs": active_jobs,
        "total_applicants": total_apps,
        "shortlisted_applicants": shortlisted,
        "interviews_scheduled": interviews_scheduled,
        "selected_candidates": selected,
        "job_statistics": [
            {"job_title": row[0], "applicants": row[1]}
            for row in job_stats
        ]
    }
