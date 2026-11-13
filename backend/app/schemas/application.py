from typing import List, Optional
import datetime
from pydantic import BaseModel
from app.models.application import ApplicationStatusEnum
from app.schemas.job import JobResponse
from app.schemas.candidate import CandidateResponse

class ApplicationCreate(BaseModel):
    resume_id: Optional[int] = None
    cover_letter: Optional[str] = None

class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatusEnum
    notes: Optional[str] = None

class StatusHistoryItem(BaseModel):
    id: int
    status: ApplicationStatusEnum
    notes: Optional[str] = None
    changed_by_name: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class ApplicationResponse(BaseModel):
    id: int
    job_id: int
    candidate_id: int
    resume_id: Optional[int] = None
    cover_letter: Optional[str] = None
    current_status: ApplicationStatusEnum
    applied_at: datetime.datetime
    updated_at: datetime.datetime
    job: JobResponse
    status_history: List[StatusHistoryItem] = []

    class Config:
        from_attributes = True

class RecruiterApplicantResponse(BaseModel):
    id: int
    job_id: int
    job_title: str
    candidate_id: int
    candidate: CandidateResponse
    resume_id: Optional[int] = None
    resume_url: Optional[str] = None
    cover_letter: Optional[str] = None
    current_status: ApplicationStatusEnum
    applied_at: datetime.datetime
    match_score: Optional[float] = None
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    status_history: List[StatusHistoryItem] = []

    class Config:
        from_attributes = True
