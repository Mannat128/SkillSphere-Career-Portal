from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc

from app.database.session import get_db
from app.core.dependencies import get_current_user, get_current_candidate
from app.core.exceptions import NotFoundException, BadRequestException
from app.models.user import User, UserRole
from app.models.candidate import Candidate
from app.models.job import Job, JobSkill, SavedJob, JobStatusEnum
from app.models.recruiter import Company
from app.models.skill import Skill
from app.models.application import Application
from app.schemas.job import JobResponse, JobListResponse

router = APIRouter(prefix="/jobs", tags=["Jobs & Search"])

@router.get("", response_model=JobListResponse)
def search_jobs(
    keyword: Optional[str] = Query(None, description="Search keyword in title or description"),
    location: Optional[str] = Query(None, description="Filter by location"),
    experience_level: Optional[str] = Query(None, description="Filter by experience level"),
    employment_type: Optional[str] = Query(None, description="Filter by employment type"),
    skill: Optional[str] = Query(None, description="Filter by required skill name"),
    sort_by: str = Query("newest", description="Sorting: newest, salary_high, salary_low"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Candidate & Public Job Search:
    Search published jobs with keyword, location, experience, job type, required skills,
    pagination, and sorting.
    """
    query = db.query(Job).filter(Job.status == JobStatusEnum.PUBLISHED)

    # 1. Keyword search
    if keyword and keyword.strip():
        term = f"%{keyword.strip()}%"
        query = query.join(Job.company).filter(
            or_(
                Job.title.ilike(term),
                Job.description.ilike(term),
                Company.name.ilike(term)
            )
        )

    # 2. Location filter
    if location and location.strip():
        query = query.filter(Job.location.ilike(f"%{location.strip()}%"))

    # 3. Experience filter
    if experience_level and experience_level.strip():
        query = query.filter(Job.experience_level.ilike(experience_level.strip()))

    # 4. Employment type filter
    if employment_type and employment_type.strip():
        query = query.filter(Job.employment_type.ilike(employment_type.strip()))

    # 5. Skill filter
    if skill and skill.strip():
        query = query.join(Job.required_skills).join(JobSkill.skill).filter(
            Skill.name.ilike(skill.strip())
        )

    # Total count
    total = query.distinct().count()

    # Sorting
    if sort_by == "salary_high":
        query = query.order_by(desc(Job.max_salary))
    elif sort_by == "salary_low":
        query = query.order_by(asc(Job.min_salary))
    else:
        query = query.order_by(desc(Job.created_at))

    # Pagination
    offset = (page - 1) * page_size
    jobs = query.distinct().offset(offset).limit(page_size).all()
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = []
    for j in jobs:
        skill_names = [js.skill.name for js in j.required_skills if js.skill]
        items.append({
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

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }

@router.get("/saved", response_model=List[JobResponse])
@router.get("/saved/all", response_model=List[JobResponse])
def get_saved_jobs(
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Retrieve all bookmarked jobs for the current candidate."""
    saved = db.query(SavedJob).filter(SavedJob.candidate_id == candidate.id).all()
    results = []
    for s in saved:
        j = s.job
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
            "total_applicants": len(j.applications),
            "is_saved": True
        })
    return results

@router.get("/{job_id}", response_model=JobResponse)
def get_job_detail(
    job_id: int,
    db: Session = Depends(get_db)
):
    """View full job description and requirements."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise NotFoundException("Job")

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

@router.post("/{job_id}/save")
def bookmark_job(
    job_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Save / bookmark a job to candidate's wishlist."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise NotFoundException("Job")

    existing = db.query(SavedJob).filter(
        SavedJob.candidate_id == candidate.id,
        SavedJob.job_id == job_id
    ).first()

    if not existing:
        saved = SavedJob(candidate_id=candidate.id, job_id=job_id)
        db.add(saved)
        db.commit()

    return {"message": "Job bookmarked successfully"}

@router.delete("/{job_id}/save")
def remove_bookmark(
    job_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Remove bookmark from candidate's saved jobs."""
    saved = db.query(SavedJob).filter(
        SavedJob.candidate_id == candidate.id,
        SavedJob.job_id == job_id
    ).first()

    if saved:
        db.delete(saved)
        db.commit()

    return {"message": "Job bookmark removed"}
