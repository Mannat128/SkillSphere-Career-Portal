
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.proctoring import ProctoringSession


logger = logging.getLogger(__name__)


# Must match the private recording directory used by
# backend/app/routers/proctoring.py
PRIVATE_RECORDING_DIR = (
    Path(settings.UPLOAD_DIR).resolve().parent
    / "private_proctoring_recordings"
).resolve()


def cleanup_expired_recordings(db: Session | None = None) -> int:
    """
    Delete recordings whose 30-day retention period has expired.

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
            .filter(
                ProctoringSession.delete_after.isnot(None),
                ProctoringSession.delete_after <= now,
                ProctoringSession.recording_path.isnot(None),
                ProctoringSession.recording_deleted_at.is_(None),
            )
            .all()
        )

        for recording in expired_sessions:
            try:
                path = Path(
                    recording.recording_path
                ).resolve()

                # Prevent deletion outside the private folder.
                if PRIVATE_RECORDING_DIR not in path.parents:
                    logger.error(
                        "Skipped unsafe recording path for session %s",
                        recording.id,
                    )
                    continue

                if path.exists():
                    if not path.is_file():
                        logger.error(
                            "Recording path is not a file for session %s",
                            recording.id,
                        )
                        continue

                    path.unlink()

                recording.recording_path = None
                recording.recording_deleted_at = now
                recording.session_status = "DELETED"
                recording.updated_at = now

                deleted_count += 1

            except OSError:
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
