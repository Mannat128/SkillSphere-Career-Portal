
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.database.session import SessionLocal
from app.services.init_db import init_db

# Import all routers
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
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("SkillSphere")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown events.
    Initializes admin provisioning and default master records.
    """
    logger.info("Starting SkillSphere Backend Application...")

    db = SessionLocal()

    try:
        init_db(db)
    except Exception as e:
        logger.error(f"Error during init_db: {e}")
    finally:
        db.close()

    yield

    logger.info("Shutting down SkillSphere Backend Application...")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Full-stack Career & Job Portal REST API with Resume OCR, "
        "AI Matching, and Recruitment Analytics."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# ==========================================
# STATIC FILES - PROFILE PICTURES & UPLOADS
# ==========================================

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# Serve uploaded files through the backend
# Example: /uploads/avatars/profile.jpg
app.mount(
    "/uploads",
    StaticFiles(directory=settings.UPLOAD_DIR),
    name="uploads"
)


# ==========================================
# CORS MIDDLEWARE
# ==========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# REGISTER API V1 ROUTERS
# ==========================================

api_v1 = settings.API_V1_PREFIX

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
app.include_router(recruiter_assessments.router, prefix=api_v1)
app.include_router(candidate_assessments.router, prefix=api_v1)


# ==========================================
# HEALTH CHECK ROUTES
# ==========================================

@app.get("/", tags=["Health"])
def root():
    return {
        "app": settings.APP_NAME,
        "status": "online",
        "documentation": "/docs",
        "version": "1.0.0"
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "database": "connected"
    }
