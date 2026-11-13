from typing import List, Optional, Dict, Any
import datetime
from pydantic import BaseModel
from app.models.user import UserRole
from app.models.recruiter import RecruiterApprovalStatus

class UserAdminView(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class PlatformAnalyticsResponse(BaseModel):
    total_users: int
    total_candidates: int
    total_recruiters: int
    total_companies: int
    total_jobs: int
    active_jobs: int
    total_applications: int
    total_resumes: int
    ocr_processed_count: int
    interviews_scheduled: int
    selected_candidates: int

class AuditLogItem(BaseModel):
    id: int
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True
