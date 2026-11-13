import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database.base import Base

class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    category = Column(String(100), nullable=True) # e.g. Frontend, Backend, Database, Cloud
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    candidate_skills = relationship("CandidateSkill", back_populates="skill", cascade="all, delete-orphan")
    job_skills = relationship("JobSkill", back_populates="skill", cascade="all, delete-orphan")
