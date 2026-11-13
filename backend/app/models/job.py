import enum
import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.database.base import Base

class JobStatusEnum(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"
    MODERATION_PENDING = "MODERATION_PENDING"
    MODERATION_REJECTED = "MODERATION_REJECTED"

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recruiter_id = Column(Integer, ForeignKey("recruiters.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=False)
    location = Column(String(150), nullable=False, index=True)
    employment_type = Column(String(100), default="Full-time", nullable=False) # Full-time, Part-time, Contract, Internship, Remote
    experience_level = Column(String(100), default="Mid-Level", nullable=False) # Entry, Mid-Level, Senior, Lead
    min_salary = Column(Numeric(12, 2), nullable=True)
    max_salary = Column(Numeric(12, 2), nullable=True)
    salary_currency = Column(String(10), default="USD", nullable=False)
    responsibilities = Column(Text, nullable=True)
    qualifications = Column(Text, nullable=True)
    status = Column(Enum(JobStatusEnum), default=JobStatusEnum.PUBLISHED, nullable=False, index=True)
    moderation_notes = Column(Text, nullable=True)
    application_deadline = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    recruiter = relationship("Recruiter", back_populates="jobs")
    company = relationship("Company", back_populates="jobs")
    required_skills = relationship("JobSkill", back_populates="job", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")
    saved_by_candidates = relationship("SavedJob", back_populates="job", cascade="all, delete-orphan")
    resume_analyses = relationship("ResumeAnalysis", back_populates="job", cascade="all, delete-orphan")
    interviews = relationship("Interview", back_populates="job")
    assessment_config = relationship("JobAssessment", back_populates="job", uselist=False, cascade="all, delete-orphan")

class JobSkill(Base):
    __tablename__ = "job_skills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    is_required = Column(Boolean, default=True, nullable=False)

    job = relationship("Job", back_populates="required_skills")
    skill = relationship("Skill", back_populates="job_skills")

class SavedJob(Base):
    __tablename__ = "saved_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    candidate = relationship("Candidate", back_populates="saved_jobs")
    job = relationship("Job", back_populates="saved_by_candidates")
