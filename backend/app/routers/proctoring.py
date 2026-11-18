
import datetime
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.config import settings
from app.core.dependencies import (
    get_current_candidate,
    get_current_recruiter,
    get_current_admin,
)
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.candidate import Candidate
from app.models.recruiter import Recruiter
from app.models.recruiter_assessment import AssessmentAssignment
from app.models.proctoring import ProctoringSession
from app.models.proctoring_violation import ProctoringViolation
from app.models.audit import AuditLog


# Separate routers are required for correct role-based URLs.
router = APIRouter(
    prefix="/candidate/first-round-assessments",
    tags=["Candidate Proctoring"],
)

recruiter_router = APIRouter(
    prefix="/recruiter/proctoring",
    tags=["Recruiter Proctoring"],
)

admin_router = APIRouter(
    prefix="/admin/proctoring",
    tags=["Admin Proctoring"],
)


MAX_RECORDING_SIZE_MB = 500

ALLOWED_VIDEO_TYPES = {
    "video/webm",
    "video/mp4",
    "video/x-matroska",
}

MAX_WARNINGS_BEFORE_FLAG = 3

PRIVATE_RECORDING_DIR = (
    Path(settings.UPLOAD_DIR).resolve().parent
    / "private_proctoring_recordings"
)


RECORDING_CHUNK_SIZE = 1024 * 1024


def has_valid_video_signature(header: bytes, content_type: str) -> bool:
    """Validate the container signature instead of trusting the upload MIME header."""
    if content_type in {"video/webm", "video/x-matroska"}:
        return header.startswith(bytes.fromhex("1A45DFA3"))

    if content_type == "video/mp4":
        return len(header) >= 8 and header[4:8] == b"ftyp"

    return False


def is_private_recording_path(path: Path) -> bool:
    """Return True only when the resolved file is inside the private recording folder."""
    try:
        resolved_path = path.resolve()
        private_root = PRIVATE_RECORDING_DIR.resolve()
        return private_root in resolved_path.parents
    except (OSError, RuntimeError):
        return False


def is_recording_available(session: ProctoringSession | None, now=None) -> bool:
    if not session or not session.recording_path or session.recording_deleted_at:
        return False

    now = now or datetime.datetime.utcnow()

    if session.delete_after and now >= session.delete_after:
        return False

    path = Path(session.recording_path)

    return is_private_recording_path(path) and path.is_file()


class ProctoringConsentRequest(BaseModel):
    consent_given: bool
    camera_permission_granted: bool
    consent_version: str = "v1"


class ProctoringViolationRequest(BaseModel):
    violation_type: str


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
        raise NotFoundException("Assessment Assignment")

    return assignment


def get_proctoring_session(
    assignment_id: int,
    db: Session,
):
    session = (
        db.query(ProctoringSession)
        .filter(
            ProctoringSession.assignment_id == assignment_id
        )
        .first()
    )

    if not session:
        raise NotFoundException("Proctoring Session")

    return session


def add_audit_log(
    db: Session,
    user_id: int,
    action: str,
    assignment_id: int,
    request: Request,
    details: dict | None = None,
):
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type="proctoring_recording",
        entity_id=assignment_id,
        ip_address=request.client.host if request.client else None,
        details=details or {},
    )

    db.add(log)


def get_authorized_recording(
    assignment_id: int,
    db: Session,
):
    session = get_proctoring_session(assignment_id, db)

    if (
        session.session_status != "COMPLETED"
        or not session.recording_completed_at
        or not session.recording_path
        or session.recording_deleted_at
    ):
        raise NotFoundException("Proctoring Recording")

    if session.delete_after and datetime.datetime.utcnow() >= session.delete_after:
        raise NotFoundException("Proctoring Recording")

    recording_path = Path(session.recording_path).resolve()

    if not is_private_recording_path(recording_path):
        raise HTTPException(
            status_code=403,
            detail="Invalid recording path.",
        )

    if not recording_path.is_file():
        raise NotFoundException("Proctoring Recording")

    return session, recording_path


def get_assignment_for_recruiter(
    assignment_id: int,
    recruiter: Recruiter,
    db: Session,
):
    assignment = (
        db.query(AssessmentAssignment)
        .filter(AssessmentAssignment.id == assignment_id)
        .first()
    )

    if not assignment or not assignment.job:
        raise NotFoundException("Assessment Assignment")

    if assignment.job.recruiter_id != recruiter.id:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to access this candidate.",
        )

    return assignment


def serialize_violation(violation: ProctoringViolation):
    return {
        "id": violation.id,
        "assignment_id": violation.assignment_id,
        "candidate_id": violation.candidate_id,
        "violation_type": violation.violation_type,
        "confidence": violation.confidence,
        "details": violation.details,
        "detected_at": violation.detected_at,
    }


# ---------------------------------------------------------
# CANDIDATE ROUTES
# ---------------------------------------------------------

@router.post("/{assignment_id}/proctoring/consent")
def save_proctoring_consent(
    assignment_id: int,
    request: ProctoringConsentRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    if not request.consent_given:
        raise BadRequestException(
            "You must accept the proctoring consent before continuing."
        )

    if not request.camera_permission_granted:
        raise BadRequestException(
            "Camera permission is required before starting the assessment."
        )

    assignment = get_candidate_assignment(
        assignment_id, candidate, db
    )

    if assignment.attempt and assignment.attempt.is_submitted:
        raise BadRequestException(
            "This assessment has already been submitted."
        )

    now = datetime.datetime.utcnow()

    session = (
        db.query(ProctoringSession)
        .filter(ProctoringSession.assignment_id == assignment_id)
        .first()
    )

    if session:
        if session.recording_path and not session.recording_deleted_at:
            raise BadRequestException(
                "A proctoring recording already exists for this assessment."
            )

        session.candidate_id = candidate.id
        session.consent_given = True
        session.consent_version = request.consent_version
        session.consented_at = now
        session.camera_permission_granted = True
        session.session_status = "READY"
        session.updated_at = now

    else:
        session = ProctoringSession(
            assignment_id=assignment_id,
            candidate_id=candidate.id,
            consent_given=True,
            consent_version=request.consent_version,
            consented_at=now,
            camera_permission_granted=True,
            session_status="READY",
        )

        db.add(session)

    db.commit()
    db.refresh(session)

    return {
        "message": "Proctoring consent saved successfully.",
        "assignment_id": assignment_id,
        "consent_given": session.consent_given,
        "camera_permission_granted": session.camera_permission_granted,
        "session_status": session.session_status,
        "consented_at": session.consented_at,
    }


@router.post("/{assignment_id}/proctoring/recording/start")
def start_recording(
    assignment_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    assignment = get_candidate_assignment(
        assignment_id, candidate, db
    )

    if not assignment.attempt:
        raise BadRequestException(
            "Start the assessment before starting proctoring recording."
        )

    if assignment.attempt.is_submitted:
        raise BadRequestException(
            "This assessment has already been submitted."
        )

    session = get_proctoring_session(assignment_id, db)

    if not session.consent_given or not session.camera_permission_granted:
        raise BadRequestException("Proctoring consent is required.")

    if session.recording_path and not session.recording_deleted_at:
        raise BadRequestException(
            "A recording already exists for this assessment."
        )

    if session.session_status == "RECORDING":
        raise BadRequestException(
            "A recording session is already active."
        )

    now = datetime.datetime.utcnow()

    session.recording_started_at = now
    session.recording_completed_at = None
    session.session_status = "RECORDING"
    session.updated_at = now

    db.commit()

    return {
        "message": "Recording session started.",
        "assignment_id": assignment_id,
        "recording_started_at": now,
        "session_status": session.session_status,
    }


@router.post("/{assignment_id}/proctoring/recording/abort")
def abort_recording(
    assignment_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """
    Reset a recording session when browser-side recording initialization fails.
    This endpoint never deletes or resets an uploaded recording.
    """
    assignment = get_candidate_assignment(
        assignment_id, candidate, db
    )

    attempt = assignment.attempt
    if not attempt:
        raise BadRequestException(
            "Start the assessment before resetting its recording session."
        )

    if attempt.is_submitted:
        raise BadRequestException(
            "This assessment has already been submitted."
        )

    if datetime.datetime.utcnow() >= attempt.expires_at:
        raise BadRequestException(
            "Assessment duration has expired. Recording cannot be restarted."
        )

    session = get_proctoring_session(assignment_id, db)

    if not session.consent_given or not session.camera_permission_granted:
        raise BadRequestException("Proctoring consent is required.")

    # Never allow this recovery route to alter an uploaded recording.
    if session.recording_path and not session.recording_deleted_at:
        raise BadRequestException(
            "An uploaded recording already exists and cannot be reset."
        )

    # Idempotent response: a retry after a successful abort is harmless.
    if session.session_status == "READY":
        return {
            "message": "Recording session is ready to be started.",
            "assignment_id": assignment_id,
            "session_status": session.session_status,
        }

    if session.session_status != "RECORDING":
        raise BadRequestException(
            "There is no active recording session to reset."
        )

    now = datetime.datetime.utcnow()
    session.session_status = "READY"
    session.recording_started_at = None
    session.recording_completed_at = None
    session.recording_filename = None
    session.recording_mime_type = None
    session.recording_size_bytes = None
    session.recording_path = None
    session.delete_after = None
    session.recording_deleted_at = None
    session.updated_at = now

    db.commit()
    db.refresh(session)

    return {
        "message": "Recording session reset. You can try starting it again.",
        "assignment_id": assignment_id,
        "session_status": session.session_status,
    }


@router.post("/{assignment_id}/proctoring/recording/upload")
async def upload_recording(
    assignment_id: int,
    file: UploadFile = File(...),
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    assignment = get_candidate_assignment(
        assignment_id, candidate, db
    )

    session = get_proctoring_session(assignment_id, db)

    if not assignment.attempt:
        raise BadRequestException(
            "Start the assessment before uploading its recording."
        )

    if assignment.attempt.is_submitted:
        raise BadRequestException(
            "This assessment has already been submitted."
        )

    if not session.consent_given or not session.camera_permission_granted:
        raise BadRequestException("Proctoring consent is required.")

    if not session.recording_started_at or session.session_status != "RECORDING":
        raise BadRequestException(
            "Start the recording session before uploading."
        )

    if session.recording_path and not session.recording_deleted_at:
        raise BadRequestException(
            "A recording has already been uploaded."
        )

    content_type = (file.content_type or "").lower()

    if content_type not in ALLOWED_VIDEO_TYPES:
        raise BadRequestException(
            "Unsupported recording format. Use WebM or MP4."
        )

    extension = {
        "video/webm": ".webm",
        "video/mp4": ".mp4",
        "video/x-matroska": ".mkv",
    }[content_type]

    max_bytes = MAX_RECORDING_SIZE_MB * 1024 * 1024
    PRIVATE_RECORDING_DIR.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid.uuid4().hex}{extension}"
    recording_path = PRIVATE_RECORDING_DIR / stored_filename
    total_bytes = 0
    signature = bytearray()

    try:
        # Stream to disk in bounded chunks; never load a 500 MB recording into RAM.
        with recording_path.open("xb") as output:
            while True:
                chunk = await file.read(RECORDING_CHUNK_SIZE)
                if not chunk:
                    break

                total_bytes += len(chunk)

                if total_bytes > max_bytes:
                    raise BadRequestException(
                        f"Recording size cannot exceed {MAX_RECORDING_SIZE_MB} MB."
                    )

                if len(signature) < 16:
                    needed = 16 - len(signature)
                    signature.extend(chunk[:needed])

                output.write(chunk)

        if total_bytes == 0:
            raise BadRequestException("The uploaded recording is empty.")

        if not has_valid_video_signature(bytes(signature), content_type):
            raise BadRequestException(
                "The uploaded file does not match its declared video format."
            )

        now = datetime.datetime.utcnow()

        session.recording_filename = file.filename or stored_filename
        session.recording_path = str(recording_path.resolve())
        session.recording_mime_type = content_type
        session.recording_size_bytes = total_bytes
        session.recording_completed_at = now
        session.delete_after = now + datetime.timedelta(days=30)
        session.recording_deleted_at = None
        session.session_status = "COMPLETED"
        session.updated_at = now

        db.commit()

    except Exception:
        db.rollback()

        if recording_path.exists():
            recording_path.unlink()

        raise

    finally:
        await file.close()

    return {
        "message": "Recording uploaded securely.",
        "assignment_id": assignment_id,
        "recording_status": session.session_status,
        "recording_size_bytes": session.recording_size_bytes,
        "delete_after": session.delete_after,
    }


@router.post("/{assignment_id}/proctoring/violation")
def record_proctoring_violation(
    assignment_id: int,
    request: ProctoringViolationRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    allowed_violations = {
        "TAB_SWITCH",
        "WINDOW_BLUR",
        "FULLSCREEN_EXIT",
        "CAMERA_DISCONNECTED",
        "RECORDING_STOPPED",
    }

    violation_type = request.violation_type.strip().upper()

    if violation_type not in allowed_violations:
        raise BadRequestException(
            "Invalid proctoring violation type."
        )

    assignment = get_candidate_assignment(
        assignment_id, candidate, db
    )

    if assignment.attempt and assignment.attempt.is_submitted:
        raise BadRequestException(
            "This assessment has already been submitted."
        )

    session = get_proctoring_session(assignment_id, db)

    if not session.consent_given or not session.camera_permission_granted:
        raise BadRequestException("Proctoring consent is required.")

    if session.session_status != "RECORDING":
        raise BadRequestException(
            "Proctoring violations can only be recorded during an active session."
        )

    now = datetime.datetime.utcnow()

    session.warning_count = (session.warning_count or 0) + 1
    session.last_violation_type = violation_type
    session.last_violation_at = now

    if session.warning_count >= MAX_WARNINGS_BEFORE_FLAG:
        session.is_flagged_for_review = True

    session.updated_at = now

    # Save browser-reported violations in the same history table.
    history_record = ProctoringViolation(
        proctoring_session_id=session.id,
        assignment_id=assignment.id,
        candidate_id=candidate.id,
        violation_type=violation_type,
        confidence=None,
        details={"source": "BROWSER_PROCTORING"},
        detected_at=now,
    )

    db.add(history_record)
    db.commit()

    return {
        "message": "Proctoring warning recorded.",
        "warning_count": session.warning_count,
        "is_flagged_for_review": session.is_flagged_for_review,
        "last_violation_type": session.last_violation_type,
    }


@router.get("/{assignment_id}/proctoring/status")
def get_proctoring_status(
    assignment_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    get_candidate_assignment(assignment_id, candidate, db)

    session = get_proctoring_session(assignment_id, db)

    return {
        "assignment_id": assignment_id,
        "session_status": session.session_status,
        "consent_given": session.consent_given,
        "camera_permission_granted": session.camera_permission_granted,
        "warning_count": session.warning_count,
        "is_flagged_for_review": session.is_flagged_for_review,
        "last_violation_type": session.last_violation_type,
    }


# ---------------------------------------------------------
# RECRUITER ROUTES
# ---------------------------------------------------------

@recruiter_router.get("/assignments/{assignment_id}/recording")
def recruiter_view_recording(
    assignment_id: int,
    request: Request,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db),
):
    get_assignment_for_recruiter(assignment_id, recruiter, db)

    session, recording_path = get_authorized_recording(
        assignment_id, db
    )

    if session.delete_after and datetime.datetime.utcnow() >= session.delete_after:
        raise NotFoundException("Proctoring Recording")

    add_audit_log(
        db=db,
        user_id=recruiter.user_id,
        action="PROCTORING_RECORDING_ACCESSED",
        assignment_id=assignment_id,
        request=request,
        details={"access_role": "RECRUITER"},
    )

    db.commit()

    return FileResponse(
        path=str(recording_path),
        media_type=session.recording_mime_type or "application/octet-stream",
        filename=session.recording_filename or recording_path.name,
        headers={"Cache-Control": "private, no-store", "Pragma": "no-cache"},
    )


@recruiter_router.get("/assignments/{assignment_id}/violations")
def recruiter_view_violations(
    assignment_id: int,
    request: Request,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db),
):
    assignment = get_assignment_for_recruiter(
        assignment_id, recruiter, db
    )

    session = get_proctoring_session(assignment_id, db)

    violations = (
        db.query(ProctoringViolation)
        .filter(
            ProctoringViolation.assignment_id == assignment.id,
            ProctoringViolation.candidate_id == assignment.candidate_id,
        )
        .order_by(ProctoringViolation.detected_at.desc())
        .all()
    )

    add_audit_log(
        db=db,
        user_id=recruiter.user_id,
        action="PROCTORING_VIOLATION_HISTORY_ACCESSED",
        assignment_id=assignment_id,
        request=request,
        details={"access_role": "RECRUITER"},
    )

    db.commit()

    return {
        "assignment_id": assignment_id,
        "warning_count": session.warning_count or 0,
        "is_flagged_for_review": bool(session.is_flagged_for_review),
        "violations": [
            serialize_violation(item) for item in violations
        ],
    }


# ---------------------------------------------------------
# ADMIN ROUTES
# ---------------------------------------------------------

@admin_router.get("/assignments/{assignment_id}/recording")
def admin_view_recording(
    assignment_id: int,
    request: Request,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    session, recording_path = get_authorized_recording(
        assignment_id, db
    )

    if session.delete_after and datetime.datetime.utcnow() >= session.delete_after:
        raise NotFoundException("Proctoring Recording")

    add_audit_log(
        db=db,
        user_id=admin.id,
        action="PROCTORING_RECORDING_ACCESSED",
        assignment_id=assignment_id,
        request=request,
        details={"access_role": "ADMIN"},
    )

    db.commit()

    return FileResponse(
        path=str(recording_path),
        media_type=session.recording_mime_type or "application/octet-stream",
        filename=session.recording_filename or recording_path.name,
        headers={"Cache-Control": "private, no-store", "Pragma": "no-cache"},
    )


@admin_router.get("/assignments/{assignment_id}/violations")
def admin_view_violations(
    assignment_id: int,
    request: Request,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    session = get_proctoring_session(assignment_id, db)

    violations = (
        db.query(ProctoringViolation)
        .filter(
            ProctoringViolation.assignment_id == assignment_id
        )
        .order_by(ProctoringViolation.detected_at.desc())
        .all()
    )

    add_audit_log(
        db=db,
        user_id=admin.id,
        action="PROCTORING_VIOLATION_HISTORY_ACCESSED",
        assignment_id=assignment_id,
        request=request,
        details={"access_role": "ADMIN"},
    )

    db.commit()

    return {
        "assignment_id": assignment_id,
        "warning_count": session.warning_count or 0,
        "is_flagged_for_review": bool(session.is_flagged_for_review),
        "violations": [
            serialize_violation(item) for item in violations
        ],
    }

@admin_router.get("/sessions")
def admin_list_proctoring_sessions(
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    now = datetime.datetime.utcnow()

    records = (
        db.query(AssessmentAssignment, ProctoringSession)
        .outerjoin(
            ProctoringSession,
            ProctoringSession.assignment_id == AssessmentAssignment.id,
        )
        .order_by(AssessmentAssignment.assigned_at.desc())
        .all()
    )

    results = []

    for assignment, session in records:
        candidate = assignment.candidate
        user = candidate.user if candidate else None
        job = assignment.job

        recording_available = is_recording_available(session, now)

        results.append({
            "assignment_id": assignment.id,
            "candidate_id": assignment.candidate_id,
            "candidate_name": user.full_name if user else None,
            "candidate_email": user.email if user else None,
            "job_title": job.title if job else None,
            "assessment_status": assignment.status,
            "session_status": (
                session.session_status if session else "NOT_STARTED"
            ),
            "consent_given": (
                bool(session.consent_given) if session else False
            ),
            "recording_available": recording_available,
            "recording_deleted": (
                bool(session.recording_deleted_at) if session else False
            ),
            "warning_count": (
                session.warning_count or 0 if session else 0
            ),
            "is_flagged_for_review": (
                bool(session.is_flagged_for_review) if session else False
            ),
            "assigned_at": assignment.assigned_at,
            "recording_completed_at": (
                session.recording_completed_at if session else None
            ),
        })

    return {
        "total": len(results),
        "sessions": results,
    }
