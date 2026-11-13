import enum
import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.base import Base

class ApplicationStatusEnum(str, enum.Enum):
    APPLIED = "APPLIED"
    UNDER_REVIEW = "UNDER_REVIEW"
    SHORTLISTED = "SHORTLISTED"
    INTERVIEW = "INTERVIEW"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"

class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True, index=True)
    cover_letter = Column(Text, nullable=True)
    current_status = Column(
        Enum(ApplicationStatusEnum),
        default=ApplicationStatusEnum.APPLIED,
        nullable=False,
        index=True
    )
    applied_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", name="uq_job_candidate_application"),
    )

    job = relationship("Job", back_populates="applications")
    candidate = relationship("Candidate", back_populates="applications")
    resume = relationship("Resume", back_populates="applications")
    status_history = relationship("ApplicationStatusHistory", back_populates="application", cascade="all, delete-orphan")
    interviews = relationship("Interview", back_populates="application", cascade="all, delete-orphan")

class ApplicationStatusHistory(Base):
    __tablename__ = "application_status_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(ApplicationStatusEnum), nullable=False)
    notes = Column(Text, nullable=True)
    changed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    application = relationship("Application", back_populates="status_history")
    changed_by = relationship("User")
