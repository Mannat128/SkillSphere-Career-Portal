import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.dependencies import get_current_admin
from app.core.exceptions import NotFoundException, BadRequestException

from app.models.user import User, UserRole
from app.models.support_ticket import (
    SupportTicket,
    TicketPriority,
)
from app.models.notification import Notification
from app.models.audit import AuditLog


router = APIRouter(
    prefix="/support-tickets/admin",
    tags=["Admin Support Ticket Management"],
)


class TicketAssignmentRequest(BaseModel):
    admin_id: Optional[int] = Field(default=None, ge=1)


class TicketPriorityRequest(BaseModel):
    priority: TicketPriority


def get_ticket_or_404(ticket_id: int, db: Session):
    ticket = (
        db.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id)
        .first()
    )

    if not ticket:
        raise NotFoundException("Support ticket")

    return ticket


def notify_ticket_creator(
    db: Session,
    ticket: SupportTicket,
    title: str,
    message: str,
):
    db.add(
        Notification(
            user_id=ticket.created_by_id,
            title=title,
            message=message,
            type="SUPPORT",
            link=f"/support-tickets/{ticket.id}",
        )
    )


# ---------------------------------------------------------
# GET ADMIN USERS AVAILABLE FOR ASSIGNMENT
# ---------------------------------------------------------

@router.get("/assignable-admins")
def get_assignable_admins(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    admins = (
        db.query(User)
        .filter(
            User.role == UserRole.ADMIN,
            User.is_active == True,
        )
        .order_by(User.full_name.asc())
        .all()
    )

    return [
        {
            "id": admin.id,
            "full_name": admin.full_name,
            "email": admin.email,
            "is_active": admin.is_active,
        }
        for admin in admins
    ]


# ---------------------------------------------------------
# ASSIGN / REASSIGN / UNASSIGN TICKET
# ---------------------------------------------------------

@router.patch("/{ticket_id}/assignment")
def update_ticket_assignment(
    ticket_id: int,
    request: TicketAssignmentRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ticket = get_ticket_or_404(ticket_id, db)

    previous_admin_id = ticket.assigned_admin_id
    new_admin_id = request.admin_id

    if new_admin_id is not None:
        admin = (
            db.query(User)
            .filter(
                User.id == new_admin_id,
                User.role == UserRole.ADMIN,
                User.is_active == True,
            )
            .first()
        )

        if not admin:
            raise BadRequestException(
                "Selected Admin does not exist or is inactive."
            )

    if previous_admin_id == new_admin_id:
        return {
            "message": "Ticket is already assigned to this Admin.",
            "assigned_admin_id": ticket.assigned_admin_id,
        }

    ticket.assigned_admin_id = new_admin_id
    ticket.updated_at = datetime.datetime.utcnow()

    if new_admin_id is None:
        assignment_action = "SUPPORT_TICKET_UNASSIGNED"
        assignment_message = (
            f"Ticket {ticket.ticket_number} has been unassigned."
        )
    else:
        assignment_action = (
            "SUPPORT_TICKET_ASSIGNED"
            if previous_admin_id is None
            else "SUPPORT_TICKET_REASSIGNED"
        )

        assignment_message = (
            f"Ticket {ticket.ticket_number} has been assigned "
            f"to Admin ID {new_admin_id}."
        )

    db.add(
        AuditLog(
            user_id=current_admin.id,
            action=assignment_action,
            entity_type="support_ticket",
            entity_id=ticket.id,
            details={
                "previous_admin_id": previous_admin_id,
                "new_admin_id": new_admin_id,
            },
        )
    )

    notify_ticket_creator(
        db,
        ticket,
        "Support ticket assignment updated",
        assignment_message,
    )

    db.commit()

    return {
        "message": "Ticket assignment updated successfully.",
        "ticket_id": ticket.id,
        "assigned_admin_id": ticket.assigned_admin_id,
    }


# ---------------------------------------------------------
# UPDATE TICKET PRIORITY
# ---------------------------------------------------------

@router.patch("/{ticket_id}/priority")
def update_ticket_priority(
    ticket_id: int,
    request: TicketPriorityRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ticket = get_ticket_or_404(ticket_id, db)

    previous_priority = ticket.priority.value
    new_priority = request.priority

    if ticket.priority == new_priority:
        return {
            "message": "Ticket already has this priority.",
            "priority": ticket.priority.value,
        }

    ticket.priority = new_priority
    ticket.updated_at = datetime.datetime.utcnow()

    db.add(
        AuditLog(
            user_id=current_admin.id,
            action="SUPPORT_TICKET_PRIORITY_CHANGED",
            entity_type="support_ticket",
            entity_id=ticket.id,
            details={
                "previous_priority": previous_priority,
                "new_priority": new_priority.value,
            },
        )
    )

    notify_ticket_creator(
        db,
        ticket,
        "Support ticket priority updated",
        f"Your ticket {ticket.ticket_number} priority "
        f"has been changed to {new_priority.value}.",
    )

    db.commit()

    return {
        "message": "Ticket priority updated successfully.",
        "ticket_id": ticket.id,
        "priority": ticket.priority.value,
    }