"""Assessment-submission-based proctoring recording retention helpers."""

from datetime import datetime, timedelta

from app.core.config import settings


def recording_expiry_at(submitted_at: datetime | None) -> datetime | None:
    """Return the configured expiry from assessment submission, never upload time."""
    if submitted_at is None:
        return None
    retention_days = max(1, int(settings.RECORDING_RETENTION_DAYS))
    return submitted_at + timedelta(days=retention_days)


def assessment_submission_at(attempt) -> datetime | None:
    """Only a submitted attempt with its authoritative timestamp can expire media."""
    if not attempt or not attempt.is_submitted:
        return None
    return attempt.submitted_at


def sync_recording_expiry(proctoring_session, attempt=None) -> datetime | None:
    """Persist the expiry derived from the attempt's immutable submitted_at."""
    if attempt is None:
        assignment = getattr(proctoring_session, "assignment", None)
        attempt = getattr(assignment, "attempt", None) if assignment else None
    expiry_at = recording_expiry_at(assessment_submission_at(attempt))
    proctoring_session.delete_after = expiry_at
    return expiry_at
