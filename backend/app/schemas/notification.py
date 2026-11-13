import datetime
from typing import Optional
from pydantic import BaseModel

class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str
    link: Optional[str] = None
    is_read: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class NotificationPreferenceUpdate(BaseModel):
    email_job_alerts: Optional[bool] = None
    email_application_updates: Optional[bool] = None
    email_interview_invites: Optional[bool] = None
    in_app_notifications: Optional[bool] = None

class NotificationPreferenceResponse(BaseModel):
    email_job_alerts: bool
    email_application_updates: bool
    email_interview_invites: bool
    in_app_notifications: bool

    class Config:
        from_attributes = True
