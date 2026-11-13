from typing import List, Optional, Any
import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.models.job import JobStatusEnum
from app.schemas.recruiter import CompanyResponse

class SkillRequirement(BaseModel):
    skill_name: str
    is_required: bool = True

class JobCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=20)
    location: str = Field(..., min_length=2, max_length=150)
    employment_type: str = "Full-time"
    experience_level: str = "Mid-Level"
    min_salary: Optional[float] = None
    max_salary: Optional[float] = None
    salary_currency: str = "USD"
    responsibilities: Optional[str] = None
    qualifications: Optional[str] = None
    application_deadline: Optional[datetime.datetime] = None
    required_skills: List[str] = [] # list of skill names

class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    min_salary: Optional[float] = None
    max_salary: Optional[float] = None
    salary_currency: Optional[str] = None
    responsibilities: Optional[str] = None
    qualifications: Optional[str] = None
    status: Optional[JobStatusEnum] = None
    application_deadline: Optional[datetime.datetime] = None
    required_skills: Optional[List[str]] = None

class JobResponse(BaseModel):
    id: int
    recruiter_id: int
    company_id: int
    title: str
    description: str
    location: str
    employment_type: str
    experience_level: str
    min_salary: Optional[float] = None
    max_salary: Optional[float] = None
    salary_currency: str
    responsibilities: Optional[str] = None
    qualifications: Optional[str] = None
    status: JobStatusEnum
    application_deadline: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    company: Optional[CompanyResponse] = None
    required_skills: List[str] = []
    total_applicants: Optional[int] = 0
    is_saved: Optional[bool] = False
    has_applied: Optional[bool] = False

    model_config = ConfigDict(from_attributes=True)

    @field_validator("required_skills", mode="before")
    @classmethod
    def serialize_skills(cls, v: Any) -> List[str]:
        if not v:
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                result.append(item)
            elif hasattr(item, "skill") and item.skill:
                result.append(item.skill.name)
            elif hasattr(item, "name"):
                result.append(item.name)
        return result

class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
