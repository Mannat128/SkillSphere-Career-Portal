import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.database.base import Base

class TechnicalAssessment(Base):
    __tablename__ = "technical_assessments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    technology = Column(String(100), nullable=False, index=True) # Python, Java, JavaScript, React, SQL, FastAPI, HTML/CSS
    description = Column(Text, nullable=True)
    difficulty = Column(String(50), default="Intermediate", nullable=False) # Beginner, Intermediate, Advanced
    duration_minutes = Column(Integer, default=15, nullable=False)
    passing_score = Column(Float, default=70.0, nullable=False) # e.g. 70%
    total_questions = Column(Integer, default=5, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    questions = relationship("AssessmentQuestion", back_populates="assessment", cascade="all, delete-orphan")
    attempts = relationship("AssessmentAttempt", back_populates="assessment", cascade="all, delete-orphan")

class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("technical_assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    option_a = Column(String(500), nullable=False)
    option_b = Column(String(500), nullable=False)
    option_c = Column(String(500), nullable=False)
    option_d = Column(String(500), nullable=False)
    correct_option = Column(String(10), nullable=False) # 'A', 'B', 'C', 'D'
    explanation = Column(Text, nullable=True)

    assessment = relationship("TechnicalAssessment", back_populates="questions")
    results = relationship("AssessmentResult", back_populates="question", cascade="all, delete-orphan")

class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("technical_assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    score = Column(Float, default=0.0, nullable=False)
    total_score = Column(Float, default=100.0, nullable=False)
    passed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    assessment = relationship("TechnicalAssessment", back_populates="attempts")
    candidate = relationship("Candidate", back_populates="assessment_attempts")
    results = relationship("AssessmentResult", back_populates="attempt", cascade="all, delete-orphan")

class AssessmentResult(Base):
    __tablename__ = "assessment_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    attempt_id = Column(Integer, ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("assessment_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    selected_option = Column(String(10), nullable=False) # 'A', 'B', 'C', 'D'
    is_correct = Column(Boolean, default=False, nullable=False)

    attempt = relationship("AssessmentAttempt", back_populates="results")
    question = relationship("AssessmentQuestion", back_populates="results")
