
import enum
import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum,
    Boolean,
)
from sqlalchemy.orm import relationship

from app.database.base import Base


class TicketStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TicketCategory(str, enum.Enum):
    ACCOUNT = "ACCOUNT"
    JOB_APPLICATION = "JOB_APPLICATION"
    ASSESSMENT = "ASSESSMENT"
    TECHNICAL = "TECHNICAL"
    PAYMENT = "PAYMENT"
    OTHER = "OTHER"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    ticket_number = Column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )

    created_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    assigned_admin_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    subject = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)

    category = Column(
        Enum(TicketCategory),
        nullable=False,
    )

    priority = Column(
        Enum(TicketPriority),
        nullable=False,
        default=TicketPriority.MEDIUM,
    )

    status = Column(
        Enum(TicketStatus),
        nullable=False,
        default=TicketStatus.OPEN,
        index=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    resolved_at = Column(
        DateTime,
        nullable=True,
    )

    messages = relationship(
        "TicketMessage",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketMessage.created_at",
    )

    attachments = relationship(
        "TicketAttachment",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )

    creator = relationship(
        "User",
        foreign_keys=[created_by_id],
    )

    assigned_admin = relationship(
        "User",
        foreign_keys=[assigned_admin_id],
    )


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    ticket_id = Column(
        Integer,
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sender_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    message = Column(Text, nullable=False)

    is_admin_reply = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )

    ticket = relationship(
        "SupportTicket",
        back_populates="messages",
    )

    sender = relationship("User")


class TicketAttachment(Base):
    __tablename__ = "ticket_attachments"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    ticket_id = Column(
        Integer,
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    uploaded_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    original_filename = Column(
        String(255),
        nullable=False,
    )

    stored_filename = Column(
        String(255),
        unique=True,
        nullable=False,
    )

    file_path = Column(
        String(500),
        nullable=False,
    )

    content_type = Column(
        String(100),
        nullable=False,
    )

    file_size = Column(
        Integer,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )

    ticket = relationship(
        "SupportTicket",
        back_populates="attachments",
    )

    uploader = relationship("User")
