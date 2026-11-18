
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.session import get_db
from app.core.dependencies import get_current_recruiter
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
)
from app.models.recruiter import Recruiter
from app.models.job import Job
from app.models.proctoring import ProctoringSession
from app.models.recruiter_assessment import (
    JobAssessment,
    CandidateAssessmentResult,
)
from app.schemas.recruiter_assessment import (
    JobAssessmentConfigCreate,
    JobAssessmentConfigResponse,
    RecruiterAssessmentResultItem,
)
from app.services.assessment_assignment_service import AssessmentAssignmentService


router = APIRouter(tags=["Recruiter First Round Assessment"])


# ---------------------------------------------------------
# GET JOB ASSESSMENT CONFIGURATION
# ---------------------------------------------------------

@router.get(
    "/jobs/{job_id}/assessment",
    response_model=Optional[JobAssessmentConfigResponse],
)
def get_job_assessment_config(
    job_id: int,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db),
):
    job = (
        db.query(Job)
        .filter(
            Job.id == job_id,
            Job.recruiter_id == recruiter.id,
        )
        .first()
    )

    if not job:
        raise NotFoundException("Job")

    config = (
        db.query(JobAssessment)
        .filter(JobAssessment.job_id == job_id)
        .first()
    )

    if not config:
        return None

    pool = AssessmentAssignmentService.get_eligible_questions(
        db,
        recruiter_id=recruiter.id,
        categories=config.categories,
        job_id=job_id,
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
        "qualification_rule": ">",
        "negative_marking": config.negative_marking,
        "negative_marks": config.negative_marks,
        "categories": config.categories or [],
        "difficulty_distribution": config.difficulty_distribution,
        "selection_mode": config.selection_mode,
        "selected_question_ids": config.selected_question_ids,
        "eligible_questions_count": len(pool),
    }


# ---------------------------------------------------------
# CREATE / UPDATE JOB ASSESSMENT CONFIGURATION
# ---------------------------------------------------------

@router.post(
    "/jobs/{job_id}/assessment",
    response_model=JobAssessmentConfigResponse,
)
def save_job_assessment_config(
    job_id: int,
    req: JobAssessmentConfigCreate,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db),
):
    job = (
        db.query(Job)
        .filter(
            Job.id == job_id,
            Job.recruiter_id == recruiter.id,
        )
        .first()
    )

    if not job:
        raise NotFoundException("Job")

    if req.is_enabled:
        if req.passing_marks > req.total_marks:
            raise BadRequestException(
                f"Passing marks ({req.passing_marks}) cannot exceed "
                f"total marks ({req.total_marks})."
            )

        # Qualification rule is fixed to strict greater-than.
        if req.qualification_rule != ">":
            raise BadRequestException(
                "Qualification rule is fixed: obtained marks must be "
                "strictly greater than passing marks."
            )

        if req.selection_mode == "SPECIFIC":
            if (
                not req.selected_question_ids
                or len(req.selected_question_ids) < req.total_questions
            ):
                raise BadRequestException(
                    f"Please select at least {req.total_questions} "
                    "questions from the Question Bank."
                )
        else:
            pool = AssessmentAssignmentService.get_eligible_questions(
                db,
                recruiter_id=recruiter.id,
                categories=req.categories,
                job_id=job_id,
            )

            if len(pool) < req.total_questions:
                raise BadRequestException(
                    f"Insufficient questions in Question Bank. "
                    f"You configured {req.total_questions} questions, "
                    f"but only {len(pool)} are available."
                )

            if req.difficulty_distribution:
                sum_dist = sum(req.difficulty_distribution.values())

                if sum_dist != req.total_questions:
                    raise BadRequestException(
                        f"Difficulty distribution total ({sum_dist}) "
                        f"does not match configured question count "
                        f"({req.total_questions})."
                    )

    config = (
        db.query(JobAssessment)
        .filter(JobAssessment.job_id == job_id)
        .first()
    )

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

    # Never save >=. Always persist strict greater-than.
    config.qualification_rule = ">"

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
        job_id=job_id,
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
        "qualification_rule": ">",
        "negative_marking": config.negative_marking,
        "negative_marks": config.negative_marks,
        "categories": config.categories or [],
        "difficulty_distribution": config.difficulty_distribution,
        "selection_mode": config.selection_mode,
        "selected_question_ids": config.selected_question_ids,
        "eligible_questions_count": len(pool),
    }


# ---------------------------------------------------------
# PREVIEW JOB ASSESSMENT
# ---------------------------------------------------------

@router.get("/jobs/{job_id}/assessment/preview")
def preview_job_assessment(
    job_id: int,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db),
):
    job = (
        db.query(Job)
        .filter(
            Job.id == job_id,
            Job.recruiter_id == recruiter.id,
        )
        .first()
    )

    if not job or not job.assessment_config:
        raise NotFoundException("Assessment Configuration")

    config = job.assessment_config

    pool = AssessmentAssignmentService.get_eligible_questions(
        db,
        recruiter_id=recruiter.id,
        categories=config.categories,
        job_id=job_id,
    )

    sample_questions = pool[:config.total_questions] if pool else []

    return {
        "title": config.title,
        "is_enabled": config.is_enabled,
        "total_questions": config.total_questions,
        "duration_minutes": config.duration_minutes,
        "total_marks": config.total_marks,
        "passing_marks": config.passing_marks,
        "qualification_rule": ">",
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
                "option_d": q.option_d,
            }
            for q in sample_questions
        ],
    }


# ---------------------------------------------------------
# RECRUITER ASSESSMENT RESULTS
# ---------------------------------------------------------

@router.get(
    "/recruiter/assessments/results",
    response_model=List[RecruiterAssessmentResultItem],
)
def get_recruiter_assessment_results(
    job_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db),
):
    query = (
        db.query(CandidateAssessmentResult)
        .join(Job)
        .filter(Job.recruiter_id == recruiter.id)
    )

    if job_id:
        query = query.filter(
            CandidateAssessmentResult.job_id == job_id
        )

    if status_filter == "qualified":
        query = query.filter(
            CandidateAssessmentResult.is_qualified.is_(True)
        )
    elif status_filter == "not_qualified":
        query = query.filter(
            CandidateAssessmentResult.is_qualified.is_(False)
        )

    results = query.order_by(
        desc(CandidateAssessmentResult.evaluated_at)
    ).all()

    # Fetch all proctoring sessions in one query.
    assignment_ids = [
        r.assignment_id
        for r in results
        if r.assignment_id is not None
    ]

    sessions = []

    if assignment_ids:
        sessions = (
            db.query(ProctoringSession)
            .filter(
                ProctoringSession.assignment_id.in_(assignment_ids)
            )
            .all()
        )

    session_map = {
        session.assignment_id: session
        for session in sessions
    }

    output = []

    for r in results:
        cand = r.candidate
        cand_user = cand.user if cand else None
        job = r.job
        assignment = r.assignment

        if search and search.strip():
            term = search.strip().lower()

            cand_name = (
                cand_user.full_name.lower()
                if cand_user and cand_user.full_name
                else ""
            )

            cand_email = (
                cand_user.email.lower()
                if cand_user and cand_user.email
                else ""
            )

            job_title = (
                job.title.lower()
                if job and job.title
                else ""
            )

            if (
                term not in cand_name
                and term not in cand_email
                and term not in job_title
            ):
                continue

        session = session_map.get(r.assignment_id)

        output.append({
            "id": r.id,
            "assignment_id": r.assignment_id,
            "candidate_id": r.candidate_id,
            "candidate_name": (
                cand_user.full_name if cand_user else "Candidate"
            ),
            "candidate_email": (
                cand_user.email if cand_user else ""
            ),
            "job_id": r.job_id,
            "job_title": job.title if job else "",
            "assessment_title": (
                assignment.config_snapshot.get(
                    "title",
                    "Assessment",
                )
                if assignment and assignment.config_snapshot
                else "Assessment"
            ),
            "obtained_marks": r.obtained_marks,
            "total_marks": r.total_marks,
            "percentage": r.percentage,
            "correct_count": r.correct_count,
            "incorrect_count": r.incorrect_count,
            "unanswered_count": r.unanswered_count,
            "passing_marks": r.passing_marks,
            "qualification_rule": ">",
            "is_qualified": r.is_qualified,
            "is_flagged_for_review": (
                session.is_flagged_for_review
                if session
                else False
            ),
            "time_taken_seconds": (
                r.attempt.time_taken_seconds
                if r.attempt
                else 0
            ),
            "evaluated_at": r.evaluated_at,
            "question_breakdown": r.question_breakdown,
        })

    return output


# ---------------------------------------------------------
# RECRUITER ASSESSMENT RESULT DETAILS
# ---------------------------------------------------------

@router.get("/recruiter/assessments/results/{result_id}")
def get_recruiter_result_detail(
    result_id: int,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db),
):
    r = (
        db.query(CandidateAssessmentResult)
        .join(Job)
        .filter(
            CandidateAssessmentResult.id == result_id,
            Job.recruiter_id == recruiter.id,
        )
        .first()
    )

    if not r:
        raise NotFoundException("Assessment Result")

    cand_user = r.candidate.user if r.candidate else None

    session = (
        db.query(ProctoringSession)
        .filter(
            ProctoringSession.assignment_id == r.assignment_id
        )
        .first()
    )

    return {
        "id": r.id,
        "assignment_id": r.assignment_id,
        "candidate_id": r.candidate_id,
        "candidate_name": (
            cand_user.full_name if cand_user else ""
        ),
        "candidate_email": (
            cand_user.email if cand_user else ""
        ),
        "job_title": r.job.title if r.job else "",
        "assessment_title": (
            r.assignment.config_snapshot.get("title")
            if r.assignment and r.assignment.config_snapshot
            else ""
        ),
        "obtained_marks": r.obtained_marks,
        "total_marks": r.total_marks,
        "percentage": r.percentage,
        "correct_count": r.correct_count,
        "incorrect_count": r.incorrect_count,
        "unanswered_count": r.unanswered_count,
        "passing_marks": r.passing_marks,
        "qualification_rule": ">",
        "is_qualified": r.is_qualified,
        "qualification_message": r.qualification_message,
        "is_flagged_for_review": (
            session.is_flagged_for_review
            if session
            else False
        ),
        "time_taken_seconds": (
            r.attempt.time_taken_seconds
            if r.attempt
            else 0
        ),
        "evaluated_at": r.evaluated_at,
        "question_breakdown": r.question_breakdown,
    }
