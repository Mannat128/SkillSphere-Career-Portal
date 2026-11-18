
import os
import uuid
import datetime
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    Form,
    Query,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.config import settings
from app.core.dependencies import get_current_user, get_current_admin
from app.core.exceptions import NotFoundException, BadRequestException

from app.models.user import User, UserRole
from app.models.support_ticket import (
    SupportTicket,
    TicketMessage,
    TicketAttachment,
    TicketStatus,
    TicketPriority,
    TicketCategory,
)
from app.models.notification import Notification
from app.models.audit import AuditLog


router = APIRouter(
    prefix="/support-tickets",
    tags=["Support Tickets"],
)


# Private directory OUTSIDE the publicly mounted uploads directory.
SUPPORT_ATTACHMENT_DIR = (
    Path(settings.UPLOAD_DIR).resolve().parent
    / "private_support_attachments"
)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024


def ticket_to_dict(ticket: SupportTicket):
    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "subject": ticket.subject,
        "description": ticket.description,
        "category": ticket.category.value,
        "priority": ticket.priority.value,
        "status": ticket.status.value,
        "created_by_id": ticket.created_by_id,
        "assigned_admin_id": ticket.assigned_admin_id,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "resolved_at": ticket.resolved_at,
        "messages": [
            {
                "id": message.id,
                "sender_id": message.sender_id,
                "message": message.message,
                "is_admin_reply": message.is_admin_reply,
                "created_at": message.created_at,
            }
            for message in ticket.messages
        ],
        "attachments": [
            {
                "id": attachment.id,
                "original_filename": attachment.original_filename,
                "content_type": attachment.content_type,
                "file_size": attachment.file_size,
                "created_at": attachment.created_at,
            }
            for attachment in ticket.attachments
        ],
    }


def get_accessible_ticket(
    ticket_id: int,
    current_user: User,
    db: Session,
):
    ticket = (
        db.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id)
        .first()
    )

    if not ticket:
        raise NotFoundException("Support ticket")

    if (
        current_user.role != UserRole.ADMIN
        and ticket.created_by_id != current_user.id
    ):
        raise NotFoundException("Support ticket")

    return ticket


def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    link: str,
):
    db.add(
        Notification(
            user_id=user_id,
            title=title,
            message=message,
            type="SUPPORT",
            link=link,
        )
    )


def save_attachments(
    files: list[UploadFile],
    ticket: SupportTicket,
    current_user: User,
    db: Session,
):
    if not files:
        return

    SUPPORT_ATTACHMENT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for file in files:
        if not file.filename:
            continue

        extension = Path(file.filename).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise BadRequestException(
                "Only PDF, JPG, JPEG, PNG and WEBP files are allowed."
            )

        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise BadRequestException(
                "Unsupported attachment content type."
            )

        content = file.file.read()

        if not content:
            raise BadRequestException(
                "Empty attachment files are not allowed."
            )

        if len(content) > MAX_FILE_SIZE:
            raise BadRequestException(
                f"Each attachment must be below "
                f"{settings.MAX_FILE_SIZE_MB} MB."
            )

        stored_filename = f"{uuid.uuid4().hex}{extension}"
        file_path = SUPPORT_ATTACHMENT_DIR / stored_filename

        with open(file_path, "wb") as output:
            output.write(content)

        db.add(
            TicketAttachment(
                ticket_id=ticket.id,
                uploaded_by_id=current_user.id,
                original_filename=os.path.basename(file.filename),
                stored_filename=stored_filename,
                file_path=str(file_path),
                content_type=file.content_type,
                file_size=len(content),
            )
        )


# ---------------------------------------------------------
# CREATE TICKET
# ---------------------------------------------------------

@router.post("")
def create_ticket(
    subject: str = Form(...),
    description: str = Form(...),
    category: TicketCategory = Form(...),
    priority: TicketPriority = Form(TicketPriority.MEDIUM),
    files: list[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not subject.strip() or not description.strip():
        raise BadRequestException(
            "Subject and description are required."
        )

    ticket_number = (
        "SS-"
        + datetime.datetime.utcnow().strftime("%Y%m%d")
        + "-"
        + uuid.uuid4().hex[:6].upper()
    )

    ticket = SupportTicket(
        ticket_number=ticket_number,
        created_by_id=current_user.id,
        subject=subject.strip(),
        description=description.strip(),
        category=category,
        priority=priority,
        status=TicketStatus.OPEN,
    )

    try:
        db.add(ticket)
        db.flush()

        save_attachments(
            files,
            ticket,
            current_user,
            db,
        )

        db.add(
            AuditLog(
                user_id=current_user.id,
                action="SUPPORT_TICKET_CREATED",
                entity_type="support_ticket",
                entity_id=ticket.id,
                details={
                    "ticket_number": ticket_number,
                },
            )
        )

        db.commit()
        db.refresh(ticket)

        return {
            "message": "Support ticket created successfully.",
            "ticket": ticket_to_dict(ticket),
        }

    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------
# ADMIN: GET ALL TICKETS
# Keep this static route before /{ticket_id}.
# ---------------------------------------------------------

@router.get("/admin/all")
def admin_get_all_tickets(
    status_filter: Optional[TicketStatus] = Query(
        None,
        alias="status",
    ),
    priority: Optional[TicketPriority] = Query(None),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(SupportTicket)

    if status_filter:
        query = query.filter(
            SupportTicket.status == status_filter
        )

    if priority:
        query = query.filter(
            SupportTicket.priority == priority
        )

    tickets = query.order_by(
        SupportTicket.created_at.desc()
    ).all()

    return [
        ticket_to_dict(ticket)
        for ticket in tickets
    ]


# ---------------------------------------------------------
# ADMIN: UPDATE TICKET STATUS
# ---------------------------------------------------------

@router.patch("/admin/{ticket_id}/status")
def admin_update_ticket_status(
    ticket_id: int,
    new_status: TicketStatus = Query(...),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ticket = (
        db.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id)
        .first()
    )

    if not ticket:
        raise NotFoundException("Support ticket")

    old_status = ticket.status.value

    ticket.status = new_status
    ticket.updated_at = datetime.datetime.utcnow()

    if new_status == TicketStatus.RESOLVED:
        ticket.resolved_at = datetime.datetime.utcnow()
    else:
        ticket.resolved_at = None

    db.add(
        AuditLog(
            user_id=current_admin.id,
            action="SUPPORT_TICKET_STATUS_CHANGED",
            entity_type="support_ticket",
            entity_id=ticket.id,
            details={
                "old_status": old_status,
                "new_status": new_status.value,
            },
        )
    )

    create_notification(
        db,
        ticket.created_by_id,
        "Support ticket updated",
        f"Your ticket {ticket.ticket_number} "
        f"is now {new_status.value}.",
        f"/support-tickets/{ticket.id}",
    )

    db.commit()

    return {
        "message": "Ticket status updated successfully.",
        "status": new_status.value,
    }


# ---------------------------------------------------------
# USER: GET OWN TICKETS
# ---------------------------------------------------------

@router.get("")
def get_my_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tickets = (
        db.query(SupportTicket)
        .filter(
            SupportTicket.created_by_id == current_user.id
        )
        .order_by(SupportTicket.created_at.desc())
        .all()
    )

    return [
        ticket_to_dict(ticket)
        for ticket in tickets
    ]


# ---------------------------------------------------------
# USER: GET SINGLE TICKET
# ---------------------------------------------------------

@router.get("/{ticket_id}")
def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = get_accessible_ticket(
        ticket_id,
        current_user,
        db,
    )

    return ticket_to_dict(ticket)


# ---------------------------------------------------------
# USER / ADMIN: SEND MESSAGE
# ---------------------------------------------------------

@router.post("/{ticket_id}/messages")
def add_ticket_message(
    ticket_id: int,
    message: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = get_accessible_ticket(
        ticket_id,
        current_user,
        db,
    )

    if ticket.status == TicketStatus.CLOSED:
        raise BadRequestException(
            "This ticket is closed."
        )

    if not message.strip() and not files:
        raise BadRequestException(
            "Message or attachment is required."
        )

    is_admin = current_user.role == UserRole.ADMIN

    if (
        ticket.status == TicketStatus.RESOLVED
        and not is_admin
    ):
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.resolved_at = None

    try:
        db.add(
            TicketMessage(
                ticket_id=ticket.id,
                sender_id=current_user.id,
                message=message.strip() or "Attachment uploaded.",
                is_admin_reply=is_admin,
            )
        )

        save_attachments(
            files,
            ticket,
            current_user,
            db,
        )

        ticket.updated_at = datetime.datetime.utcnow()

        if is_admin:
            create_notification(
                db,
                ticket.created_by_id,
                "Support team replied",
                f"There is a new reply on ticket "
                f"{ticket.ticket_number}.",
                f"/support-tickets/{ticket.id}",
            )
        else:
            admins = (
                db.query(User)
                .filter(
                    User.role == UserRole.ADMIN,
                    User.is_active == True,
                )
                .all()
            )

            for admin in admins:
                create_notification(
                    db,
                    admin.id,
                    "New support message",
                    f"New message on ticket "
                    f"{ticket.ticket_number}.",
                    f"/support-tickets/{ticket.id}",
                )

        db.add(
            AuditLog(
                user_id=current_user.id,
                action="SUPPORT_TICKET_MESSAGE_ADDED",
                entity_type="support_ticket",
                entity_id=ticket.id,
                details={
                    "ticket_number": ticket.ticket_number,
                },
            )
        )

        db.commit()
        db.refresh(ticket)

        return {
            "message": "Message sent successfully.",
            "ticket": ticket_to_dict(ticket),
        }

    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------
# PRIVATE ATTACHMENT DOWNLOAD
# ---------------------------------------------------------

@router.get("/{ticket_id}/attachments/{attachment_id}")
def download_ticket_attachment(
    ticket_id: int,
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = get_accessible_ticket(
        ticket_id,
        current_user,
        db,
    )

    attachment = (
        db.query(TicketAttachment)
        .filter(
            TicketAttachment.id == attachment_id,
            TicketAttachment.ticket_id == ticket.id,
        )
        .first()
    )

    if not attachment:
        raise NotFoundException("Attachment")

    file_path = Path(attachment.file_path).resolve()
    private_dir = SUPPORT_ATTACHMENT_DIR.resolve()

    if (
        private_dir not in file_path.parents
        or not file_path.is_file()
    ):
        raise NotFoundException("Attachment file")

    return FileResponse(
        path=str(file_path),
        media_type=attachment.content_type,
        filename=attachment.original_filename,
    )
