import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database.base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True) # e.g. "USER_REGISTERED", "RECRUITER_APPROVED", "JOB_CREATED", "STATUS_CHANGED"
    entity_type = Column(String(100), nullable=True) # "user", "job", "application", "recruiter"
    entity_id = Column(Integer, nullable=True)
    ip_address = Column(String(50), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)

    user = relationship("User", back_populates="audit_logs")
