
import asyncio
import logging

from app.services.proctoring_cleanup import cleanup_expired_recordings

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60


async def run_proctoring_cleanup_scheduler():
    """
    Run expired-recording cleanup once at startup,
    then repeat every 24 hours.
    """

    while True:
        try:
            deleted_count = await asyncio.to_thread(
                cleanup_expired_recordings
            )
            logger.info(
                "Proctoring cleanup completed. Deleted: %s",
                deleted_count,
            )
        except Exception:
            logger.exception("Scheduled proctoring cleanup failed.")

        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
