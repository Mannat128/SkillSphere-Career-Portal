
import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.session import get_db
from app.core.dependencies import get_current_candidate
from app.core.exceptions import NotFoundException, BadRequestException
from app.models.candidate import Candidate
from app.models.proctoring import ProctoringSession
from app.models.recruiter_assessment import (
    AssessmentAssignment,
    CandidateAssessmentAttempt,
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


router = APIRouter(
    prefix="/candidate/first-round-assessments",
    tags=["Candidate First Round Assessment"],
)


def get_candidate_safe_status(status: str) -> str:
    """Hide qualification status from candidates."""
    if status in ("QUALIFIED", "NOT_QUALIFIED"):
        return "COMPLETED"
    return status


def get_owned_assignment(
    assignment_id: int,
    candidate: Candidate,
    db: Session,
) -> AssessmentAssignment:
    """Return an assignment only if it belongs to the logged-in candidate."""
    assignment = (
        db.query(AssessmentAssignment)
        .filter(
            AssessmentAssignment.id == assignment_id,
            AssessmentAssignment.candidate_id == candidate.id,
        )
        .first()
    )

    if not assignment:
        raise NotFoundException("Assessment Assignment")

    return assignment


def require_proctoring_consent(
    assignment: AssessmentAssignment,
    candidate: Candidate,
    db: Session,
) -> ProctoringSession:
    """Require recorded consent and camera permission before assessment start."""
    session = (
        db.query(ProctoringSession)
        .filter(
            ProctoringSession.assignment_id == assignment.id,
            ProctoringSession.candidate_id == candidate.id,
        )
        .first()
    )

    if not session:
        raise BadRequestException(
            "Please complete proctoring consent before starting the assessment."
        )

    if not session.consent_given:
        raise BadRequestException(
            "Proctoring consent is required before starting the assessment."
        )

    if not session.camera_permission_granted:
        raise BadRequestException(
            "Camera permission is required before starting the assessment."
        )

    return session


def require_completed_recording(
    assignment: AssessmentAssignment,
    candidate: Candidate,
    db: Session,
) -> ProctoringSession:
    """Require a successfully uploaded recording before assessment evaluation."""
    session = (
        db.query(ProctoringSession)
        .filter(
            ProctoringSession.assignment_id == assignment.id,
            ProctoringSession.candidate_id == candidate.id,
        )
        .first()
    )

    if not session:
        raise BadRequestException(
            "Proctoring session not found. Assessment cannot be submitted."
        )

    if not session.consent_given or not session.camera_permission_granted:
        raise BadRequestException(
            "Valid proctoring consent and camera permission are required."
        )

    if (
        session.session_status != "COMPLETED"
        or not session.recording_path
        or not session.recording_completed_at
        or session.recording_deleted_at is not None
    ):
        raise BadRequestException(
            "Your proctoring recording is not completed or uploaded yet. "
            "Please complete the recording upload before submitting."
        )

    return session


def get_assigned_question_ids(
    assignment: AssessmentAssignment,
) -> set:
    """Build the set of question IDs assigned to this candidate."""
    return {
        str(question["id"])
        for question in (assignment.assigned_questions or [])
        if isinstance(question, dict) and question.get("id") is not None
    }


def validate_answer(
    question_id: int,
    selected_option: Optional[str],
    valid_question_ids: set,
) -> Optional[str]:
    """Validate question ownership and the selected MCQ option."""
    question_key = str(question_id)

    if question_key not in valid_question_ids:
        raise BadRequestException(
            "Invalid question. This question is not part of your assessment."
        )

    if selected_option is None:
        return None

    normalized_option = selected_option.strip().upper()

    if normalized_option not in {"A", "B", "C", "D"}:
        raise BadRequestException(
            "Invalid option. Please select A, B, C, or D."
        )

    return normalized_option


@router.get("", response_model=List[CandidateAssignmentListItem])
def list_candidate_first_round_assessments(
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """List assessments assigned to the logged-in candidate."""
    assignments = (
        db.query(AssessmentAssignment)
        .filter(AssessmentAssignment.candidate_id == candidate.id)
        .order_by(desc(AssessmentAssignment.assigned_at))
        .all()
    )

    output = []

    for assignment in assignments:
        config = assignment.config_snapshot or {}
        attempt = assignment.attempt

        output.append({
            "id": assignment.id,
            "job_id": assignment.job_id,
            "job_title": assignment.job.title if assignment.job else "Position",
            "company_name": (
                assignment.job.company.name
                if assignment.job and assignment.job.company
                else "Company"
            ),
            "assessment_title": config.get(
                "title", "First Round Assessment"
            ),
            "total_questions": config.get("total_questions", 0),
            "duration_minutes": config.get("duration_minutes", 30),
            "total_marks": config.get("total_marks", 0.0),
            "negative_marking": config.get("negative_marking", False),
            "negative_marks": config.get("negative_marks", 0.0),
            "status": get_candidate_safe_status(assignment.status),
            "assigned_at": assignment.assigned_at,
            "started_at": attempt.started_at if attempt else None,
            "expires_at": attempt.expires_at if attempt else None,
            "is_submitted": attempt.is_submitted if attempt else False,
        })

    return output


@router.get("/{assignment_id}")
def get_assessment_instructions(
    assignment_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """Return assessment instructions without qualification criteria."""
    assignment = get_owned_assignment(assignment_id, candidate, db)

    config = assignment.config_snapshot or {}
    attempt = assignment.attempt

    return {
        "assignment_id": assignment.id,
        "job_title": assignment.job.title if assignment.job else "",
        "company_name": (
            assignment.job.company.name
            if assignment.job and assignment.job.company
            else ""
        ),
        "title": config.get("title"),
        "instructions": config.get("instructions"),
        "total_questions": config.get("total_questions"),
        "duration_minutes": config.get("duration_minutes"),
        "total_marks": config.get("total_marks"),
        "negative_marking": config.get("negative_marking"),
        "negative_marks": config.get("negative_marks"),
        "status": get_candidate_safe_status(assignment.status),
        "is_started": bool(attempt),
        "is_submitted": attempt.is_submitted if attempt else False,
    }


@router.post(
    "/{assignment_id}/start",
    response_model=CandidateTestStartResponse,
)
def start_or_resume_assessment(
    assignment_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """Start or resume an assessment after verifying proctoring consent."""
    assignment = get_owned_assignment(assignment_id, candidate, db)

    # Consent and camera permission are mandatory before an attempt starts.
    require_proctoring_consent(assignment, candidate, db)

    config = assignment.config_snapshot or {}
    duration_min = config.get("duration_minutes", 30)
    now = datetime.datetime.utcnow()

    attempt = assignment.attempt

    if attempt:
        if attempt.candidate_id != candidate.id:
            raise NotFoundException("Assessment Attempt")

        if attempt.is_submitted:
            raise BadRequestException(
                "You have already submitted this assessment. Retakes are not allowed."
            )

        if now >= attempt.expires_at:
            raise BadRequestException(
                "Assessment duration has expired. Please submit your assessment."
            )

    else:
        if assignment.status in ("SUBMITTED", "QUALIFIED", "NOT_QUALIFIED", "EXPIRED"):
            raise BadRequestException(
                "This assessment is no longer available. Retakes are not allowed."
            )

        expires = now + datetime.timedelta(minutes=duration_min)

        attempt = CandidateAssessmentAttempt(
            assignment_id=assignment.id,
            candidate_id=candidate.id,
            started_at=now,
            expires_at=expires,
            is_submitted=False,
            saved_answers={},
            marked_for_review=[],
        )

        db.add(attempt)
        assignment.status = "IN_PROGRESS"
        db.commit()
        db.refresh(attempt)

    remaining_sec = max(
        0,
        int((attempt.expires_at - now).total_seconds()),
    )

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
            marks=q["marks"],
        )
        for q in (assignment.assigned_questions or [])
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
        "marked_for_review": attempt.marked_for_review or [],
    }


@router.post("/{assignment_id}/save-answer")
def save_candidate_answer(
    assignment_id: int,
    req: SaveAnswerRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """Save an answer or update its review status."""
    assignment = get_owned_assignment(assignment_id, candidate, db)

    attempt = assignment.attempt

    if not attempt or attempt.candidate_id != candidate.id:
        raise NotFoundException("Active Assessment Attempt")

    if attempt.is_submitted:
        raise BadRequestException("Assessment is already submitted.")

    now = datetime.datetime.utcnow()

    if now >= attempt.expires_at:
        raise BadRequestException(
            "Assessment duration has expired. Please submit your assessment."
        )

    valid_question_ids = get_assigned_question_ids(assignment)

    normalized_option = validate_answer(
        req.question_id,
        req.selected_option,
        valid_question_ids,
    )

    answers = dict(attempt.saved_answers or {})

    if normalized_option is not None:
        answers[str(req.question_id)] = normalized_option

    attempt.saved_answers = answers

    if req.is_marked_for_review is not None:
        reviews = list(attempt.marked_for_review or [])

        if req.is_marked_for_review and req.question_id not in reviews:
            reviews.append(req.question_id)

        elif (
            not req.is_marked_for_review
            and req.question_id in reviews
        ):
            reviews.remove(req.question_id)

        attempt.marked_for_review = reviews

    db.commit()

    return {"message": "Answer saved successfully"}


@router.post(
    "/{assignment_id}/submit",
    response_model=CandidateAssessmentResultResponse,
)
def submit_assessment(
    assignment_id: int,
    req: Optional[SubmitAssessmentRequest] = None,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """
    Verify recording, evaluate the assessment internally,
    and return only a neutral confirmation to the candidate.
    """
    assignment = get_owned_assignment(assignment_id, candidate, db)

    attempt = assignment.attempt

    if not attempt or attempt.candidate_id != candidate.id:
        raise NotFoundException("Assessment Attempt")

    if attempt.is_submitted:
        return {
            "assignment_id": assignment.id,
            "message": "Your assessment has already been submitted successfully.",
            "submitted_at": attempt.submitted_at,
        }

    # Recording must be uploaded and completed before evaluation.
    require_completed_recording(assignment, candidate, db)

    valid_question_ids = get_assigned_question_ids(assignment)

    # After the deadline, only answers saved before expiry may be evaluated.
    # Do not accept new answers supplied in the final submit request.
    submission_is_expired = datetime.datetime.utcnow() >= attempt.expires_at

    if req and req.final_answers and not submission_is_expired:
        merged = dict(attempt.saved_answers or {})

        for question_id, selected_option in req.final_answers.items():
            question_key = str(question_id)

            if question_key not in valid_question_ids:
                raise BadRequestException(
                    "Submission contains a question that was not assigned to you."
                )

            normalized_option = validate_answer(
                question_id,
                selected_option,
                valid_question_ids,
            )

            if normalized_option is not None:
                merged[question_key] = normalized_option

        attempt.saved_answers = merged

    # Evaluate and store the result internally.
    # Candidate receives no marks or qualification details.
    AssessmentAssignmentService.evaluate_attempt(db, attempt)

    return {
        "assignment_id": assignment.id,
        "message": "Your assessment has been submitted successfully.",
        "submitted_at": attempt.submitted_at,
    }


@router.get(
    "/{assignment_id}/result",
    response_model=CandidateAssessmentResultResponse,
)
def get_candidate_result(
    assignment_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """Return submission status only, never the candidate scorecard."""
    assignment = get_owned_assignment(assignment_id, candidate, db)

    attempt = assignment.attempt

    if not attempt or not attempt.is_submitted:
        raise NotFoundException("Assessment Submission")

    return {
        "assignment_id": assignment.id,
        "message": "Your assessment has been submitted successfully.",
        "submitted_at": attempt.submitted_at,
    }
