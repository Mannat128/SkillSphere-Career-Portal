import asyncio
import datetime
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.dependencies import get_current_candidate
from app.models.candidate import Candidate
from app.models.recruiter_assessment import (
    AssessmentAssignment,
    CandidateAssessmentAttempt,
)
from app.models.proctoring import ProctoringSession
from app.models.proctoring_violation import ProctoringViolation
from app.services.computer_vision_service import detect_objects


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/candidate/first-round-assessments",
    tags=["AI Computer Vision Proctoring"],
)

MAX_FRAME_SIZE = 5 * 1024 * 1024
DETECTION_COOLDOWN_SECONDS = 10
MAX_WARNINGS_BEFORE_FLAG = 3
ALLOWED_FRAME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def get_candidate_assignment(
    assignment_id: int,
    candidate: Candidate,
    db: Session,
):
    assignment = (
        db.query(AssessmentAssignment)
        .filter(
            AssessmentAssignment.id == assignment_id,
            AssessmentAssignment.candidate_id == candidate.id,
        )
        .first()
    )

    if not assignment:
        raise HTTPException(
            status_code=404,
            detail="Assessment assignment not found.",
        )

    return assignment


def get_active_attempt(
    assignment_id: int,
    candidate_id: int,
    db: Session,
):
    attempt = (
        db.query(CandidateAssessmentAttempt)
        .filter(
            CandidateAssessmentAttempt.assignment_id == assignment_id,
            CandidateAssessmentAttempt.candidate_id == candidate_id,
        )
        .first()
    )

    if not attempt:
        raise HTTPException(
            status_code=400,
            detail="Start the assessment before using AI proctoring.",
        )

    if attempt.is_submitted:
        raise HTTPException(
            status_code=400,
            detail="The assessment has already been submitted.",
        )

    if datetime.datetime.utcnow() >= attempt.expires_at:
        raise HTTPException(
            status_code=400,
            detail="The assessment duration has expired.",
        )

    return attempt


def get_active_proctoring_session(
    assignment_id: int,
    candidate_id: int,
    db: Session,
):
    session = (
        db.query(ProctoringSession)
        .filter(
            ProctoringSession.assignment_id == assignment_id,
            ProctoringSession.candidate_id == candidate_id,
        )
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Proctoring session not found.",
        )

    if not session.consent_given:
        raise HTTPException(
            status_code=403,
            detail="Proctoring consent is required.",
        )

    if not session.camera_permission_granted:
        raise HTTPException(
            status_code=403,
            detail="Camera permission is required.",
        )

    if session.session_status != "RECORDING":
        raise HTTPException(
            status_code=400,
            detail="The assessment recording is not active.",
        )

    return session


def get_violation_confidence(
    violation_type: str,
    detections: list,
):
    """Return the highest relevant detection confidence, if available."""
    if violation_type == "AI_PHONE_DETECTED":
        matching_label = "cell phone"
    elif violation_type == "AI_MULTIPLE_PEOPLE_DETECTED":
        matching_label = "person"
    else:
        return None

    confidences = []

    for detection in detections:
        label = str(detection.get("label", "")).lower()
        if label != matching_label:
            continue

        confidence = detection.get("confidence")
        if confidence is not None:
            try:
                confidences.append(float(confidence))
            except (TypeError, ValueError):
                continue

    return max(confidences) if confidences else None


@router.post("/{assignment_id}/proctoring/analyze-frame")
async def analyze_proctoring_frame(
    assignment_id: int,
    file: UploadFile = File(...),
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """Analyse one webcam frame in memory; never persist the original frame."""
    image_bytes = None

    try:
        get_candidate_assignment(assignment_id, candidate, db)
        get_active_attempt(assignment_id, candidate.id, db)
        session = get_active_proctoring_session(
            assignment_id,
            candidate.id,
            db,
        )

        content_type = (file.content_type or "").lower().split(";")[0].strip()
        if content_type not in ALLOWED_FRAME_TYPES:
            raise HTTPException(
                status_code=415,
                detail="Only JPEG, PNG and WebP frames are supported.",
            )

        image_bytes = await file.read(MAX_FRAME_SIZE + 1)

        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="Uploaded frame is empty.",
            )

        if len(image_bytes) > MAX_FRAME_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Frame size exceeds the 5 MB limit.",
            )

        try:
            result = await asyncio.to_thread(detect_objects, image_bytes)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc
        except RuntimeError as exc:
            logger.exception("Computer vision processing failed.")
            raise HTTPException(
                status_code=503,
                detail="Computer vision service is temporarily unavailable.",
            ) from exc

        # The frame is discarded before any database update.
        del image_bytes
        image_bytes = None

        # Re-check the persisted state after inference. The recording may have
        # been aborted or the assessment submitted while YOLO was processing.
        db.expire(session)
        session = get_active_proctoring_session(
            assignment_id,
            candidate.id,
            db,
        )
        get_active_attempt(assignment_id, candidate.id, db)

        detected_violations = []
        if result.get("phone_detected"):
            detected_violations.append("AI_PHONE_DETECTED")
        if result.get("multiple_people_detected"):
            detected_violations.append("AI_MULTIPLE_PEOPLE_DETECTED")

        now = datetime.datetime.utcnow()
        warning_recorded = False

        if detected_violations:
            previous_time = session.last_violation_at
            cooldown_passed = (
                previous_time is None
                or (now - previous_time).total_seconds()
                >= DETECTION_COOLDOWN_SECONDS
            )

            if cooldown_passed:
                detections = result.get("detections") or []

                for violation_type in detected_violations:
                    violation_record = ProctoringViolation(
                        proctoring_session_id=session.id,
                        assignment_id=assignment_id,
                        candidate_id=candidate.id,
                        violation_type=violation_type,
                        confidence=get_violation_confidence(
                            violation_type,
                            detections,
                        ),
                        details={
                            "person_count": result.get("person_count", 0),
                            "detections": detections,
                            "source": "YOLO_COMPUTER_VISION",
                            "note": (
                                "AI detection is a review signal only and "
                                "may be inaccurate; it is not conclusive evidence."
                            ),
                        },
                        detected_at=now,
                    )
                    db.add(violation_record)

                # One warning per analysed frame, even with multiple detections.
                session.warning_count = (session.warning_count or 0) + 1
                session.last_violation_type = ",".join(detected_violations)
                session.last_violation_at = now

                if session.warning_count >= MAX_WARNINGS_BEFORE_FLAG:
                    session.is_flagged_for_review = True

                session.updated_at = now

                try:
                    db.commit()
                    warning_recorded = True
                except Exception as exc:
                    db.rollback()
                    logger.exception(
                        "Failed to save proctoring violation history."
                    )
                    raise HTTPException(
                        status_code=500,
                        detail="Unable to save proctoring violation.",
                    ) from exc

        return {
            "message": "Frame analysed successfully.",
            "assignment_id": assignment_id,
            "phone_detected": result.get("phone_detected"),
            "person_count": result.get("person_count"),
            "multiple_people_detected": result.get("multiple_people_detected"),
            "object_detection_available": bool(
                result.get("object_detection_available", True)
            ),
            "face_detected": bool(result.get("face_detected")),
            "face_count": int(result.get("face_count", 0) or 0),
            "looking_away_detected": bool(
                result.get("looking_away_detected")
            ),
            "detected_violations": detected_violations,
            "warning_recorded": warning_recorded,
            "warning_count": session.warning_count or 0,
            "is_flagged_for_review": bool(session.is_flagged_for_review),
            "detections": result.get("detections") or [],
        }

    except HTTPException:
        raise
    finally:
        if image_bytes is not None:
            del image_bytes
        await file.close()
