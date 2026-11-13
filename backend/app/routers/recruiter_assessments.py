from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.session import get_db
from app.core.dependencies import get_current_user, get_current_recruiter
from app.core.exceptions import NotFoundException, BadRequestException, ForbiddenException
from app.models.user import User, UserRole
from app.models.recruiter import Recruiter
from app.models.job import Job
from app.models.recruiter_assessment import (
    JobAssessment,
    QuestionBankQuestion,
    AssessmentAssignment,
    CandidateAssessmentResult,
)
from app.schemas.recruiter_assessment import (
    JobAssessmentConfigCreate,
    JobAssessmentConfigResponse,
    RecruiterAssessmentResultItem,
)
from app.services.assessment_assignment_service import AssessmentAssignmentService

router = APIRouter(tags=["Recruiter First Round Assessment"])

@router.get("/jobs/{job_id}/assessment", response_model=Optional[JobAssessmentConfigResponse])
def get_job_assessment_config(
    job_id: int,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """Retrieve First Round Assessment Configuration for a job."""
    job = db.query(Job).filter(Job.id == job_id, Job.recruiter_id == recruiter.id).first()
    if not job:
        raise NotFoundException("Job")

    config = db.query(JobAssessment).filter(JobAssessment.job_id == job_id).first()
    if not config:
        return None

    # Calculate available eligible questions
    pool = AssessmentAssignmentService.get_eligible_questions(
        db,
        recruiter_id=recruiter.id,
        categories=config.categories,
        job_id=job_id
    )

    return {
        "id": config.id,
        "job_id": config.job_id,
        "is_enabled": config.is_enabled,
        "title": config.title,
        "instructions": config.instructions,
        "total_questions": config.total_questions,
        "duration_minutes": config.duration_minutes,
        "total_marks": config.total_marks,
        "passing_marks": config.passing_marks,
        "qualification_rule": config.qualification_rule,
        "negative_marking": config.negative_marking,
        "negative_marks": config.negative_marks,
        "categories": config.categories or [],
        "difficulty_distribution": config.difficulty_distribution,
        "selection_mode": config.selection_mode,
        "selected_question_ids": config.selected_question_ids,
        "eligible_questions_count": len(pool)
    }

@router.post("/jobs/{job_id}/assessment", response_model=JobAssessmentConfigResponse)
def save_job_assessment_config(
    job_id: int,
    req: JobAssessmentConfigCreate,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """
    Save or update First Round Assessment Configuration for a job:
    Supports:
    1. Add Manually (explicit questions)
    2. Bulk Uploaded questions
    3. Select from Question Bank (or Random selection with difficulty distribution)
    Validates passing criteria, question count, and question availability.
    """
    job = db.query(Job).filter(Job.id == job_id, Job.recruiter_id == recruiter.id).first()
    if not job:
        raise NotFoundException("Job")

    # Validation
    if req.is_enabled:
        if req.passing_marks > req.total_marks:
            raise BadRequestException(f"Passing marks ({req.passing_marks}) cannot exceed total marks ({req.total_marks}).")

        if req.qualification_rule not in [">", ">="]:
            raise BadRequestException("Qualification rule must be '>' or '>='.")

        if req.selection_mode == "SPECIFIC":
            if not req.selected_question_ids or len(req.selected_question_ids) < req.total_questions:
                raise BadRequestException(
                    f"Please select at least {req.total_questions} questions from the Question Bank."
                )
        else:
            # Check pool availability
            pool = AssessmentAssignmentService.get_eligible_questions(
                db,
                recruiter_id=recruiter.id,
                categories=req.categories,
                job_id=job_id
            )
            if len(pool) < req.total_questions:
                raise BadRequestException(
                    f"Insufficient questions in Question Bank. You configured {req.total_questions} questions, but only {len(pool)} are available."
                )

            if req.difficulty_distribution:
                sum_dist = sum(req.difficulty_distribution.values())
                if sum_dist != req.total_questions:
                    raise BadRequestException(
                        f"Difficulty distribution total ({sum_dist}) does not match configured question count ({req.total_questions})."
                    )

    config = db.query(JobAssessment).filter(JobAssessment.job_id == job_id).first()
    if not config:
        config = JobAssessment(job_id=job_id)
        db.add(config)

    config.is_enabled = req.is_enabled
    config.title = req.title
    config.instructions = req.instructions
    config.total_questions = req.total_questions
    config.duration_minutes = req.duration_minutes
    config.total_marks = req.total_marks
    config.passing_marks = req.passing_marks
    config.qualification_rule = req.qualification_rule
    config.negative_marking = req.negative_marking
    config.negative_marks = req.negative_marks
    config.categories = req.categories
    config.difficulty_distribution = req.difficulty_distribution
    config.selection_mode = req.selection_mode
    config.selected_question_ids = req.selected_question_ids

    db.commit()
    db.refresh(config)

    pool = AssessmentAssignmentService.get_eligible_questions(
        db,
        recruiter_id=recruiter.id,
        categories=config.categories,
        job_id=job_id
    )

    return {
        "id": config.id,
        "job_id": config.job_id,
        "is_enabled": config.is_enabled,
        "title": config.title,
        "instructions": config.instructions,
        "total_questions": config.total_questions,
        "duration_minutes": config.duration_minutes,
        "total_marks": config.total_marks,
        "passing_marks": config.passing_marks,
        "qualification_rule": config.qualification_rule,
        "negative_marking": config.negative_marking,
        "negative_marks": config.negative_marks,
        "categories": config.categories or [],
        "difficulty_distribution": config.difficulty_distribution,
        "selection_mode": config.selection_mode,
        "selected_question_ids": config.selected_question_ids,
        "eligible_questions_count": len(pool)
    }

@router.get("/jobs/{job_id}/assessment/preview")
def preview_job_assessment(
    job_id: int,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """Preview assessment configuration and eligible questions before publishing."""
    job = db.query(Job).filter(Job.id == job_id, Job.recruiter_id == recruiter.id).first()
    if not job or not job.assessment_config:
        raise NotFoundException("Assessment Configuration")

    config = job.assessment_config
    pool = AssessmentAssignmentService.get_eligible_questions(
        db,
        recruiter_id=recruiter.id,
        categories=config.categories,
        job_id=job_id
    )

    sample_questions = pool[:config.total_questions] if pool else []

    return {
        "title": config.title,
        "is_enabled": config.is_enabled,
        "total_questions": config.total_questions,
        "duration_minutes": config.duration_minutes,
        "total_marks": config.total_marks,
        "passing_marks": config.passing_marks,
        "qualification_rule": config.qualification_rule,
        "negative_marking": config.negative_marking,
        "negative_marks": config.negative_marks,
        "categories": config.categories or [],
        "eligible_count": len(pool),
        "sample_questions": [
            {
                "id": q.id,
                "question_text": q.question_text,
                "category": q.category,
                "difficulty": q.difficulty,
                "marks": q.marks,
                "option_a": q.option_a,
                "option_b": q.option_b,
                "option_c": q.option_c,
                "option_d": q.option_d
            }
            for q in sample_questions
        ]
    }

# --- Recruiter Results Dashboard ---

@router.get("/recruiter/assessments/results", response_model=List[RecruiterAssessmentResultItem])
def get_recruiter_assessment_results(
    job_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, description="qualified, not_qualified"),
    search: Optional[str] = Query(None),
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """
    Section 13: Recruiter Assessment Results Dashboard.
    Recruiter views assessment scorecards for their own jobs only.
    """
    query = db.query(CandidateAssessmentResult).join(Job).filter(Job.recruiter_id == recruiter.id)

    if job_id:
        query = query.filter(CandidateAssessmentResult.job_id == job_id)

    if status_filter == "qualified":
        query = query.filter(CandidateAssessmentResult.is_qualified == True)
    elif status_filter == "not_qualified":
        query = query.filter(CandidateAssessmentResult.is_qualified == False)

    results = query.order_by(desc(CandidateAssessmentResult.evaluated_at)).all()
    output = []

    for r in results:
        cand = r.candidate
        cand_user = cand.user if cand else None
        job = r.job
        assignment = r.assignment

        if search and search.strip():
            term = search.strip().lower()
            cand_name = cand_user.full_name.lower() if cand_user else ""
            cand_email = cand_user.email.lower() if cand_user else ""
            if term not in cand_name and term not in cand_email:
                continue

        output.append({
            "id": r.id,
            "candidate_id": r.candidate_id,
            "candidate_name": cand_user.full_name if cand_user else "Candidate",
            "candidate_email": cand_user.email if cand_user else "",
            "job_id": r.job_id,
            "job_title": job.title if job else "",
            "assessment_title": assignment.config_snapshot.get("title", "Assessment") if assignment else "Assessment",
            "obtained_marks": r.obtained_marks,
            "total_marks": r.total_marks,
            "percentage": r.percentage,
            "correct_count": r.correct_count,
            "incorrect_count": r.incorrect_count,
            "unanswered_count": r.unanswered_count,
            "passing_marks": r.passing_marks,
            "qualification_rule": r.qualification_rule,
            "is_qualified": r.is_qualified,
            "time_taken_seconds": r.attempt.time_taken_seconds if r.attempt else 0,
            "evaluated_at": r.evaluated_at,
            "question_breakdown": r.question_breakdown
        })

    return output

@router.get("/recruiter/assessments/results/{result_id}")
def get_recruiter_result_detail(
    result_id: int,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """View detailed candidate scorecard with question breakdown."""
    r = db.query(CandidateAssessmentResult).join(Job).filter(
        CandidateAssessmentResult.id == result_id,
        Job.recruiter_id == recruiter.id
    ).first()
    if not r:
        raise NotFoundException("Assessment Result")

    cand_user = r.candidate.user if r.candidate else None
    return {
        "id": r.id,
        "candidate_id": r.candidate_id,
        "candidate_name": cand_user.full_name if cand_user else "",
        "candidate_email": cand_user.email if cand_user else "",
        "job_title": r.job.title if r.job else "",
        "assessment_title": r.assignment.config_snapshot.get("title") if r.assignment else "",
        "obtained_marks": r.obtained_marks,
        "total_marks": r.total_marks,
        "percentage": r.percentage,
        "correct_count": r.correct_count,
        "incorrect_count": r.incorrect_count,
        "unanswered_count": r.unanswered_count,
        "passing_marks": r.passing_marks,
        "qualification_rule": r.qualification_rule,
        "is_qualified": r.is_qualified,
        "qualification_message": r.qualification_message,
        "time_taken_seconds": r.attempt.time_taken_seconds if r.attempt else 0,
        "evaluated_at": r.evaluated_at,
        "question_breakdown": r.question_breakdown
    }
