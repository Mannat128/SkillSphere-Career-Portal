from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.dependencies import get_current_user, get_current_candidate
from app.core.exceptions import NotFoundException, BadRequestException
from app.models.resume import Resume, ResumeAnalysis
from app.models.job import Job
from app.schemas.resume import (
    ResumeAnalysisResponse,
    MultiJobMatchRequest,
    MultiJobMatchResponse,
)
from app.services.matching_service import MatchingService

router = APIRouter(prefix="/resume-analysis", tags=["Resume Matching & Skill Gap Analysis"])

@router.post("/analyze", response_model=ResumeAnalysisResponse)
def analyze_resume(
    resume_id: int,
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    Step 9 & Section 7.A:
    Compare candidate skills against job required skills, calculate transparent match percentage,
    matched skills, missing skills, and targeted improvement suggestions.
    """
    try:
        result = MatchingService.analyze_resume_for_job(db, resume_id, job_id)
        return result
    except ValueError as e:
        raise NotFoundException(str(e))

@router.get("", response_model=List[ResumeAnalysisResponse])
def get_analyses_for_candidate(
    candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """List all previous resume-job analyses for the candidate."""
    analyses = db.query(ResumeAnalysis).join(Resume).filter(
        Resume.candidate_id == candidate.id
    ).order_by(ResumeAnalysis.created_at.desc()).all()

    results = []
    for a in analyses:
        results.append({
            "id": a.id,
            "resume_id": a.resume_id,
            "job_id": a.job_id,
            "job_title": a.job.title if a.job else "Unknown Job",
            "company_name": a.job.company.name if (a.job and a.job.company) else "Partner",
            "match_score": a.match_score,
            "matched_skills": a.matched_skills,
            "missing_skills": a.missing_skills,
            "recommendations": a.recommendations,
            "explanation": a.explanation
        })
    return results

@router.post("/compare-multi", response_model=MultiJobMatchResponse)
def compare_multi_jobs(
    req: MultiJobMatchRequest,
    db: Session = Depends(get_db)
):
    """
    Section 7.D:
    Multi-Job Resume Comparison:
    Compare a single resume across multiple active job postings to help the candidate
    identify the best-fitting opportunities.
    """
    resume = db.query(Resume).filter(Resume.id == req.resume_id).first()
    if not resume:
        raise NotFoundException("Resume")

    comparisons = []
    for job_id in req.job_ids:
        try:
            analysis = MatchingService.analyze_resume_for_job(db, req.resume_id, job_id)
            comparisons.append(analysis)
        except Exception:
            continue

    # Sort descending by match score
    comparisons.sort(key=lambda x: x["match_score"], reverse=True)

    return {
        "resume_id": req.resume_id,
        "comparisons": comparisons
    }
