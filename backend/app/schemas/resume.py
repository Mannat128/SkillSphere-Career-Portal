from typing import List, Optional, Dict, Any
import datetime
from pydantic import BaseModel
from app.models.resume import OCRStatusEnum

class ExtractedEducation(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    graduation_year: Optional[str] = None

class ExtractedExperience(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None

class ExtractedResumeData(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    skills: List[str] = []
    educations: List[ExtractedEducation] = []
    experiences: List[ExtractedExperience] = []
    projects: List[str] = []
    certifications: List[str] = []
    summary: Optional[str] = None

class ResumeResponse(BaseModel):
    id: int
    candidate_id: int
    file_name: str
    original_filename: str
    file_size: int
    mime_type: str
    is_primary: bool
    upload_date: datetime.datetime
    ocr_status: OCRStatusEnum
    download_url: str

    class Config:
        from_attributes = True

class ResumeOCRResultResponse(BaseModel):
    resume_id: int
    status: OCRStatusEnum
    raw_text: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    confidence_scores: Optional[Dict[str, float]] = None
    error_message: Optional[str] = None
    verified_by_candidate: bool
    verified_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True

class ResumeReviewUpdateRequest(BaseModel):
    extracted_data: Dict[str, Any]

class ResumeConfirmRequest(BaseModel):
    apply_to_profile: bool = True

class ResumeAnalysisResponse(BaseModel):
    id: Optional[int] = None
    resume_id: int
    job_id: int
    job_title: str
    company_name: str
    match_score: float
    matched_skills: List[str]
    missing_skills: List[str]
    recommendations: Optional[str] = None
    explanation: Optional[str] = None

class MultiJobMatchRequest(BaseModel):
    resume_id: int
    job_ids: List[int]

class MultiJobMatchResponse(BaseModel):
    resume_id: int
    comparisons: List[ResumeAnalysisResponse]
