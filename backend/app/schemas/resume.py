from typing import List, Optional, Dict, Any
import datetime
from pydantic import BaseModel, field_validator
from app.models.resume import OCRStatusEnum
from urllib.parse import urlsplit

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

    @field_validator("extracted_data")
    @classmethod
    def validate_review_urls(cls, data):
        if not isinstance(data, dict):
            raise ValueError("Extracted resume data must be an object.")
        url_fields = ("linkedin_url", "github_url", "portfolio_url", "additional_url")
        for field in url_fields:
            value = data.get(field)
            if not value:
                continue
            if not isinstance(value, str):
                raise ValueError(f"{field} must be a URL string.")
            normalized = value.strip()
            parsed = urlsplit(normalized)
            if not parsed.scheme:
                normalized = f"https://{normalized}"
                parsed = urlsplit(normalized)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError(f"{field} must be a valid HTTP or HTTPS URL.")
            data[field] = normalized
        for project in data.get("projects", []) or []:
            if not isinstance(project, dict):
                raise ValueError("Each extracted project must be an object.")
            for field in ("project_url", "github_url", "image_url"):
                value = project.get(field)
                if not value:
                    continue
                if not isinstance(value, str):
                    raise ValueError(f"Project {field} must be a URL string.")
                normalized = value.strip()
                parsed = urlsplit(normalized)
                if not parsed.scheme:
                    normalized = f"https://{normalized}"
                    parsed = urlsplit(normalized)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                    raise ValueError(f"Project {field} must be a valid HTTP or HTTPS URL.")
                project[field] = normalized
        return data

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
