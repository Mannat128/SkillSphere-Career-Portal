from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from urllib.parse import urlsplit, urlunsplit

class EducationItem(BaseModel):
    id: Optional[int] = None
    institution: str = Field(..., min_length=2)
    degree: str = Field(..., min_length=2)
    field_of_study: Optional[str] = None
    graduation_year: Optional[str] = None
    grade: Optional[str] = None

    class Config:
        from_attributes = True

class ExperienceItem(BaseModel):
    id: Optional[int] = None
    company: str = Field(..., min_length=2)
    position: str = Field(..., min_length=2)
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    description: Optional[str] = None

    class Config:
        from_attributes = True

class ProjectItem(BaseModel):
    id: Optional[int] = None
    title: str = Field(..., min_length=2)
    description: Optional[str] = None
    technologies: Optional[str] = None
    project_url: Optional[str] = None
    github_url: Optional[str] = None
    image_url: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    @field_validator("project_url", "github_url", "image_url")
    @classmethod
    def validate_project_urls(cls, value):
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if not parsed.scheme:
            normalized = f"https://{normalized}"
            parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Project links must be valid HTTP or HTTPS URLs.")
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))

    @model_validator(mode="after")
    def validate_project_dates(self):
        allowed = (r"\d{4}", r"\d{4}-\d{2}", r"\d{4}-\d{2}-\d{2}")
        import re
        for value in (self.start_date, self.end_date):
            if value and not any(re.fullmatch(pattern, value.strip()) for pattern in allowed):
                raise ValueError("Project dates must use YYYY, YYYY-MM, or YYYY-MM-DD.")
        return self

    class Config:
        from_attributes = True

class CertificationItem(BaseModel):
    id: Optional[int] = None
    name: str = Field(..., min_length=2)
    issuing_organization: str = Field(..., min_length=2)
    issue_date: Optional[str] = None
    credential_url: Optional[str] = None

    class Config:
        from_attributes = True

class CandidateSkillItem(BaseModel):
    skill_id: int
    name: str
    proficiency: str = "Intermediate"
    years_of_experience: float = 1.0

class CandidateProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=150)
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    headline: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    additional_url: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value):
        if value is None:
            return None
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Enter your full name.")
        if normalized.casefold() in {
            "professional summary", "summary", "profile", "experience",
            "education", "skills", "projects", "resume", "curriculum vitae",
        }:
            raise ValueError("Enter a person’s name, not a resume section heading.")
        return normalized

    @field_validator("linkedin_url", "github_url", "portfolio_url", "additional_url")
    @classmethod
    def validate_profile_urls(cls, value):
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if not parsed.scheme:
            normalized = f"https://{normalized}"
            parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Professional links must be valid HTTP or HTTPS URLs.")
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))

    @field_validator("contact_email")
    @classmethod
    def validate_contact_email(cls, value):
        if value is None or not value.strip():
            return None
        from email_validator import validate_email, EmailNotValidError
        try:
            return validate_email(value.strip(), check_deliverability=False).normalized
        except EmailNotValidError as exc:
            raise ValueError("Enter a valid contact email address.") from exc

class CareerPreferencesUpdate(BaseModel):
    preferred_job_titles: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    preferred_locations: Optional[List[str]] = None
    work_modes: Optional[List[str]] = None
    employment_types: Optional[List[str]] = None
    expected_salary_min: Optional[float] = None
    expected_salary_max: Optional[float] = None
    salary_currency: Optional[str] = "USD"
    notice_period_days: Optional[int] = 0
    availability_status: Optional[str] = "Immediately"
    is_open_to_work: Optional[bool] = True

class CareerPreferencesResponse(BaseModel):
    preferred_job_titles: List[str] = []
    preferred_skills: List[str] = []
    preferred_locations: List[str] = []
    work_modes: List[str] = []
    employment_types: List[str] = []
    expected_salary_min: Optional[float] = None
    expected_salary_max: Optional[float] = None
    salary_currency: str = "USD"
    notice_period_days: int = 0
    availability_status: str = "Immediately"
    is_open_to_work: bool = True

class ProfileVisibilityUpdate(BaseModel):
    visibility: str = Field(..., description="'PUBLIC_TO_RECRUITERS' or 'PRIVATE'")

class ProfileVisibilityResponse(BaseModel):
    visibility: str
    is_open_to_work: bool

class ProfileCompletionResponse(BaseModel):
    completion_percentage: int
    completed_fields: List[str]
    missing_fields: List[str]
    section_breakdown: dict

class SkillAddRequest(BaseModel):
    skill_name: str = Field(..., min_length=1)
    proficiency: str = "Intermediate"
    years_of_experience: float = 1.0

class CandidateResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    headline: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    additional_url: Optional[str] = None
    profile_percentage: int
    avatar_url: Optional[str] = None
    visibility: str = "PUBLIC_TO_RECRUITERS"
    is_open_to_work: bool = True
    preferred_job_titles: List[str] = []
    preferred_locations: List[str] = []
    work_modes: List[str] = []
    employment_types: List[str] = []
    expected_salary_min: Optional[float] = None
    expected_salary_max: Optional[float] = None
    salary_currency: str = "USD"
    notice_period_days: int = 0
    availability_status: str = "Immediately"
    skills: List[CandidateSkillItem] = []
    educations: List[EducationItem] = []
    experiences: List[ExperienceItem] = []
    projects: List[ProjectItem] = []
    certifications: List[CertificationItem] = []

    class Config:
        from_attributes = True

class JobAlertPreferenceUpdate(BaseModel):
    keywords: Optional[str] = None
    preferred_location: Optional[str] = None
    preferred_job_type: Optional[str] = None
    experience_level: Optional[str] = None
    is_active: bool = True

class JobAlertPreferenceResponse(BaseModel):
    id: int
    keywords: Optional[str] = None
    preferred_location: Optional[str] = None
    preferred_job_type: Optional[str] = None
    experience_level: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True
