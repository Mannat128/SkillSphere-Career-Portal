import os
import uuid
import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, status, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.config import settings
from app.core.dependencies import get_current_user, get_current_candidate
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)
from app.models.user import User, UserRole
from app.models.candidate import (
    Candidate,
    CandidateSkill,
    CandidateEducation,
    CandidateExperience,
)
from app.models.skill import Skill
from app.models.resume import Resume, ResumeOCRResult, OCRStatusEnum
from app.schemas.resume import (
    ResumeResponse,
    ResumeOCRResultResponse,
    ResumeReviewUpdateRequest,
    ResumeConfirmRequest,
)
from app.services.ocr_service import OCRService
from app.services.resume_parser import ResumeParser

router = APIRouter(prefix="/resumes", tags=["Resumes & OCR"])

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}

@router.post("/upload", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """
    Step 1 & Step 2 & Step 3:
    Upload resume file (PDF, JPG, JPEG, PNG <= 10MB), execute digital PyMuPDF extraction
    or Tesseract OCR, parse structured information, and calculate confidence scores.
    """
    # 1. Validation: filename and extension
    if not file.filename:
        raise BadRequestException("No file provided")

    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise BadRequestException(
            f"Unsupported file format '{file_ext}'. Allowed formats: PDF, JPG, JPEG, PNG."
        )

    # Validate MIME type
    if file.content_type and file.content_type.lower() not in ALLOWED_MIME_TYPES:
        raise BadRequestException(f"Unsupported MIME type: {file.content_type}")

    # Read content and validate size (Max 10 MB)
    contents = await file.read()
    file_size = len(contents)
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024

    if file_size > max_bytes:
        raise BadRequestException(
            f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB ({round(file_size / (1024*1024), 2)}MB detected)."
        )

    if file_size == 0:
        raise BadRequestException("The uploaded file is empty.")

    # 2. Save securely to private uploads folder
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
    stored_path = os.path.join(settings.UPLOAD_DIR, unique_name)

    with open(stored_path, "wb") as f:
        f.write(contents)

    # Reset primary status on other candidate resumes if this is primary
    db.query(Resume).filter(Resume.candidate_id == candidate.id).update({"is_primary": False})

    resume = Resume(
        candidate_id=candidate.id,
        file_name=unique_name,
        original_filename=file.filename,
        file_path=stored_path,
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        is_primary=True,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    # 3. Create initial OCR record
    ocr_record = ResumeOCRResult(
        resume_id=resume.id,
        status=OCRStatusEnum.PROCESSING,
        verified_by_candidate=False,
    )
    db.add(ocr_record)
    db.commit()
    db.refresh(ocr_record)

    # 4. Execute extraction synchronously (or background task)
    try:
        raw_text, metadata = OCRService.process_file(stored_path, resume.mime_type)
        extracted_data, confidence_scores = ResumeParser.parse(raw_text, db=db)

        ocr_record.raw_text = raw_text
        ocr_record.extracted_data = extracted_data
        ocr_record.confidence_scores = confidence_scores
        ocr_record.status = OCRStatusEnum.COMPLETED
    except Exception as e:
        ocr_record.status = OCRStatusEnum.FAILED
        ocr_record.error_message = str(e)

    db.commit()

    return {
        "id": resume.id,
        "candidate_id": resume.candidate_id,
        "file_name": resume.file_name,
        "original_filename": resume.original_filename,
        "file_size": resume.file_size,
        "mime_type": resume.mime_type,
        "is_primary": resume.is_primary,
        "upload_date": resume.upload_date,
        "ocr_status": ocr_record.status,
        "download_url": f"/api/v1/resumes/{resume.id}/download"
    }

@router.get("", response_model=List[ResumeResponse])
def get_candidate_resumes(
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """List all resumes uploaded by the current candidate."""
    resumes = db.query(Resume).filter(Resume.candidate_id == candidate.id).order_by(Resume.upload_date.desc()).all()
    results = []
    for r in resumes:
        ocr_status = r.ocr_result.status if r.ocr_result else OCRStatusEnum.PENDING
        results.append({
            "id": r.id,
            "candidate_id": r.candidate_id,
            "file_name": r.file_name,
            "original_filename": r.original_filename,
            "file_size": r.file_size,
            "mime_type": r.mime_type,
            "is_primary": r.is_primary,
            "upload_date": r.upload_date,
            "ocr_status": ocr_status,
            "download_url": f"/api/v1/resumes/{r.id}/download"
        })
    return results

@router.get("/{resume_id}", response_model=ResumeResponse)
def get_resume_detail(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get single resume metadata with access control."""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise NotFoundException("Resume")

    # Authorization: Owner candidate, authorized recruiter, or Admin
    if current_user.role == UserRole.CANDIDATE and resume.candidate.user_id != current_user.id:
        raise ForbiddenException()

    ocr_status = resume.ocr_result.status if resume.ocr_result else OCRStatusEnum.PENDING
    return {
        "id": resume.id,
        "candidate_id": resume.candidate_id,
        "file_name": resume.file_name,
        "original_filename": resume.original_filename,
        "file_size": resume.file_size,
        "mime_type": resume.mime_type,
        "is_primary": resume.is_primary,
        "upload_date": resume.upload_date,
        "ocr_status": ocr_status,
        "download_url": f"/api/v1/resumes/{resume.id}/download"
    }

@router.get("/{resume_id}/ocr-status")
def get_ocr_status(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """View OCR processing status."""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise NotFoundException("Resume")
    return {
        "resume_id": resume.id,
        "status": resume.ocr_result.status if resume.ocr_result else "PENDING",
        "error_message": resume.ocr_result.error_message if resume.ocr_result else None
    }

@router.get("/{resume_id}/extracted-data", response_model=ResumeOCRResultResponse)
def get_extracted_data(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 4 & Step 5:
    Fetch extracted information and confidence scores for candidate review.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume or not resume.ocr_result:
        raise NotFoundException("Resume OCR result")

    if current_user.role == UserRole.CANDIDATE and resume.candidate.user_id != current_user.id:
        raise ForbiddenException()

    return resume.ocr_result

@router.put("/{resume_id}/extracted-data")
def update_extracted_data(
    resume_id: int,
    req: ResumeReviewUpdateRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """
    Step 5:
    Interactive Review: Allow candidate to modify, correct, add or delete extracted fields.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id, Resume.candidate_id == candidate.id).first()
    if not resume or not resume.ocr_result:
        raise NotFoundException("Resume OCR result")

    resume.ocr_result.extracted_data = req.extracted_data
    db.commit()
    return {"message": "Extracted resume information updated successfully", "data": req.extracted_data}

@router.post("/{resume_id}/confirm")
@router.post("/{resume_id}/confirm-to-profile")
def confirm_and_save_profile(
    resume_id: int,
    req: ResumeConfirmRequest,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 6:
    Candidate confirms verified OCR results and applies them directly to their candidate profile.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id, Resume.candidate_id == candidate.id).first()
    if not resume or not resume.ocr_result or not resume.ocr_result.extracted_data:
        raise NotFoundException("Resume OCR result")

    data = resume.ocr_result.extracted_data
    resume.ocr_result.verified_by_candidate = True
    resume.ocr_result.verified_at = datetime.datetime.utcnow()

    if req.apply_to_profile:
        # Apply phone / location if available and currently empty
        if data.get("phone") and not candidate.phone:
            candidate.phone = data["phone"]
        if data.get("location") and not candidate.location:
            candidate.location = data["location"]
        if data.get("summary") and not candidate.bio:
            candidate.bio = data["summary"]

        # Apply Skills
        extracted_skills = data.get("skills", [])
        for skill_name in extracted_skills:
            clean_name = skill_name.strip()
            skill = db.query(Skill).filter(Skill.name.ilike(clean_name)).first()
            if not skill:
                skill = Skill(name=clean_name, category="General")
                db.add(skill)
                db.commit()
                db.refresh(skill)

            # Check candidate skill association
            existing_cs = db.query(CandidateSkill).filter(
                CandidateSkill.candidate_id == candidate.id,
                CandidateSkill.skill_id == skill.id
            ).first()
            if not existing_cs:
                cs = CandidateSkill(
                    candidate_id=candidate.id,
                    skill_id=skill.id,
                    proficiency="Intermediate"
                )
                db.add(cs)

        # Apply Education
        for edu in data.get("educations", []):
            inst = edu.get("institution")
            deg = edu.get("degree")
            if inst and deg:
                existing_edu = db.query(CandidateEducation).filter(
                    CandidateEducation.candidate_id == candidate.id,
                    CandidateEducation.institution == inst,
                    CandidateEducation.degree == deg
                ).first()
                if not existing_edu:
                    c_edu = CandidateEducation(
                        candidate_id=candidate.id,
                        institution=inst,
                        degree=deg,
                        graduation_year=edu.get("graduation_year")
                    )
                    db.add(c_edu)

        # Apply Experience
        for exp in data.get("experiences", []):
            comp = exp.get("company")
            pos = exp.get("position")
            if comp and pos:
                existing_exp = db.query(CandidateExperience).filter(
                    CandidateExperience.candidate_id == candidate.id,
                    CandidateExperience.company == comp,
                    CandidateExperience.position == pos
                ).first()
                if not existing_exp:
                    c_exp = CandidateExperience(
                        candidate_id=candidate.id,
                        company=comp,
                        position=pos,
                        description=exp.get("description")
                    )
                    db.add(c_exp)

    db.commit()
    return {"message": "Verified resume data successfully applied to candidate profile."}

@router.get("/{resume_id}/download")
def download_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Secure download endpoint for private resume documents.
    Protected from unauthorized public URL scraping.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise NotFoundException("Resume")

    # Only owner candidate, recruiters, or admin can access
    if current_user.role == UserRole.CANDIDATE and resume.candidate.user_id != current_user.id:
        raise ForbiddenException("You cannot access another candidate's private document.")

    if not os.path.exists(resume.file_path):
        raise NotFoundException("Resume file on server disk")

    return FileResponse(
        resume.file_path,
        media_type=resume.mime_type,
        filename=resume.original_filename
    )

@router.delete("/{resume_id}")
def delete_resume(
    resume_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Delete uploaded resume file and database record."""
    resume = db.query(Resume).filter(Resume.id == resume_id, Resume.candidate_id == candidate.id).first()
    if not resume:
        raise NotFoundException("Resume")

    if os.path.exists(resume.file_path):
        try:
            os.remove(resume.file_path)
        except Exception:
            pass

    db.delete(resume)
    db.commit()
    return {"message": "Resume deleted successfully"}
