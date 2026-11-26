
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.proctoring import ProctoringSession
from app.models.recruiter_assessment import AssessmentAssignment
from app.services.recording_retention import recording_expiry_at


logger = logging.getLogger(__name__)


# Must match the private recording directory used by
# backend/app/routers/proctoring.py
PRIVATE_RECORDING_DIR = (
    Path(settings.UPLOAD_DIR).resolve().parent
    / "private_proctoring_recordings"
).resolve()


def cleanup_expired_recordings(db: Session | None = None) -> int:
    """
    Delete completed recordings after their configured retention period.

    Database session metadata and audit history are retained.
    Only files inside the private recording directory are deleted.
    """

    own_session = db is None
    session = db or SessionLocal()

    deleted_count = 0
    now = datetime.utcnow()

    try:
        expired_sessions = (
            session.query(ProctoringSession)
            .options(
                joinedload(ProctoringSession.assignment)
                .joinedload(AssessmentAssignment.attempt)
            )
            .filter(
                ProctoringSession.recording_path.isnot(None),
                ProctoringSession.recording_deleted_at.is_(None),
                ProctoringSession.session_status == "COMPLETED",
            )
            .all()
        )

        for recording in expired_sessions:
            attempt = recording.assignment.attempt if recording.assignment else None
            # Missing submission metadata has no safe substitute. Clear any
            # stale upload-based deadline and preserve the recording for review.
            expiry_at = recording_expiry_at(
                attempt.submitted_at
                if attempt and attempt.is_submitted
                else None
            )
            if recording.delete_after != expiry_at:
                recording.delete_after = expiry_at
                recording.updated_at = now
            if expiry_at is None or expiry_at > now:
                continue

            try:
                from app.services.storage_service import StorageService
                if not StorageService.delete_recording(recording.recording_path):
                    logger.error("Storage deletion failed for recording session %s", recording.id)
                    continue

                recording.recording_path = None
                recording.recording_deleted_at = now
                recording.session_status = "DELETED"
                recording.updated_at = now

                deleted_count += 1

            except Exception:
                logger.exception(
                    "Could not delete recording for session %s",
                    recording.id,
                )

        session.commit()

        logger.info(
            "Expired proctoring recordings deleted: %s",
            deleted_count,
        )

        return deleted_count

    except Exception:
        session.rollback()

        logger.exception(
            "Proctoring recording cleanup failed."
        )

        raise

    finally:
        if own_session:
            session.close()
