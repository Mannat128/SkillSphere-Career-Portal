from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.user import UserRole

class UserRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)

class RecruiterRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    company_name: str = Field(..., min_length=2, max_length=200)
    designation: Optional[str] = "Hiring Manager"
    company_website: Optional[str] = None
    company_location: Optional[str] = None
    industry: Optional[str] = None
    company_description: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, max_length=128)

class VerifyEmailRequest(BaseModel):
    token: str

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
