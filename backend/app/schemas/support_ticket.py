
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.support_ticket import (
    TicketStatus,
    TicketPriority,
    TicketCategory,
)


class TicketCreate(BaseModel):
    subject: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    category: TicketCategory = TicketCategory.OTHER
    priority: TicketPriority = TicketPriority.MEDIUM


class TicketMessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)


class TicketStatusUpdate(BaseModel):
    status: TicketStatus
    reason: Optional[str] = Field(None, max_length=1000)


class TicketPriorityUpdate(BaseModel):
    priority: TicketPriority


class TicketMessageResponse(BaseModel):
    id: int
    sender_id: int
    message: str
    is_admin_reply: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TicketAttachmentResponse(BaseModel):
    id: int
    original_filename: str
    content_type: str
    file_size: int
    created_at: datetime

    class Config:
        from_attributes = True


class TicketResponse(BaseModel):
    id: int
    ticket_number: str
    created_by_id: int
    assigned_admin_id: Optional[int] = None
    subject: str
    description: str
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None

    messages: List[TicketMessageResponse] = []
    attachments: List[TicketAttachmentResponse] = []

    class Config:
        from_attributes = True
