import io
import os
import uuid
import datetime
import zipfile
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
    CandidateProject,
)
from app.models.skill import Skill
from app.models.resume import Resume, ResumeOCRResult, OCRStatusEnum
from app.models.application import Application
from app.models.job import Job
from app.models.recruiter import Recruiter
from app.schemas.resume import (
    ResumeResponse,
    ResumeOCRResultResponse,
    ResumeReviewUpdateRequest,
    ResumeConfirmRequest,
)
from app.services.ocr_service import OCRService
from app.services.resume_parser import ResumeParser

router = APIRouter(prefix="/resumes", tags=["Resumes & OCR"])


def _authorize_resume_read(current_user: User, resume: Resume, db: Session) -> None:
    """Allow owners, admins, and recruiters with an application to their job."""
    if current_user.role == UserRole.ADMIN:
        return

    if current_user.role == UserRole.CANDIDATE:
        if resume.candidate and resume.candidate.user_id == current_user.id:
            return
        raise ForbiddenException("You cannot access another candidate's private resume.")

    if current_user.role == UserRole.RECRUITER:
        recruiter_id = db.query(Recruiter.id).filter(
            Recruiter.user_id == current_user.id
        ).scalar()
        if recruiter_id is not None:
            application = db.query(Application.id).join(
                Job, Application.job_id == Job.id
            ).filter(
                Application.resume_id == resume.id,
                Job.recruiter_id == recruiter_id,
            ).first()
            if application:
                return

    raise ForbiddenException("You are not authorized to access this private resume.")

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".docx"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def validate_resume_content(file_ext: str, contents: bytes) -> None:
    """Validate file signatures before storing uploaded resume bytes."""
    valid = False
    if file_ext == ".pdf":
        valid = b"%PDF-" in contents[:1024]
    elif file_ext == ".png":
        valid = contents.startswith(b"\x89PNG\r\n\x1a\n")
    elif file_ext in {".jpg", ".jpeg"}:
        valid = contents.startswith(b"\xff\xd8\xff")
    elif file_ext == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(contents)) as archive:
                names = set(archive.namelist())
                valid = (
                    "[Content_Types].xml" in names
                    and "word/document.xml" in names
                    and len(names) <= 5000
                    and sum(item.file_size for item in archive.infolist()) <= 50 * 1024 * 1024
                    and archive.testzip() is None
                )
        except (zipfile.BadZipFile, OSError):
            valid = False
    if not valid:
        raise BadRequestException("The uploaded file content does not match a supported resume format.")

@router.post("/upload", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """
    Step 1 & Step 2 & Step 3:
    Upload resume file (PDF, DOCX, JPG, JPEG, PNG <= 10MB), execute digital extraction
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

    validate_resume_content(file_ext, contents)

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

    _authorize_resume_read(current_user, resume, db)

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
    _authorize_resume_read(current_user, resume, db)
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

    _authorize_resume_read(current_user, resume, db)

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
        # This endpoint runs only after the candidate explicitly confirms the review.
        # Existing profile fields are filled only when empty; login email is never changed.
        extracted_name = data.get("full_name")
        if not ResumeParser.is_probable_person_name(extracted_name):
            # Older OCR results may contain a section heading as the candidate
            # name. Re-parse the stored text before applying the explicitly
            # reviewed result, so a heading never replaces the account name.
            reparsed, _ = ResumeParser.parse(resume.ocr_result.raw_text or "", db=db)
            extracted_name = reparsed.get("full_name")
            if ResumeParser.is_probable_person_name(extracted_name):
                data["full_name"] = extracted_name
        if ResumeParser.is_probable_person_name(extracted_name):
            current_user.full_name = extracted_name.strip()
        extracted_email = data.get("email")
        if isinstance(extracted_email, str) and extracted_email.strip() and not candidate.contact_email:
            candidate.contact_email = extracted_email.strip()
        for field in (
            "phone", "location", "headline", "bio", "linkedin_url",
            "github_url", "portfolio_url", "additional_url",
        ):
            extracted_field = "summary" if field == "bio" else field
            value = data.get(extracted_field)
            if isinstance(value, str) and value.strip() and not getattr(candidate, field):
                setattr(candidate, field, value.strip())

        # Apply Skills
        extracted_skills = data.get("skills", [])
        for skill_name in extracted_skills:
            clean_name = skill_name.strip() if isinstance(skill_name, str) else ""
            if not clean_name:
                continue
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
                        field_of_study=edu.get("field_of_study"),
                        graduation_year=edu.get("graduation_year"),
                        grade=edu.get("grade"),
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
                        start_date=exp.get("start_date"),
                        end_date=exp.get("end_date"),
                        is_current=bool(exp.get("is_current", False)),
                        description=exp.get("description")
                    )
                    db.add(c_exp)

        # Projects are appended only when their title is not already on this profile.
        for project in data.get("projects", []):
            if not isinstance(project, dict):
                continue
            title = str(project.get("title") or "").strip()
            if not title:
                continue
            existing_project = db.query(CandidateProject).filter(
                CandidateProject.candidate_id == candidate.id,
                CandidateProject.title.ilike(title),
            ).first()
            if existing_project:
                continue
            db.add(CandidateProject(
                candidate_id=candidate.id,
                title=title,
                description=project.get("description"),
                technologies=project.get("technologies"),
                project_url=project.get("project_url"),
                github_url=project.get("github_url"),
                image_url=project.get("image_url"),
                start_date=project.get("start_date"),
                end_date=project.get("end_date"),
            ))

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

    _authorize_resume_read(current_user, resume, db)

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
