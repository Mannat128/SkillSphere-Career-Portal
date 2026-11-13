import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float, Numeric, JSON
from sqlalchemy.orm import relationship
from app.database.base import Base

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    location = Column(String(150), nullable=True)
    headline = Column(String(200), nullable=True) # e.g. "Full Stack Developer | React & Python"
    bio = Column(Text, nullable=True)
    profile_percentage = Column(Integer, default=0, nullable=False)
    visibility = Column(String(50), default="PUBLIC_TO_RECRUITERS", nullable=False) # PUBLIC_TO_RECRUITERS, PRIVATE
    is_open_to_work = Column(Boolean, default=True, nullable=False)
    preferred_job_titles = Column(JSON, nullable=True) # list of job title strings
    preferred_locations = Column(JSON, nullable=True) # list of location strings
    work_modes = Column(JSON, nullable=True) # list of modes e.g. ["Remote", "Hybrid", "On-site"]
    employment_types = Column(JSON, nullable=True) # list e.g. ["Full-time", "Part-time", "Internship", "Contract"]
    expected_salary_min = Column(Numeric(12, 2), nullable=True)
    expected_salary_max = Column(Numeric(12, 2), nullable=True)
    salary_currency = Column(String(10), default="USD", nullable=False)
    notice_period_days = Column(Integer, default=0, nullable=False)
    availability_status = Column(String(50), default="Immediately", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="candidate_profile")
    resumes = relationship("Resume", back_populates="candidate", cascade="all, delete-orphan")
    skills = relationship("CandidateSkill", back_populates="candidate", cascade="all, delete-orphan")
    educations = relationship("CandidateEducation", back_populates="candidate", cascade="all, delete-orphan")
    experiences = relationship("CandidateExperience", back_populates="candidate", cascade="all, delete-orphan")
    projects = relationship("CandidateProject", back_populates="candidate", cascade="all, delete-orphan")
    certifications = relationship("CandidateCertification", back_populates="candidate", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="candidate", cascade="all, delete-orphan")
    saved_jobs = relationship("SavedJob", back_populates="candidate", cascade="all, delete-orphan")
    alert_preferences = relationship("JobAlertPreference", back_populates="candidate", uselist=False, cascade="all, delete-orphan")
    interviews = relationship("Interview", back_populates="candidate")
    interview_sessions = relationship("InterviewSession", back_populates="candidate", cascade="all, delete-orphan")
    assessment_attempts = relationship("AssessmentAttempt", back_populates="candidate", cascade="all, delete-orphan")

class CandidateSkill(Base):
    __tablename__ = "candidate_skills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    proficiency = Column(String(50), default="Intermediate") # Beginner, Intermediate, Advanced, Expert
    years_of_experience = Column(Float, default=1.0)

    candidate = relationship("Candidate", back_populates="skills")
    skill = relationship("Skill", back_populates="candidate_skills")

class CandidateEducation(Base):
    __tablename__ = "candidate_education"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    institution = Column(String(200), nullable=False)
    degree = Column(String(150), nullable=False)
    field_of_study = Column(String(150), nullable=True)
    graduation_year = Column(String(20), nullable=True)
    grade = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    candidate = relationship("Candidate", back_populates="educations")

class CandidateExperience(Base):
    __tablename__ = "candidate_experience"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    company = Column(String(200), nullable=False)
    position = Column(String(150), nullable=False)
    location = Column(String(150), nullable=True)
    start_date = Column(String(50), nullable=True)
    end_date = Column(String(50), nullable=True)
    is_current = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    candidate = relationship("Candidate", back_populates="experiences")

class CandidateProject(Base):
    __tablename__ = "candidate_projects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    technologies = Column(String(300), nullable=True)
    project_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    candidate = relationship("Candidate", back_populates="projects")

class CandidateCertification(Base):
    __tablename__ = "candidate_certifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    issuing_organization = Column(String(200), nullable=False)
    issue_date = Column(String(50), nullable=True)
    credential_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    candidate = relationship("Candidate", back_populates="certifications")

class JobAlertPreference(Base):
    __tablename__ = "job_alert_preferences"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    keywords = Column(String(255), nullable=True)
    preferred_location = Column(String(150), nullable=True)
    preferred_job_type = Column(String(100), nullable=True)
    experience_level = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    candidate = relationship("Candidate", back_populates="alert_preferences")
