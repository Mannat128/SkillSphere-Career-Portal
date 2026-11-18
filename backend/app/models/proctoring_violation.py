
import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
)

from app.database.base import Base


class ProctoringViolation(Base):
    __tablename__ = "proctoring_violations"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    proctoring_session_id = Column(
        Integer,
        ForeignKey("proctoring_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    assignment_id = Column(
        Integer,
        ForeignKey("assessment_assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    candidate_id = Column(
        Integer,
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    violation_type = Column(
        String(100),
        nullable=False,
        index=True,
    )

    confidence = Column(
        Float,
        nullable=True,
    )

    details = Column(
        JSON,
        nullable=True,
    )

    detected_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
        index=True,
    )