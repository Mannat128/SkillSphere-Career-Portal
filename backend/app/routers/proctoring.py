
import datetime
import hashlib
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
    get_current_user,
    oauth2_scheme,
)
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.candidate import Candidate
from app.models.recruiter import Recruiter
from app.models.recruiter_assessment import AssessmentAssignment
from app.models.proctoring import ProctoringSession
from app.models.proctoring_violation import ProctoringViolation
from app.models.audit import AuditLog
from app.services.recording_retention import recording_expiry_at, sync_recording_expiry
from app.routers.candidate_assessments import ensure_assessment_available


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

    if is_recording_expired(session, now):
        return False

    from app.services.storage_service import StorageService
    return StorageService.is_file_available(session.recording_path)


def is_recording_expired(session: ProctoringSession, now=None) -> bool:
    now = now or datetime.datetime.utcnow()
    assignment = getattr(session, "assignment", None)
    attempt = getattr(assignment, "attempt", None) if assignment else None
    if not attempt or not attempt.is_submitted or not attempt.submitted_at:
        return True
    expires_at = recording_expiry_at(attempt.submitted_at)
    return now >= expires_at


class ProctoringConsentRequest(BaseModel):
    consent_given: bool
    camera_permission_granted: bool
    microphone_permission_granted: bool = False
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
    for_update: bool = False,
):
    query = (
        db.query(ProctoringSession)
        .filter(
            ProctoringSession.assignment_id == assignment_id
        )
    )
    if for_update:
        query = query.with_for_update()
    session = query.first()

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


def audit_recording_event(
    db: Session,
    request: Request,
    assignment_id: int,
    user_id: int | None,
    role: str,
    action: str,
    outcome: str,
    session_id: int | None = None,
    status_code: int | None = None,
):
    """Persist a recording access event without storing URLs, tokens, or secrets."""
    occurred_at = datetime.datetime.utcnow()
    details = {
        "role": role,
        "outcome": outcome,
        "recording_session_id": session_id,
        "timestamp": occurred_at.isoformat() + "Z",
    }
    if status_code is not None:
        details["status_code"] = status_code
    db.add(AuditLog(
        user_id=user_id,
        action=action,
        entity_type="proctoring_recording",
        entity_id=assignment_id,
        ip_address=request.client.host if request.client else None,
        details=details,
        created_at=occurred_at,
    ))
    db.commit()


def audit_failed_recording_request(
    db: Session,
    request: Request,
    assignment_id: int,
    user_id: int | None,
    role: str,
    error: HTTPException,
):
    session_id = None
    try:
        session_id = db.query(ProctoringSession.id).filter(
            ProctoringSession.assignment_id == assignment_id
        ).scalar()
    except Exception:
        # The denied/invalid request still gets an audit row when session lookup fails.
        db.rollback()
    forbidden = error.status_code == 403
    audit_recording_event(
        db=db,
        request=request,
        assignment_id=assignment_id,
        user_id=user_id,
        role=role,
        action="PROCTORING_RECORDING_ACCESS_DENIED" if forbidden else "PROCTORING_RECORDING_ACCESS_FAILED",
        outcome="denied" if forbidden else "failed",
        session_id=session_id,
        status_code=error.status_code,
    )


def get_recording_actor(request: Request, db: Session, token: str, required_role: str):
    """Authenticate recording viewers here so authentication/role denials are audited too."""
    assignment_id = request.path_params.get("assignment_id")
    try:
        assignment_id = int(assignment_id) if assignment_id is not None else 0
        user = get_current_user(token=token, db=db)
    except HTTPException as exc:
        audit_failed_recording_request(db, request, assignment_id or 0, None, required_role, exc)
        raise

    actual_role = getattr(user.role, "value", str(user.role)).upper()
    if actual_role != required_role:
        error = HTTPException(status_code=403, detail="You are not authorized to access proctoring recordings.")
        audit_failed_recording_request(db, request, assignment_id or 0, user.id, actual_role, error)
        raise error

    if required_role == "RECRUITER":
        recruiter = db.query(Recruiter).filter(Recruiter.user_id == user.id).first()
        if not recruiter:
            error = HTTPException(status_code=403, detail="Recruiter profile not found.")
            audit_failed_recording_request(db, request, assignment_id or 0, user.id, actual_role, error)
            raise error
        return recruiter
    return user


def get_recording_recruiter(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return get_recording_actor(request, db, token, "RECRUITER")


def get_recording_admin(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return get_recording_actor(request, db, token, "ADMIN")


def create_recording_playback_link(
    assignment_id: int,
    request: Request,
    user_id: int,
    access_role: str,
    db: Session,
    attachment: bool = False,
):
    try:
        session, recording_path = get_authorized_recording(assignment_id, db)
    except HTTPException as exc:
        audit_failed_recording_request(db, request, assignment_id, user_id, access_role, exc)
        raise
    if not isinstance(recording_path, str) or not recording_path.startswith(("cloudinary://", "s3://")):
        return {"url": None, "expires_in_seconds": 600}

    from app.services.storage_service import StorageService
    try:
        if recording_path.startswith("cloudinary://"):
            asset_format = session.cloudinary_format or (session.recording_mime_type or "video/webm").split("/")[-1]
            signed_url = StorageService.get_access_url(
                recording_path,
                expires_in_seconds=600,
                asset_format=asset_format,
                attachment=attachment,
            )
        else:
            signed_url = StorageService.get_access_url(
                recording_path,
                expires_in_seconds=600,
                attachment=attachment,
            )
    except Exception as exc:
        audit_recording_event(
            db, request, assignment_id, user_id, access_role,
            "PROCTORING_RECORDING_SIGNED_URL_GENERATION_FAILED", "failed", session.id, 502,
        )
        raise

    audit_recording_event(
        db, request, assignment_id, user_id, access_role,
        "PROCTORING_RECORDING_SIGNED_URL_GENERATED" if not attachment else "PROCTORING_RECORDING_DOWNLOAD_URL_GENERATED",
        "success", session.id,
    )
    return {
        "url": signed_url,
        "expires_in_seconds": 600,
        "expires_at": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10),
    }


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

    if is_recording_expired(session):
        raise NotFoundException("Proctoring Recording")

    if session.recording_path.startswith(("s3://", "cloudinary://")):
        from app.services.storage_service import StorageService
        if not StorageService.is_file_available(session.recording_path):
            raise NotFoundException("Proctoring Recording")
        return session, session.recording_path

    recording_path = Path(session.recording_path).resolve()

    if not is_private_recording_path(recording_path):
        raise HTTPException(
            status_code=403,
            detail="Invalid recording path.",
        )

    if not recording_path.is_file():
        raise NotFoundException("Proctoring Recording")

    return session, recording_path


def ensure_recording_upload_allowed(session: ProctoringSession) -> None:
    if session.recording_path and not session.recording_deleted_at:
        raise BadRequestException("A recording has already been uploaded.")
    if not session.recording_started_at or session.session_status != "RECORDING":
        raise BadRequestException("Start the recording session before uploading.")


def persist_recording_storage_metadata(session: ProctoringSession, metadata: dict) -> None:
    session.recording_path = metadata["storage_reference"]
    session.recording_provider = metadata.get("provider")
    session.cloudinary_asset_id = metadata.get("asset_id")
    session.cloudinary_public_id = metadata.get("public_id")
    session.cloudinary_version = metadata.get("version")
    session.cloudinary_format = metadata.get("format")
    session.cloudinary_resource_type = metadata.get("resource_type")
    session.cloudinary_delivery_type = metadata.get("delivery_type")


def recording_metadata_matches(
    session: ProctoringSession | None,
    metadata: dict,
    content_type: str,
    size_bytes: int,
    assessment_submitted_at: datetime.datetime | None = None,
) -> bool:
    """Confirm a commit with an ambiguous response actually persisted all recording metadata."""
    if not session or session.session_status != "COMPLETED" or not session.recording_completed_at:
        return False
    return all((
        session.recording_path == metadata.get("storage_reference"),
        session.recording_provider == metadata.get("provider"),
        session.cloudinary_asset_id == metadata.get("asset_id"),
        session.cloudinary_public_id == metadata.get("public_id"),
        session.cloudinary_version == metadata.get("version"),
        session.cloudinary_format == metadata.get("format"),
        session.cloudinary_resource_type == metadata.get("resource_type"),
        session.cloudinary_delivery_type == metadata.get("delivery_type"),
        session.recording_mime_type == content_type,
        session.recording_size_bytes == size_bytes,
        session.delete_after == recording_expiry_at(assessment_submitted_at),
        session.recording_deleted_at is None,
    ))


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
    if not request.microphone_permission_granted:
        raise BadRequestException("Microphone permission is required for proctoring audio.")

    assignment = get_candidate_assignment(
        assignment_id, candidate, db
    )

    # Consent is part of assessment access. Reject it server-side outside the
    # configured UTC window, even when a client bypasses the instructions UI.
    ensure_assessment_available(
        assignment.config_snapshot or {}, datetime.datetime.utcnow()
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
        session.camera_permission_granted = request.camera_permission_granted
        session.microphone_permission_granted = request.microphone_permission_granted
        session.session_status = "READY"
        session.updated_at = now

    else:
        session = ProctoringSession(
            assignment_id=assignment_id,
            candidate_id=candidate.id,
            consent_given=True,
            consent_version=request.consent_version,
            consented_at=now,
            camera_permission_granted=request.camera_permission_granted,
            microphone_permission_granted=request.microphone_permission_granted,
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

    now = datetime.datetime.utcnow()
    ensure_assessment_available(assignment.config_snapshot or {}, now)
    if now >= assignment.attempt.expires_at:
        raise BadRequestException(
            "Assessment duration has expired. Recording cannot be started."
        )

    session = get_proctoring_session(assignment_id, db)

    if not session.consent_given or not session.camera_permission_granted or not session.microphone_permission_granted:
        raise BadRequestException("Proctoring consent is required.")

    if session.recording_path and not session.recording_deleted_at:
        raise BadRequestException(
            "A recording already exists for this assessment."
        )

    if session.session_status == "RECORDING":
        raise BadRequestException(
            "A recording session is already active."
        )

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

    if not session.consent_given or not session.camera_permission_granted or not session.microphone_permission_granted:
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

    session = get_proctoring_session(assignment_id, db, for_update=True)

    if not assignment.attempt:
        raise BadRequestException(
            "Start the assessment before uploading its recording."
        )

    if assignment.attempt.is_submitted:
        raise BadRequestException(
            "This assessment has already been submitted."
        )

    if not session.consent_given or not session.camera_permission_granted or not session.microphone_permission_granted:
        raise BadRequestException("Proctoring consent is required.")

    ensure_recording_upload_allowed(session)

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
    stored_metadata = None
    upload_digest = hashlib.sha256()

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
                upload_digest.update(chunk)

        if total_bytes == 0:
            raise BadRequestException("The uploaded recording is empty.")

        if not has_valid_video_signature(bytes(signature), content_type):
            raise BadRequestException(
                "The uploaded file does not match its declared video format."
            )

        from app.services.storage_service import StorageService
        stored_metadata = StorageService.save_recording_with_metadata(
            source_path=recording_path,
            destination_filename=stored_filename,
            content_type=content_type,
            idempotency_key=f"assessment-{assignment_id}",
            content_sha256=upload_digest.hexdigest(),
        )
        stored_reference = stored_metadata["storage_reference"]

        now = datetime.datetime.utcnow()

        session.recording_filename = file.filename or stored_filename
        persist_recording_storage_metadata(session, stored_metadata)
        session.recording_mime_type = content_type
        session.recording_size_bytes = total_bytes
        session.recording_completed_at = now
        # A recording can exist before assessment submission. Keep expiry unset
        # until the attempt's authoritative submitted_at is available.
        sync_recording_expiry(session, assignment.attempt)
        session.recording_deleted_at = None
        session.session_status = "COMPLETED"
        session.updated_at = now

        try:
            db.commit()
        except Exception:
            # Commit responses can be lost after the database committed. Read
            # the row back and report success only if the whole metadata set is
            # persisted; otherwise preserve Cloudinary for a stable-ID retry.
            db.rollback()
            persisted = db.query(ProctoringSession).filter(
                ProctoringSession.assignment_id == assignment_id
            ).first()
            if not recording_metadata_matches(
                persisted,
                stored_metadata,
                content_type,
                total_bytes,
                assignment.attempt.submitted_at if assignment.attempt and assignment.attempt.is_submitted else None,
            ):
                raise
            session = persisted

    except Exception:
        db.rollback()

        # Do not delete the Cloudinary object on commit exceptions: some database
        # drivers can report a lost commit response after the transaction landed.
        # The stable upload ID + content fingerprint lets a retry reconcile it.

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
        "MICROPHONE_DISCONNECTED",
        "RECORDING_FAILURE",
        "RECORDING_STOPPED",
        "AI_NO_FACE_DETECTED",
        "AI_LOOKING_AWAY_DETECTED",
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

    if not session.consent_given or not session.camera_permission_granted or not session.microphone_permission_granted:
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
    recruiter: Recruiter = Depends(get_recording_recruiter),
    db: Session = Depends(get_db),
):
    try:
        get_assignment_for_recruiter(assignment_id, recruiter, db)
        session, recording_path = get_authorized_recording(assignment_id, db)
    except HTTPException as exc:
        audit_failed_recording_request(db, request, assignment_id, recruiter.user_id, "RECRUITER", exc)
        raise

    if isinstance(recording_path, str) and recording_path.startswith(("s3://", "cloudinary://")):
        from app.services.storage_service import StorageService
        from fastapi.responses import RedirectResponse
        try:
            if recording_path.startswith("cloudinary://"):
                file_format = session.cloudinary_format or (session.recording_mime_type or "video/webm").split("/")[-1]
                signed_url = StorageService.get_access_url(recording_path, expires_in_seconds=600, asset_format=file_format)
            else:
                signed_url = StorageService.get_access_url(recording_path, expires_in_seconds=600)
        except Exception:
            audit_recording_event(db, request, assignment_id, recruiter.user_id, "RECRUITER", "PROCTORING_RECORDING_SIGNED_URL_GENERATION_FAILED", "failed", session.id, 502)
            raise
        audit_recording_event(db, request, assignment_id, recruiter.user_id, "RECRUITER", "PROCTORING_RECORDING_ACCESSED", "success", session.id)
        return RedirectResponse(url=signed_url, status_code=307, headers={"Cache-Control": "private, no-store"})

    audit_recording_event(db, request, assignment_id, recruiter.user_id, "RECRUITER", "PROCTORING_RECORDING_ACCESSED", "success", session.id)
    return FileResponse(
        path=str(recording_path),
        media_type=session.recording_mime_type or "application/octet-stream",
        filename=session.recording_filename or (recording_path.name if hasattr(recording_path, "name") else "recording.webm"),
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


@recruiter_router.get("/assignments/{assignment_id}/recording-url")
def recruiter_recording_playback_url(
    assignment_id: int,
    request: Request,
    attachment: bool = False,
    recruiter: Recruiter = Depends(get_recording_recruiter),
    db: Session = Depends(get_db),
):
    try:
        get_assignment_for_recruiter(assignment_id, recruiter, db)
    except HTTPException as exc:
        audit_failed_recording_request(db, request, assignment_id, recruiter.user_id, "RECRUITER", exc)
        raise
    return create_recording_playback_link(
        assignment_id, request, recruiter.user_id, "RECRUITER", db, attachment
    )


# ---------------------------------------------------------
# ADMIN ROUTES
# ---------------------------------------------------------

@admin_router.get("/assignments/{assignment_id}/recording")
def admin_view_recording(
    assignment_id: int,
    request: Request,
    admin=Depends(get_recording_admin),
    db: Session = Depends(get_db),
):
    try:
        session, recording_path = get_authorized_recording(assignment_id, db)
    except HTTPException as exc:
        audit_failed_recording_request(db, request, assignment_id, admin.id, "ADMIN", exc)
        raise

    if isinstance(recording_path, str) and recording_path.startswith(("s3://", "cloudinary://")):
        from app.services.storage_service import StorageService
        from fastapi.responses import RedirectResponse
        try:
            if recording_path.startswith("cloudinary://"):
                file_format = session.cloudinary_format or (session.recording_mime_type or "video/webm").split("/")[-1]
                signed_url = StorageService.get_access_url(recording_path, expires_in_seconds=600, asset_format=file_format)
            else:
                signed_url = StorageService.get_access_url(recording_path, expires_in_seconds=600)
        except Exception:
            audit_recording_event(db, request, assignment_id, admin.id, "ADMIN", "PROCTORING_RECORDING_SIGNED_URL_GENERATION_FAILED", "failed", session.id, 502)
            raise
        audit_recording_event(db, request, assignment_id, admin.id, "ADMIN", "PROCTORING_RECORDING_ACCESSED", "success", session.id)
        return RedirectResponse(url=signed_url, status_code=307, headers={"Cache-Control": "private, no-store"})

    audit_recording_event(db, request, assignment_id, admin.id, "ADMIN", "PROCTORING_RECORDING_ACCESSED", "success", session.id)
    return FileResponse(
        path=str(recording_path),
        media_type=session.recording_mime_type or "application/octet-stream",
        filename=session.recording_filename or (recording_path.name if hasattr(recording_path, "name") else "recording.webm"),
        headers={"Cache-Control": "private, no-store", "Pragma": "no-cache"},
    )


@admin_router.get("/assignments/{assignment_id}/recording-url")
def admin_recording_playback_url(
    assignment_id: int,
    request: Request,
    attachment: bool = False,
    admin=Depends(get_recording_admin),
    db: Session = Depends(get_db),
):
    return create_recording_playback_link(
        assignment_id, request, admin.id, "ADMIN", db, attachment
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
