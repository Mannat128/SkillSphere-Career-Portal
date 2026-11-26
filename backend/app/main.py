
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.database.session import SessionLocal
from app.services.init_db import init_db
from app.services.proctoring_scheduler import (
    run_proctoring_cleanup_scheduler,
)

from app.routers import (
    auth,
    candidate,
    resumes,
    jobs,
    applications,
    matching,
    interviews,
    assessments,
    recruiter,
    admin,
    notifications,
    question_bank,
    recruiter_assessments,
    candidate_assessments,
    assessment_reviews,
    proctoring,
    support_tickets,
    support_ticket_admin,
    computer_vision,
    assistant,
    recruiter_ai,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
# HTTPX INFO records include complete request URLs. Some providers place
# signatures/API identifiers in query parameters, so keep request URLs out of
# application logs. Provider-specific service code emits sanitized status logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("SkillSphere")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SkillSphere Backend Application...")

    db = SessionLocal()

    try:
        init_db(db)
    except Exception:
        logger.exception("Error during database initialization.")
    finally:
        db.close()

    cleanup_task = asyncio.create_task(
        run_proctoring_cleanup_scheduler()
    )

    yield

    logger.info("Shutting down SkillSphere Backend Application...")

    cleanup_task.cancel()

    try:
        await cleanup_task
    except asyncio.CancelledError:
        logger.info("Proctoring cleanup scheduler stopped.")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Full-stack Career & Job Portal REST API with Resume OCR, "
        "AI Matching, Recruitment Analytics, AI Proctoring "
        "and the SkillSphere Assistant."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# Ensure private directories (recordings and support attachments) are safely created
PRIVATE_RECORDING_DIR = (
    os.path.join(os.path.dirname(os.path.abspath(settings.UPLOAD_DIR)), "private_proctoring_recordings")
)
SUPPORT_ATTACHMENT_DIR = (
    os.path.join(os.path.dirname(os.path.abspath(settings.UPLOAD_DIR)), "private_support_attachments")
)
os.makedirs(PRIVATE_RECORDING_DIR, exist_ok=True)
os.makedirs(SUPPORT_ATTACHMENT_DIR, exist_ok=True)

app.mount(
    "/uploads",
    StaticFiles(directory=settings.UPLOAD_DIR),
    name="uploads",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Token-Invalid"],
)

api_v1 = settings.API_V1_PREFIX

# EXISTING APPLICATION ROUTERS

app.include_router(auth.router, prefix=api_v1)
app.include_router(candidate.router, prefix=api_v1)
app.include_router(resumes.router, prefix=api_v1)
app.include_router(jobs.router, prefix=api_v1)
app.include_router(applications.router, prefix=api_v1)
app.include_router(matching.router, prefix=api_v1)
app.include_router(interviews.router, prefix=api_v1)
app.include_router(assessments.router, prefix=api_v1)
app.include_router(recruiter.router, prefix=api_v1)
app.include_router(admin.router, prefix=api_v1)
app.include_router(notifications.router, prefix=api_v1)
app.include_router(question_bank.router, prefix=api_v1)

# RECRUITER AND CANDIDATE ASSESSMENTS

app.include_router(
    recruiter_assessments.router,
    prefix=api_v1,
)

app.include_router(
    candidate_assessments.router,
    prefix=api_v1,
)

# MANUAL RECRUITER ASSESSMENT REVIEW

app.include_router(
    assessment_reviews.router,
    prefix=api_v1,
)

# PROCTORING AND COMPUTER VISION

app.include_router(
    proctoring.router,
    prefix=api_v1,
)

app.include_router(
    computer_vision.router,
    prefix=api_v1,
)

app.include_router(
    proctoring.recruiter_router,
    prefix=api_v1,
)

# SUPPORT TICKET SYSTEM

app.include_router(
    support_tickets.router,
    prefix=api_v1,
)

# ADMIN SUPPORT TICKET MANAGEMENT

app.include_router(
    support_ticket_admin.router,
    prefix=api_v1,
)

# LOCAL SKILLSPHERE ASSISTANT AND SEPARATE RECRUITER AI TOOLS

app.include_router(
    assistant.router,
    prefix=api_v1,
)

app.include_router(
    recruiter_ai.router,
    prefix=api_v1,
)

# ROOT / HEALTH ENDPOINTS

@app.get("/", tags=["Health"])
def root():
    return {
        "app": settings.APP_NAME,
        "status": "online",
        "documentation": "/docs",
        "version": "1.0.0",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "database": "connected",
    }
