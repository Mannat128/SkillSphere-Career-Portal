from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.models.recruiter import RecruiterApprovalStatus

class CompanyCreateUpdate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    logo_url: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None

class CompanyResponse(BaseModel):
    id: int
    name: str
    logo_url: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    class Config:
        from_attributes = True

class RecruiterProfileUpdate(BaseModel):
    designation: Optional[str] = None
    phone: Optional[str] = None

class RecruiterResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str
    designation: Optional[str] = None
    phone: Optional[str] = None
    approval_status: RecruiterApprovalStatus
    rejection_reason: Optional[str] = None
    company: Optional[CompanyResponse] = None

    class Config:
        from_attributes = True

class RecruiterVerificationAction(BaseModel):
    approval_status: RecruiterApprovalStatus
    rejection_reason: Optional[str] = None
