from typing import List
import datetime
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.dependencies import get_current_user, get_current_candidate
from app.core.exceptions import NotFoundException, BadRequestException
from app.models.candidate import Candidate
from app.models.assessment import (
    TechnicalAssessment,
    AssessmentQuestion,
    AssessmentAttempt,
    AssessmentResult,
)
from app.schemas.assessment import (
    AssessmentListItem,
    AssessmentAttemptStart,
    AssessmentQuestionItem,
    AssessmentSubmissionRequest,
    AssessmentAttemptResultResponse,
    AssessmentQuestionResultItem,
)

router = APIRouter(prefix="/assessments", tags=["Technical Assessments"])

@router.get("", response_model=List[AssessmentListItem])
def list_assessments(db: Session = Depends(get_db)):
    """List all available technology assessments."""
    assessments = db.query(TechnicalAssessment).filter(TechnicalAssessment.is_active == True).all()
    return assessments

@router.get("/{assessment_id}", response_model=AssessmentListItem)
def get_assessment(assessment_id: int, db: Session = Depends(get_db)):
    """Get single assessment details."""
    assessment = db.query(TechnicalAssessment).filter(TechnicalAssessment.id == assessment_id).first()
    if not assessment:
        raise NotFoundException("Assessment")
    return assessment

@router.post("/{assessment_id}/start", response_model=AssessmentAttemptStart)
def start_assessment_attempt(
    assessment_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """
    Start a timed assessment attempt.
    Returns test questions without exposing correct options.
    """
    assessment = db.query(TechnicalAssessment).filter(TechnicalAssessment.id == assessment_id).first()
    if not assessment:
        raise NotFoundException("Assessment")

    attempt = AssessmentAttempt(
        assessment_id=assessment.id,
        candidate_id=candidate.id,
        started_at=datetime.datetime.utcnow(),
        score=0.0,
        total_score=100.0,
        passed=False
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    question_items = [
        AssessmentQuestionItem(
            id=q.id,
            question_text=q.question_text,
            option_a=q.option_a,
            option_b=q.option_b,
            option_c=q.option_c,
            option_d=q.option_d
        )
        for q in assessment.questions
    ]

    return {
        "attempt_id": attempt.id,
        "assessment_id": assessment.id,
        "title": assessment.title,
        "technology": assessment.technology,
        "duration_minutes": assessment.duration_minutes,
        "started_at": attempt.started_at,
        "questions": question_items
    }

@router.post("/attempts/{attempt_id}/submit", response_model=AssessmentAttemptResultResponse)
def submit_assessment_attempt(
    attempt_id: int,
    req: AssessmentSubmissionRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """
    Submit answers, automatically compute actual score from database answers,
    record question results with explanations, and update candidate history.
    """
    attempt = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.id == attempt_id,
        AssessmentAttempt.candidate_id == candidate.id
    ).first()
    if not attempt:
        raise NotFoundException("Assessment Attempt")

    if attempt.completed_at:
        raise BadRequestException("This assessment attempt has already been submitted.")

    assessment = attempt.assessment
    correct_count = 0
    total_q = len(assessment.questions)
    results_list = []

    # Map question IDs to question records
    q_map = {q.id: q for q in assessment.questions}

    for sub in req.answers:
        q = q_map.get(sub.question_id)
        if not q:
            continue

        is_correct = (sub.selected_option.strip().upper() == q.correct_option.strip().upper())
        if is_correct:
            correct_count += 1

        res = AssessmentResult(
            attempt_id=attempt.id,
            question_id=q.id,
            selected_option=sub.selected_option.strip().upper(),
            is_correct=is_correct
        )
        db.add(res)

        results_list.append(
            AssessmentQuestionResultItem(
                question_id=q.id,
                question_text=q.question_text,
                selected_option=sub.selected_option.strip().upper(),
                correct_option=q.correct_option,
                is_correct=is_correct,
                explanation=q.explanation
            )
        )

    score_percentage = round((correct_count / float(total_q)) * 100.0, 1) if total_q > 0 else 0.0
    attempt.completed_at = datetime.datetime.utcnow()
    attempt.score = score_percentage
    attempt.passed = (score_percentage >= assessment.passing_score)

    db.commit()

    return {
        "attempt_id": attempt.id,
        "assessment_title": assessment.title,
        "technology": assessment.technology,
        "score": attempt.score,
        "total_score": 100.0,
        "passed": attempt.passed,
        "started_at": attempt.started_at,
        "completed_at": attempt.completed_at,
        "question_results": results_list
    }

@router.get("/attempts/history")
def get_attempt_history(
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """View candidate's test attempts and scores."""
    attempts = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.candidate_id == candidate.id
    ).order_by(AssessmentAttempt.created_at.desc()).all()

    return [
        {
            "id": a.id,
            "assessment_id": a.assessment_id,
            "title": a.assessment.title if a.assessment else "",
            "technology": a.assessment.technology if a.assessment else "",
            "score": a.score,
            "passed": a.passed,
            "completed_at": a.completed_at
        }
        for a in attempts
    ]
