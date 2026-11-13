from typing import List, Optional
import datetime
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from app.database.session import get_db
from app.core.dependencies import get_current_admin
from app.core.exceptions import NotFoundException, BadRequestException, ForbiddenException
from app.models.user import User, UserRole
from app.models.recruiter import Recruiter, Company, RecruiterApprovalStatus
from app.models.job import Job, JobStatusEnum
from app.models.application import Application, ApplicationStatusEnum
from app.models.resume import Resume, ResumeOCRResult, OCRStatusEnum
from app.models.audit import AuditLog
from app.models.interview import Interview
from app.schemas.admin import (
    UserAdminView,
    PlatformAnalyticsResponse,
    AuditLogItem,
)
from app.schemas.recruiter import RecruiterVerificationAction
from app.services.export_service import ExportService

router = APIRouter(prefix="/admin", tags=["Admin Administration"])

# User Management
@router.get("/users", response_model=List[UserAdminView])
def get_users(
    search: Optional[str] = Query(None),
    role: Optional[UserRole] = Query(None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """View registered users with search and role filtering."""
    query = db.query(User)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(User.full_name.ilike(term), User.email.ilike(term)))
    if role:
        query = query.filter(User.role == role)

    return query.order_by(User.created_at.desc()).all()

@router.put("/users/{user_id}/toggle-status")
@router.patch("/users/{user_id}/toggle-status")
def toggle_user_status(
    user_id: int,
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Enable or disable a user account."""
    if user_id == admin_user.id:
        raise BadRequestException("Cannot disable your own administrator account.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("User")

    user.is_active = not user.is_active

    # Audit log
    audit = AuditLog(
        user_id=admin_user.id,
        action="USER_STATUS_TOGGLED",
        entity_type="user",
        entity_id=user.id,
        details={"new_active_status": user.is_active}
    )
    db.add(audit)
    db.commit()

    return {"message": f"User account has been {'reactivated' if user.is_active else 'disabled'}.", "is_active": user.is_active}

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Safely delete inappropriate account."""
    if user_id == admin_user.id:
        raise BadRequestException("Cannot delete the active administrator account.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("User")

    audit = AuditLog(
        user_id=admin_user.id,
        action="USER_DELETED",
        entity_type="user",
        entity_id=user.id,
        details={"deleted_email": user.email, "role": user.role.value}
    )
    db.add(audit)
    db.delete(user)
    db.commit()

    return {"message": "User account permanently removed."}

# Recruiter Verification
@router.get("/recruiters")
def list_recruiters(
    status: Optional[RecruiterApprovalStatus] = Query(None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """View recruiter registration requests and company profiles."""
    query = db.query(Recruiter).join(User, Recruiter.user_id == User.id)
    if status:
        query = query.filter(Recruiter.approval_status == status)

    recruiters = query.order_by(Recruiter.created_at.desc()).all()
    results = []
    for r in recruiters:
        results.append({
            "id": r.id,
            "user_id": r.user_id,
            "full_name": r.user.full_name if r.user else "",
            "email": r.user.email if r.user else "",
            "designation": r.designation,
            "company_name": r.company.name if r.company else "Independent",
            "company_website": r.company.website if r.company else None,
            "company_industry": r.company.industry if r.company else None,
            "approval_status": r.approval_status,
            "rejection_reason": r.rejection_reason,
            "created_at": r.created_at
        })
    return results

@router.put("/recruiters/{recruiter_id}/verify")
@router.patch("/recruiters/{recruiter_id}/verify")
def verify_recruiter(
    recruiter_id: int,
    req: RecruiterVerificationAction,
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Approve, reject, or suspend recruiter registration."""
    recruiter = db.query(Recruiter).filter(Recruiter.id == recruiter_id).first()
    if not recruiter:
        raise NotFoundException("Recruiter")

    recruiter.approval_status = req.approval_status
    recruiter.rejection_reason = req.rejection_reason
    recruiter.reviewed_by_id = admin_user.id
    if req.approval_status == RecruiterApprovalStatus.APPROVED:
        recruiter.approved_at = datetime.datetime.utcnow()

    # Audit log
    audit = AuditLog(
        user_id=admin_user.id,
        action=f"RECRUITER_{req.approval_status.value}",
        entity_type="recruiter",
        entity_id=recruiter.id,
        details={"reason": req.rejection_reason}
    )
    db.add(audit)
    db.commit()

    return {"message": f"Recruiter status updated to {req.approval_status.value}"}

# Job Moderation
@router.get("/jobs")
def get_all_jobs_moderation(
    status: Optional[JobStatusEnum] = Query(None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """View all platform job postings for moderation."""
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    jobs = query.order_by(Job.created_at.desc()).all()
    results = []
    for j in jobs:
        results.append({
            "id": j.id,
            "title": j.title,
            "company_name": j.company.name if j.company else "",
            "location": j.location,
            "employment_type": j.employment_type,
            "status": j.status,
            "moderation_notes": j.moderation_notes,
            "created_at": j.created_at
        })
    return results

@router.put("/jobs/{job_id}/moderate")
def moderate_job(
    job_id: int,
    new_status: JobStatusEnum,
    notes: Optional[str] = None,
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Approve, reject, or disable a job posting."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise NotFoundException("Job")

    job.status = new_status
    job.moderation_notes = notes

    audit = AuditLog(
        user_id=admin_user.id,
        action="JOB_MODERATED",
        entity_type="job",
        entity_id=job.id,
        details={"new_status": new_status.value, "notes": notes}
    )
    db.add(audit)
    db.commit()

    return {"message": f"Job status updated to {new_status.value}"}

# Platform Analytics
@router.get("/analytics", response_model=PlatformAnalyticsResponse)
def get_platform_analytics(
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Section 9: Platform Analytics:
    All numbers derived strictly from real database records.
    """
    return {
        "total_users": db.query(User).count(),
        "total_candidates": db.query(User).filter(User.role == UserRole.CANDIDATE).count(),
        "total_recruiters": db.query(User).filter(User.role == UserRole.RECRUITER).count(),
        "total_companies": db.query(Company).count(),
        "total_jobs": db.query(Job).count(),
        "active_jobs": db.query(Job).filter(Job.status == JobStatusEnum.PUBLISHED).count(),
        "total_applications": db.query(Application).count(),
        "total_resumes": db.query(Resume).count(),
        "ocr_processed_count": db.query(ResumeOCRResult).filter(ResumeOCRResult.status == OCRStatusEnum.COMPLETED).count(),
        "interviews_scheduled": db.query(Interview).count(),
        "selected_candidates": db.query(Application).filter(Application.current_status == ApplicationStatusEnum.SELECTED).count()
    }

# Audit Logs
@router.get("/audit-logs", response_model=List[AuditLogItem])
def get_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Maintain activity records for compliance and platform security."""
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    results = []
    for l in logs:
        results.append({
            "id": l.id,
            "user_id": l.user_id,
            "user_email": l.user.email if l.user else None,
            "action": l.action,
            "entity_type": l.entity_type,
            "entity_id": l.entity_id,
            "details": l.details,
            "created_at": l.created_at
        })
    return results

# Reports
@router.get("/reports/excel")
def export_excel_report(
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Export complete platform data in Excel format."""
    buf = ExportService.generate_excel_report(db)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=SkillSphere_Platform_Report.xlsx"}
    )

@router.get("/reports/pdf")
def export_pdf_report(
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Export executive analytics report in PDF format."""
    buf = ExportService.generate_pdf_report(db)
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=SkillSphere_Executive_Report.pdf"}
    )
