import enum
import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.database.base import Base

class InterviewStatusEnum(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    RESCHEDULED = "RESCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    recruiter_id = Column(Integer, ForeignKey("recruiters.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    interview_date = Column(DateTime, nullable=False)
    interview_type = Column(String(100), default="Video Call", nullable=False) # Video Call, In-Person, Phone
    meeting_link = Column(String(500), nullable=True)
    instructions = Column(Text, nullable=True)
    status = Column(Enum(InterviewStatusEnum), default=InterviewStatusEnum.SCHEDULED, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    application = relationship("Application", back_populates="interviews")
    recruiter = relationship("Recruiter", back_populates="interviews")
    candidate = relationship("Candidate", back_populates="interviews")
    job = relationship("Job", back_populates="interviews")

class InterviewSession(Base):
    """Candidate AI Mock Interview / Practice Session"""
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    role_or_tech = Column(String(150), nullable=False) # e.g. "React Developer", "Python Backend"
    total_questions = Column(Integer, default=5, nullable=False)
    completed = Column(DateTime, nullable=True)
    feedback_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    candidate = relationship("Candidate", back_populates="interview_sessions")
    questions = relationship("InterviewQuestion", back_populates="session", cascade="all, delete-orphan")

class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    category = Column(String(100), default="Technical", nullable=False)
    difficulty = Column(String(50), default="Intermediate", nullable=False) # Beginner, Intermediate, Advanced

    session = relationship("InterviewSession", back_populates="questions")
    answers = relationship("InterviewAnswer", back_populates="question", cascade="all, delete-orphan")

class InterviewAnswer(Base):
    __tablename__ = "interview_answers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_answer = Column(Text, nullable=False)
    ai_feedback = Column(Text, nullable=True)
    score = Column(Float, nullable=True) # 0 to 100
    strengths = Column(Text, nullable=True)
    improvements = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    question = relationship("InterviewQuestion", back_populates="answers")
    candidate = relationship("Candidate")
