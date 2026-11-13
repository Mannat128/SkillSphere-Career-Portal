import enum
import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.database.base import Base

class RecruiterApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), unique=True, index=True, nullable=False)
    logo_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    website = Column(String(255), nullable=True)
    industry = Column(String(100), nullable=True)
    location = Column(String(150), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    recruiters = relationship("Recruiter", back_populates="company")
    jobs = relationship("Job", back_populates="company")

class Recruiter(Base):
    __tablename__ = "recruiters"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    designation = Column(String(100), nullable=True) # e.g. "Senior Technical Recruiter"
    phone = Column(String(50), nullable=True)
    approval_status = Column(Enum(RecruiterApprovalStatus), default=RecruiterApprovalStatus.PENDING, nullable=False, index=True)
    rejection_reason = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="recruiter_profile", foreign_keys=[user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    company = relationship("Company", back_populates="recruiters")
    jobs = relationship("Job", back_populates="recruiter", cascade="all, delete-orphan")
    interviews = relationship("Interview", back_populates="recruiter")
