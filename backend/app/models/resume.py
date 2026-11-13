import enum
import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from app.database.base import Base

class OCRStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False) # bytes
    mime_type = Column(String(100), nullable=False)
    is_primary = Column(Boolean, default=True, nullable=False)
    version_number = Column(Integer, default=1, nullable=False)
    upload_date = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    candidate = relationship("Candidate", back_populates="resumes")
    ocr_result = relationship("ResumeOCRResult", back_populates="resume", uselist=False, cascade="all, delete-orphan")
    analyses = relationship("ResumeAnalysis", back_populates="resume", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="resume")

class ResumeOCRResult(Base):
    __tablename__ = "resume_ocr_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    status = Column(Enum(OCRStatusEnum), default=OCRStatusEnum.PENDING, nullable=False, index=True)
    raw_text = Column(Text(length=100000), nullable=True) # full extracted text
    extracted_data = Column(JSON, nullable=True) # structured JSON with extracted details
    confidence_scores = Column(JSON, nullable=True) # field-level confidence ratings
    error_message = Column(Text, nullable=True)
    verified_by_candidate = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    resume = relationship("Resume", back_populates="ocr_result")

class ResumeAnalysis(Base):
    __tablename__ = "resume_analysis"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    match_score = Column(Float, nullable=False) # 0 to 100 percentage
    matched_skills = Column(JSON, nullable=False) # list of matched skill names
    missing_skills = Column(JSON, nullable=False) # list of missing required skills
    recommendations = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True) # transparent match score calculation
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    resume = relationship("Resume", back_populates="analyses")
    job = relationship("Job", back_populates="resume_analyses")
