import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database.base import Base


class ProctoringSession(Base):
    __tablename__ = "proctoring_sessions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
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

    # Candidate consent
    consent_given = Column(Boolean, default=False, nullable=False)
    consent_version = Column(String(50), nullable=True)
    consented_at = Column(DateTime, nullable=True)

    camera_permission_granted = Column(
        Boolean,
        default=False,
        nullable=False,
    )
    microphone_permission_granted = Column(Boolean, default=False, nullable=False)

    # Session state
    session_status = Column(
        String(30),
        default="PENDING",
        nullable=False,
    )

    # Private recording metadata
    recording_filename = Column(String(255), nullable=True)
    recording_path = Column(String(500), nullable=True)
    recording_provider = Column(String(30), nullable=True)
    cloudinary_asset_id = Column(String(128), nullable=True)
    cloudinary_public_id = Column(String(255), nullable=True)
    cloudinary_version = Column(String(50), nullable=True)
    cloudinary_format = Column(String(20), nullable=True)
    cloudinary_resource_type = Column(String(20), nullable=True)
    cloudinary_delivery_type = Column(String(30), nullable=True)
    recording_mime_type = Column(String(100), nullable=True)
    recording_size_bytes = Column(BigInteger, nullable=True)

    recording_started_at = Column(DateTime, nullable=True)
    recording_completed_at = Column(DateTime, nullable=True)

    # Automatic deletion after configured retention (15 days by default)
    delete_after = Column(DateTime, nullable=True)
    recording_deleted_at = Column(DateTime, nullable=True)

    # Proctoring violations
    warning_count = Column(Integer, default=0, nullable=False)
    is_flagged_for_review = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    last_violation_type = Column(String(50), nullable=True)
    last_violation_at = Column(DateTime, nullable=True)

    # Timestamps
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

    # Relationships
    assignment = relationship("AssessmentAssignment")
    candidate = relationship("Candidate")

    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            name="uq_proctoring_session_assignment",
        ),
    )
