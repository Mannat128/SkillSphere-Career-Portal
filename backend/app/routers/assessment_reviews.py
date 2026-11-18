
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.session import get_db
from app.core.dependencies import get_current_recruiter
from app.core.exceptions import NotFoundException, BadRequestException

from app.models.recruiter import Recruiter
from app.models.job import Job
from app.models.recruiter_assessment import CandidateAssessmentResult
from app.models.notification import Notification


router = APIRouter(
    prefix="/recruiter/assessments/reviews",
    tags=["Recruiter Manual Assessment Review"],
)


class AssessmentReviewRequest(BaseModel):
    decision: str = Field(..., pattern="^(QUALIFIED|NOT_QUALIFIED)$")
    review_notes: Optional[str] = Field(None, max_length=2000)


def get_recruiter_owned_result(
    result_id: int,
    recruiter: Recruiter,
    db: Session,
):
    result = (
        db.query(CandidateAssessmentResult)
        .join(Job)
        .filter(
            CandidateAssessmentResult.id == result_id,
            Job.recruiter_id == recruiter.id,
        )
        .first()
    )

    if not result:
        raise NotFoundException("Assessment Result")

    return result


@router.get("")
def list_assessment_reviews(
    review_status: str = Query("PENDING_REVIEW"),
    job_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db),
):
    allowed_statuses = {
        "PENDING_REVIEW",
        "QUALIFIED",
        "NOT_QUALIFIED",
        "ALL",
    }

    review_status = review_status.upper()

    if review_status not in allowed_statuses:
        raise BadRequestException("Invalid review status.")

    query = (
        db.query(CandidateAssessmentResult)
        .join(Job)
        .filter(Job.recruiter_id == recruiter.id)
    )

    if review_status != "ALL":
        query = query.filter(
            CandidateAssessmentResult.review_status == review_status
        )

    if job_id:
        query = query.filter(
            CandidateAssessmentResult.job_id == job_id
        )

    results = query.order_by(
        desc(CandidateAssessmentResult.evaluated_at)
    ).all()

    output = []

    for result in results:
        candidate = result.candidate
        candidate_user = candidate.user if candidate else None
        job = result.job
        assignment = result.assignment

        if search and search.strip():
            term = search.strip().lower()

            name = (
                candidate_user.full_name.lower()
                if candidate_user and candidate_user.full_name
                else ""
            )
            email = (
                candidate_user.email.lower()
                if candidate_user and candidate_user.email
                else ""
            )
            title = job.title.lower() if job and job.title else ""

            if term not in name and term not in email and term not in title:
                continue

        output.append({
            "id": result.id,
            "assignment_id": result.assignment_id,
            "candidate_id": result.candidate_id,
            "candidate_name": (
                candidate_user.full_name
                if candidate_user
                else "Candidate"
            ),
            "candidate_email": (
                candidate_user.email
                if candidate_user
                else ""
            ),
            "job_id": result.job_id,
            "job_title": job.title if job else "",
            "assessment_title": (
                assignment.config_snapshot.get("title", "Assessment")
                if assignment and assignment.config_snapshot
                else "Assessment"
            ),
            "obtained_marks": result.obtained_marks,
            "total_marks": result.total_marks,
            "percentage": result.percentage,
            "passing_marks": result.passing_marks,
            "automatic_score_qualified": result.is_qualified,
            "review_status": result.review_status,
            "review_notes": result.review_notes,
            "reviewed_at": result.reviewed_at,
            "evaluated_at": result.evaluated_at,
            "correct_count": result.correct_count,
            "incorrect_count": result.incorrect_count,
            "unanswered_count": result.unanswered_count,
            "time_taken_seconds": (
                result.attempt.time_taken_seconds
                if result.attempt
                else 0
            ),
            "question_breakdown": result.question_breakdown,
        })

    return output


@router.post("/{result_id}/review")
def submit_assessment_review(
    result_id: int,
    req: AssessmentReviewRequest,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db),
):
    result = get_recruiter_owned_result(
        result_id,
        recruiter,
        db,
    )

    if result.review_status != "PENDING_REVIEW":
        raise BadRequestException(
            "This assessment has already been reviewed. "
            "Review decisions cannot be changed."
        )

    decision = req.decision.upper()
    now = datetime.utcnow()

    result.review_status = decision
    result.reviewed_by_id = recruiter.user_id
    result.reviewed_at = now
    result.review_notes = (
        req.review_notes.strip()
        if req.review_notes and req.review_notes.strip()
        else None
    )

    # The recruiter's final decision controls the candidate's workflow status.
    if result.assignment:
        result.assignment.status = decision
        result.assignment.updated_at = now

    candidate_user = (
        result.candidate.user
        if result.candidate
        else None
    )

    if candidate_user:
        if decision == "QUALIFIED":
            title = "Assessment Review Completed"
            message = (
                f"Your assessment for '{result.job.title if result.job else 'the position'}' "
                "has been reviewed. You have qualified for the next round."
            )
        else:
            title = "Assessment Review Completed"
            message = (
                f"Your assessment for '{result.job.title if result.job else 'the position'}' "
                "has been reviewed. You have not been selected for the next round."
            )

        db.add(
            Notification(
                user_id=candidate_user.id,
                title=title,
                message=message,
                type="APPLICATION",
                link="/candidate/assessments",
            )
        )

    db.commit()
    db.refresh(result)

    return {
        "message": "Assessment review submitted successfully.",
        "result_id": result.id,
        "review_status": result.review_status,
        "reviewed_at": result.reviewed_at,
    }