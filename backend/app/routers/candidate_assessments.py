import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.session import get_db
from app.core.dependencies import get_current_user, get_current_candidate
from app.core.exceptions import NotFoundException, BadRequestException, ForbiddenException
from app.models.user import User
from app.models.candidate import Candidate
from app.models.recruiter_assessment import (
    AssessmentAssignment,
    CandidateAssessmentAttempt,
    CandidateAssessmentResult,
)
from app.schemas.recruiter_assessment import (
    CandidateAssignmentListItem,
    CandidateTestStartResponse,
    CandidateQuestionItem,
    SaveAnswerRequest,
    SubmitAssessmentRequest,
    CandidateAssessmentResultResponse,
)
from app.services.assessment_assignment_service import AssessmentAssignmentService

router = APIRouter(prefix="/candidate/first-round-assessments", tags=["Candidate First Round Assessment"])

@router.get("", response_model=List[CandidateAssignmentListItem])
def list_candidate_first_round_assessments(
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """
    Section 7: Candidate Assessment Dashboard.
    List all First Round recruitment assessments assigned to this candidate.
    """
    assignments = db.query(AssessmentAssignment).filter(
        AssessmentAssignment.candidate_id == candidate.id
    ).order_by(desc(AssessmentAssignment.assigned_at)).all()

    output = []
    for a in assignments:
        config = a.config_snapshot
        attempt = a.attempt
        result = a.result

        output.append({
            "id": a.id,
            "job_id": a.job_id,
            "job_title": a.job.title if a.job else "Position",
            "company_name": a.job.company.name if (a.job and a.job.company) else "Company",
            "assessment_title": config.get("title", "First Round Assessment"),
            "total_questions": config.get("total_questions", 0),
            "duration_minutes": config.get("duration_minutes", 30),
            "total_marks": config.get("total_marks", 0.0),
            "passing_marks": config.get("passing_marks", 0.0),
            "qualification_rule": config.get("qualification_rule", ">"),
            "negative_marking": config.get("negative_marking", False),
            "negative_marks": config.get("negative_marks", 0.0),
            "status": a.status,
            "assigned_at": a.assigned_at,
            "started_at": attempt.started_at if attempt else None,
            "expires_at": attempt.expires_at if attempt else None,
            "is_submitted": attempt.is_submitted if attempt else False,
            "is_qualified": result.is_qualified if result else None
        })

    return output

@router.get("/{assignment_id}")
def get_assessment_instructions(
    assignment_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """View test metadata, rules, and instructions before starting."""
    assignment = db.query(AssessmentAssignment).filter(
        AssessmentAssignment.id == assignment_id,
        AssessmentAssignment.candidate_id == candidate.id
    ).first()
    if not assignment:
        raise NotFoundException("Assessment Assignment")

    config = assignment.config_snapshot
    attempt = assignment.attempt

    return {
        "assignment_id": assignment.id,
        "job_title": assignment.job.title if assignment.job else "",
        "company_name": assignment.job.company.name if (assignment.job and assignment.job.company) else "",
        "title": config.get("title"),
        "instructions": config.get("instructions"),
        "total_questions": config.get("total_questions"),
        "duration_minutes": config.get("duration_minutes"),
        "total_marks": config.get("total_marks"),
        "passing_marks": config.get("passing_marks"),
        "qualification_rule": config.get("qualification_rule"),
        "negative_marking": config.get("negative_marking"),
        "negative_marks": config.get("negative_marks"),
        "status": assignment.status,
        "is_started": bool(attempt),
        "is_submitted": attempt.is_submitted if attempt else False,
    }

@router.post("/{assignment_id}/start", response_model=CandidateTestStartResponse)
def start_or_resume_assessment(
    assignment_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """
    Start or resume time-bound assessment attempt.
    - If already submitted: blocks retake.
    - If active: restores state and calculates remaining time based on backend expiry.
    - If expired: automatically submits and evaluates.
    - Questions provided WITHOUT correct answers.
    """
    assignment = db.query(AssessmentAssignment).filter(
        AssessmentAssignment.id == assignment_id,
        AssessmentAssignment.candidate_id == candidate.id
    ).first()
    if not assignment:
        raise NotFoundException("Assessment Assignment")

    config = assignment.config_snapshot
    duration_min = config.get("duration_minutes", 30)
    now = datetime.datetime.utcnow()

    attempt = assignment.attempt

    if attempt:
        if attempt.is_submitted:
            raise BadRequestException("You have already submitted this assessment. Retakes are not allowed.")

        # Check if time expired
        if now >= attempt.expires_at:
            # Auto-submit
            AssessmentAssignmentService.evaluate_attempt(db, attempt)
            raise BadRequestException("Assessment duration has expired. Your answers have been automatically submitted.")
    else:
        # Create new attempt
        expires = now + datetime.timedelta(minutes=duration_min)
        attempt = CandidateAssessmentAttempt(
            assignment_id=assignment.id,
            candidate_id=candidate.id,
            started_at=now,
            expires_at=expires,
            is_submitted=False,
            saved_answers={},
            marked_for_review=[]
        )
        db.add(attempt)
        assignment.status = "IN_PROGRESS"
        db.commit()
        db.refresh(attempt)

    remaining_sec = max(0, int((attempt.expires_at - now).total_seconds()))

    # Build question items without exposing correct answers!
    question_items = [
        CandidateQuestionItem(
            id=q["id"],
            question_text=q["question_text"],
            category=q["category"],
            difficulty=q["difficulty"],
            option_a=q["option_a"],
            option_b=q["option_b"],
            option_c=q["option_c"],
            option_d=q["option_d"],
            marks=q["marks"]
        )
        for q in assignment.assigned_questions
    ]

    return {
        "attempt_id": attempt.id,
        "assignment_id": assignment.id,
        "title": config.get("title", "Assessment"),
        "duration_minutes": duration_min,
        "started_at": attempt.started_at,
        "expires_at": attempt.expires_at,
        "remaining_seconds": remaining_sec,
        "negative_marking": config.get("negative_marking", False),
        "negative_marks": config.get("negative_marks", 0.0),
        "questions": question_items,
        "saved_answers": attempt.saved_answers or {},
        "marked_for_review": attempt.marked_for_review or []
    }

@router.post("/{assignment_id}/save-answer")
def save_candidate_answer(
    assignment_id: int,
    req: SaveAnswerRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Save an answer or toggle mark-for-review during active test."""
    assignment = db.query(AssessmentAssignment).filter(
        AssessmentAssignment.id == assignment_id,
        AssessmentAssignment.candidate_id == candidate.id
    ).first()
    if not assignment or not assignment.attempt:
        raise NotFoundException("Active Assessment Attempt")

    attempt = assignment.attempt
    if attempt.is_submitted:
        raise BadRequestException("Assessment is already submitted.")

    now = datetime.datetime.utcnow()
    if now >= attempt.expires_at:
        AssessmentAssignmentService.evaluate_attempt(db, attempt)
        raise BadRequestException("Assessment duration has expired. Answers submitted.")

    answers = dict(attempt.saved_answers or {})
    if req.selected_option is not None:
        answers[str(req.question_id)] = req.selected_option
    attempt.saved_answers = answers

    if req.is_marked_for_review is not None:
        reviews = list(attempt.marked_for_review or [])
        if req.is_marked_for_review and req.question_id not in reviews:
            reviews.append(req.question_id)
        elif not req.is_marked_for_review and req.question_id in reviews:
            reviews.remove(req.question_id)
        attempt.marked_for_review = reviews

    db.commit()
    return {"message": "Answer saved successfully"}

@router.post("/{assignment_id}/submit", response_model=CandidateAssessmentResultResponse)
def submit_assessment(
    assignment_id: int,
    req: Optional[SubmitAssessmentRequest] = None,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """
    Candidate final submission:
    Evaluates assessment completely on the backend and immediately returns qualification scorecard.
    """
    assignment = db.query(AssessmentAssignment).filter(
        AssessmentAssignment.id == assignment_id,
        AssessmentAssignment.candidate_id == candidate.id
    ).first()
    if not assignment or not assignment.attempt:
        raise NotFoundException("Assessment Attempt")

    attempt = assignment.attempt
    if attempt.is_submitted:
        # Return existing result
        result = assignment.result
        if result:
            return {
                "assignment_id": assignment.id,
                "job_title": assignment.job.title if assignment.job else "",
                "assessment_title": assignment.config_snapshot.get("title", ""),
                "obtained_marks": result.obtained_marks,
                "total_marks": result.total_marks,
                "percentage": result.percentage,
                "correct_count": result.correct_count,
                "incorrect_count": result.incorrect_count,
                "unanswered_count": result.unanswered_count,
                "passing_marks": result.passing_marks,
                "qualification_rule": result.qualification_rule,
                "is_qualified": result.is_qualified,
                "qualification_message": result.qualification_message,
                "submitted_at": attempt.submitted_at or datetime.datetime.utcnow(),
                "time_taken_seconds": attempt.time_taken_seconds or 0
            }
        raise BadRequestException("Already submitted.")

    if req and req.final_answers:
        merged = dict(attempt.saved_answers or {})
        merged.update(req.final_answers)
        attempt.saved_answers = merged

    # Backend Evaluation
    result = AssessmentAssignmentService.evaluate_attempt(db, attempt)

    return {
        "assignment_id": assignment.id,
        "job_title": assignment.job.title if assignment.job else "",
        "assessment_title": assignment.config_snapshot.get("title", ""),
        "obtained_marks": result.obtained_marks,
        "total_marks": result.total_marks,
        "percentage": result.percentage,
        "correct_count": result.correct_count,
        "incorrect_count": result.incorrect_count,
        "unanswered_count": result.unanswered_count,
        "passing_marks": result.passing_marks,
        "qualification_rule": result.qualification_rule,
        "is_qualified": result.is_qualified,
        "qualification_message": result.qualification_message,
        "submitted_at": attempt.submitted_at,
        "time_taken_seconds": attempt.time_taken_seconds or 0
    }

@router.get("/{assignment_id}/result", response_model=CandidateAssessmentResultResponse)
def get_candidate_result(
    assignment_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Retrieve immediate candidate result scorecard."""
    assignment = db.query(AssessmentAssignment).filter(
        AssessmentAssignment.id == assignment_id,
        AssessmentAssignment.candidate_id == candidate.id
    ).first()
    if not assignment or not assignment.result:
        raise NotFoundException("Assessment Result")

    result = assignment.result
    attempt = assignment.attempt

    return {
        "assignment_id": assignment.id,
        "job_title": assignment.job.title if assignment.job else "",
        "assessment_title": assignment.config_snapshot.get("title", ""),
        "obtained_marks": result.obtained_marks,
        "total_marks": result.total_marks,
        "percentage": result.percentage,
        "correct_count": result.correct_count,
        "incorrect_count": result.incorrect_count,
        "unanswered_count": result.unanswered_count,
        "passing_marks": result.passing_marks,
        "qualification_rule": result.qualification_rule,
        "is_qualified": result.is_qualified,
        "qualification_message": result.qualification_message,
        "submitted_at": attempt.submitted_at if attempt else result.evaluated_at,
        "time_taken_seconds": attempt.time_taken_seconds if attempt else 0
    }
