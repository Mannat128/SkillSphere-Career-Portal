import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, Float, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database.base import Base


class SpheraConversation(Base):
    __tablename__ = "sphera_conversations"
    __table_args__ = (
        Index("ix_sphera_conversations_user_updated", "user_id", "updated_at"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title = Column(String(120), nullable=False)
    mode = Column(String(32), nullable=False, default="website_help")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )
    guest_session_hash = Column(String(64), nullable=True, index=True)
    selected_language = Column(String(16), nullable=False, default="auto")
    last_intent = Column(String(80), nullable=True)
    last_confidence = Column(Float, nullable=True)

    messages = relationship(
        "SpheraMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="SpheraMessage.created_at",
    )


class SpheraMessage(Base):
    __tablename__ = "sphera_messages"
    __table_args__ = (
        Index("ix_sphera_messages_conversation_created", "conversation_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    conversation_id = Column(
        Integer,
        ForeignKey("sphera_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(16), nullable=False)
    text = Column(Text, nullable=False)
    intent = Column(String(80), nullable=True)
    confidence = Column(Float, nullable=True)
    language = Column(String(16), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    conversation = relationship("SpheraConversation", back_populates="messages")


class AssistantFeedback(Base):
    __tablename__ = "assistant_feedback"
    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_assistant_feedback_user_message"),
        Index(
            "uq_assistant_feedback_guest_message",
            "message_id",
            "guest_session_hash",
            unique=True,
        ),
        Index("ix_assistant_feedback_status_priority", "status", "priority"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("sphera_messages.id", ondelete="CASCADE"), nullable=True, index=True)
    conversation_id = Column(Integer, ForeignKey("sphera_conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    guest_session_hash = Column(String(64), nullable=True, index=True)
    user_role = Column(String(32), nullable=False)
    rating = Column(String(16), nullable=False)
    category = Column(String(40), nullable=True)
    comment = Column(String(1000), nullable=True)
    language = Column(String(16), nullable=False, default="en")
    matched_intent = Column(String(80), nullable=True)
    match_score = Column(Float, nullable=False, default=0.0)
    status = Column(String(20), nullable=False, default="OPEN", index=True)
    priority = Column(String(20), nullable=False, default="MEDIUM", index=True)
    admin_notes = Column(String(2000), nullable=True)
    assigned_admin_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)


class AssistantUnansweredQuestion(Base):
    __tablename__ = "assistant_unanswered_questions"
    __table_args__ = (UniqueConstraint("query_hash", "language", name="uq_assistant_unanswered_query_language"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_hash = Column(String(64), nullable=False, index=True)
    normalized_query = Column(String(500), nullable=False)
    language = Column(String(16), nullable=False, index=True)
    best_intent = Column(String(80), nullable=True)
    match_score = Column(Float, nullable=False, default=0.0)
    frequency = Column(Integer, nullable=False, default=1)
    review_status = Column(String(20), nullable=False, default="OPEN", index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class AssistantKnowledgeSuggestion(Base):
    __tablename__ = "assistant_knowledge_suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    unanswered_id = Column(Integer, ForeignKey("assistant_unanswered_questions.id", ondelete="SET NULL"), nullable=True, index=True)
    intent_id = Column(String(80), nullable=False)
    language = Column(String(16), nullable=False)
    question = Column(String(500), nullable=False)
    response = Column(String(2000), nullable=False)
    route = Column(String(160), nullable=True)
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
