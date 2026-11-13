import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.base import Base

class QuestionBankQuestion(Base):
    __tablename__ = "question_bank_questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recruiter_id = Column(Integer, ForeignKey("recruiters.id", ondelete="CASCADE"), nullable=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_shared = Column(Boolean, default=False, nullable=False, index=True) # Admin shared pool
    question_text = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True) # Python, React, SQL, Java, etc.
    difficulty = Column(String(50), default="Medium", nullable=False, index=True) # Easy, Medium, Hard
    option_a = Column(String(500), nullable=False)
    option_b = Column(String(500), nullable=False)
    option_c = Column(String(500), nullable=False)
    option_d = Column(String(500), nullable=False)
    correct_answer = Column(String(10), nullable=False) # 'A', 'B', 'C', 'D'
    marks = Column(Float, default=1.0, nullable=False)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    recruiter = relationship("Recruiter")
    job = relationship("Job")
    creator = relationship("User")

class JobAssessment(Base):
    __tablename__ = "job_assessments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    title = Column(String(200), default="First Round Technical MCQ Assessment", nullable=False)
    instructions = Column(Text, nullable=True)
    total_questions = Column(Integer, default=10, nullable=False)
    duration_minutes = Column(Integer, default=30, nullable=False)
    total_marks = Column(Float, default=10.0, nullable=False)
    passing_marks = Column(Float, default=6.0, nullable=False)
    qualification_rule = Column(String(10), default=">", nullable=False) # '>' or '>='
    negative_marking = Column(Boolean, default=False, nullable=False)
    negative_marks = Column(Float, default=0.0, nullable=False) # marks deducted per incorrect answer
    categories = Column(JSON, nullable=True) # list of category names
    difficulty_distribution = Column(JSON, nullable=True) # e.g. {"Easy": 3, "Medium": 5, "Hard": 2}
    selection_mode = Column(String(50), default="RANDOM", nullable=False) # "RANDOM" or "SPECIFIC"
    selected_question_ids = Column(JSON, nullable=True) # if SPECIFIC mode
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    job = relationship("Job", back_populates="assessment_config")
    assignments = relationship("AssessmentAssignment", back_populates="job_assessment", cascade="all, delete-orphan")

class AssessmentAssignment(Base):
    __tablename__ = "assessment_assignments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    job_assessment_id = Column(Integer, ForeignKey("job_assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="PENDING", nullable=False, index=True) # PENDING, IN_PROGRESS, SUBMITTED, QUALIFIED, NOT_QUALIFIED, EXPIRED
    config_snapshot = Column(JSON, nullable=False) # frozen configuration at shortlisting
    assigned_questions = Column(JSON, nullable=False) # list of question objects WITHOUT correct answers
    private_answer_key = Column(JSON, nullable=False) # server-only mapping: {str(question_id): correct_option}
    assigned_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    application = relationship("Application")
    job = relationship("Job")
    candidate = relationship("Candidate")
    job_assessment = relationship("JobAssessment", back_populates="assignments")
    attempt = relationship("CandidateAssessmentAttempt", back_populates="assignment", uselist=False, cascade="all, delete-orphan")
    result = relationship("CandidateAssessmentResult", back_populates="assignment", uselist=False, cascade="all, delete-orphan")

class CandidateAssessmentAttempt(Base):
    __tablename__ = "candidate_assessment_attempts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    assignment_id = Column(Integer, ForeignKey("assessment_assignments.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False) # backend source of truth
    submitted_at = Column(DateTime, nullable=True)
    time_taken_seconds = Column(Integer, nullable=True)
    is_submitted = Column(Boolean, default=False, nullable=False, index=True)
    saved_answers = Column(JSON, default={}, nullable=False) # {str(question_id): selected_option}
    marked_for_review = Column(JSON, default=[], nullable=False) # [question_id, ...]

    assignment = relationship("AssessmentAssignment", back_populates="attempt")
    candidate = relationship("Candidate")
    result = relationship("CandidateAssessmentResult", back_populates="attempt", uselist=False, cascade="all, delete-orphan")

class CandidateAssessmentResult(Base):
    __tablename__ = "candidate_assessment_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    attempt_id = Column(Integer, ForeignKey("candidate_assessment_attempts.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("assessment_assignments.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    obtained_marks = Column(Float, nullable=False)
    total_marks = Column(Float, nullable=False)
    percentage = Column(Float, nullable=False)
    correct_count = Column(Integer, nullable=False)
    incorrect_count = Column(Integer, nullable=False)
    unanswered_count = Column(Integer, nullable=False)
    passing_marks = Column(Float, nullable=False)
    qualification_rule = Column(String(10), nullable=False) # '>' or '>='
    is_qualified = Column(Boolean, nullable=False, index=True)
    qualification_message = Column(String(255), nullable=False)
    question_breakdown = Column(JSON, nullable=True) # detailed breakdown for recruiter
    evaluated_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    attempt = relationship("CandidateAssessmentAttempt", back_populates="result")
    assignment = relationship("AssessmentAssignment", back_populates="result")
    candidate = relationship("Candidate")
    job = relationship("Job")
