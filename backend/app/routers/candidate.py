import os
import io
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, status, Response, UploadFile, File, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.config import settings
from app.core.dependencies import get_current_user, get_current_candidate
from app.core.exceptions import NotFoundException, BadRequestException, ForbiddenException
from app.models.user import User
from app.models.candidate import (
    Candidate,
    CandidateEducation,
    CandidateExperience,
    CandidateProject,
    CandidateCertification,
    CandidateSkill,
    JobAlertPreference,
)
from app.models.skill import Skill
from app.models.job import Job, JobSkill, JobStatusEnum
from app.schemas.candidate import (
    CandidateProfileUpdate,
    CandidateResponse,
    EducationItem,
    ExperienceItem,
    ProjectItem,
    CertificationItem,
    JobAlertPreferenceUpdate,
    JobAlertPreferenceResponse,
    CareerPreferencesUpdate,
    CareerPreferencesResponse,
    ProfileVisibilityUpdate,
    ProfileVisibilityResponse,
    ProfileCompletionResponse,
)
from app.schemas.job import JobResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from urllib.parse import urlsplit

router = APIRouter(prefix="/candidate", tags=["Candidate Profile"])

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5 MB

def calculate_profile_completion_details(cand: Candidate, user: Optional[User] = None) -> Dict[str, Any]:
    """
    Calculate dynamic profile completeness score and detailed missing/completed fields breakdown.
    Total: 100%
    """
    completed_fields = []
    missing_fields = []
    section_breakdown = {}

    # 1. Basic Info (20% total, 5% each)
    basic_score = 0
    if cand.phone and cand.phone.strip():
        basic_score += 5
        completed_fields.append("Phone Number")
    else:
        missing_fields.append("Phone Number")

    if cand.location and cand.location.strip():
        basic_score += 5
        completed_fields.append("Location")
    else:
        missing_fields.append("Location")

    if cand.headline and cand.headline.strip():
        basic_score += 5
        completed_fields.append("Professional Headline")
    else:
        missing_fields.append("Professional Headline")

    if cand.bio and cand.bio.strip():
        basic_score += 5
        completed_fields.append("Bio / Professional Summary")
    else:
        missing_fields.append("Bio / Professional Summary")

    section_breakdown["basic_info"] = {"score": basic_score, "max": 20}

    # 2. Profile Picture (10%)
    avatar_score = 0
    avatar_url = user.avatar_url if user else (cand.user.avatar_url if cand.user else None)
    if avatar_url:
        avatar_score = 10
        completed_fields.append("Profile Picture")
    else:
        missing_fields.append("Profile Picture")
    section_breakdown["profile_picture"] = {"score": avatar_score, "max": 10}

    # 3. Education (15%)
    edu_score = 0
    if cand.educations and len(cand.educations) > 0:
        edu_score = 15
        completed_fields.append(f"Education ({len(cand.educations)} records)")
    else:
        missing_fields.append("Education Details")
    section_breakdown["education"] = {"score": edu_score, "max": 15}

    # 4. Work Experience (15%)
    exp_score = 0
    if cand.experiences and len(cand.experiences) > 0:
        exp_score = 15
        completed_fields.append(f"Work Experience ({len(cand.experiences)} records)")
    else:
        missing_fields.append("Work Experience")
    section_breakdown["work_experience"] = {"score": exp_score, "max": 15}

    # 5. Technical Skills (15%)
    skill_score = 0
    if cand.skills and len(cand.skills) >= 3:
        skill_score = 15
        completed_fields.append(f"Technical Skills ({len(cand.skills)} skills)")
    elif cand.skills and len(cand.skills) > 0:
        skill_score = 8
        completed_fields.append(f"Technical Skills ({len(cand.skills)} skills)")
        missing_fields.append("Add at least 3 skills for optimal visibility")
    else:
        missing_fields.append("Technical Skills")
    section_breakdown["skills"] = {"score": skill_score, "max": 15}

    # 6. Projects (10%)
    proj_score = 0
    if cand.projects and len(cand.projects) > 0:
        proj_score = 10
        completed_fields.append(f"Projects ({len(cand.projects)} projects)")
    else:
        missing_fields.append("Projects")
    section_breakdown["projects"] = {"score": proj_score, "max": 10}

    # 7. Certifications (5%)
    cert_score = 0
    if cand.certifications and len(cand.certifications) > 0:
        cert_score = 5
        completed_fields.append(f"Certifications ({len(cand.certifications)} records)")
    else:
        missing_fields.append("Certifications")
    section_breakdown["certifications"] = {"score": cert_score, "max": 5}

    # 8. Career Preferences (10%)
    pref_score = 0
    has_titles = bool(cand.preferred_job_titles and len(cand.preferred_job_titles) > 0)
    has_locs = bool(cand.preferred_locations and len(cand.preferred_locations) > 0)
    if has_titles or has_locs:
        pref_score = 10
        completed_fields.append("Career Preferences")
    else:
        missing_fields.append("Career Preferences")
    section_breakdown["career_preferences"] = {"score": pref_score, "max": 10}

    total_percentage = min(100, basic_score + avatar_score + edu_score + exp_score + skill_score + proj_score + cert_score + pref_score)

    return {
        "percentage": total_percentage,
        "completed_fields": completed_fields,
        "missing_fields": missing_fields,
        "section_breakdown": section_breakdown,
    }

def calculate_profile_percentage(cand: Candidate, user: Optional[User] = None) -> int:
    """Convenience helper returning single integer percentage score."""
    details = calculate_profile_completion_details(cand, user)
    return details["percentage"]

# ==================== PROFILE VIEW & UPDATE ====================

@router.get("/profile", response_model=CandidateResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Retrieve full candidate profile."""
    # Ensure profile percentage is refreshed from actual data
    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()

    skills_data = [
        {
            "skill_id": cs.skill_id,
            "name": cs.skill.name if cs.skill else "",
            "proficiency": cs.proficiency,
            "years_of_experience": cs.years_of_experience or 1.0
        }
        for cs in candidate.skills
    ]

    return {
        "id": candidate.id,
        "user_id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "contact_email": candidate.contact_email,
        "phone": candidate.phone,
        "location": candidate.location,
        "headline": candidate.headline,
        "bio": candidate.bio,
        "linkedin_url": candidate.linkedin_url,
        "github_url": candidate.github_url,
        "portfolio_url": candidate.portfolio_url,
        "additional_url": candidate.additional_url,
        "profile_percentage": candidate.profile_percentage,
        "avatar_url": current_user.avatar_url,
        "visibility": candidate.visibility or "PUBLIC_TO_RECRUITERS",
        "is_open_to_work": candidate.is_open_to_work if candidate.is_open_to_work is not None else True,
        "preferred_job_titles": candidate.preferred_job_titles or [],
        "preferred_locations": candidate.preferred_locations or [],
        "work_modes": candidate.work_modes or [],
        "employment_types": candidate.employment_types or [],
        "expected_salary_min": float(candidate.expected_salary_min) if candidate.expected_salary_min else None,
        "expected_salary_max": float(candidate.expected_salary_max) if candidate.expected_salary_max else None,
        "salary_currency": candidate.salary_currency or "USD",
        "notice_period_days": candidate.notice_period_days or 0,
        "availability_status": candidate.availability_status or "Immediately",
        "skills": skills_data,
        "educations": candidate.educations or [],
        "experiences": candidate.experiences or [],
        "projects": candidate.projects or [],
        "certifications": candidate.certifications or []
    }

@router.put("/profile", response_model=CandidateResponse)
def update_profile(
    req: CandidateProfileUpdate,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update personal candidate profile fields."""
    if req.full_name is not None:
        current_user.full_name = req.full_name
    if req.phone is not None:
        candidate.phone = req.phone
    if "contact_email" in req.model_fields_set:
        candidate.contact_email = req.contact_email or None
    if req.location is not None:
        candidate.location = req.location
    if req.headline is not None:
        candidate.headline = req.headline
    if req.bio is not None:
        candidate.bio = req.bio
    for field in ("linkedin_url", "github_url", "portfolio_url", "additional_url"):
        if field in req.model_fields_set:
            value = getattr(req, field)
            setattr(candidate, field, value or None)

    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    db.refresh(candidate)

    return get_profile(current_user, candidate, db)

# ==================== PROFILE COMPLETION ====================

@router.get("/profile/completion", response_model=ProfileCompletionResponse)
def get_profile_completion(
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Dynamically calculate profile completion percentage, completed fields list,
    and missing fields breakdown using actual candidate profile records.
    """
    details = calculate_profile_completion_details(candidate, current_user)
    if candidate.profile_percentage != details["percentage"]:
        candidate.profile_percentage = details["percentage"]
        db.commit()

    return {
        "completion_percentage": details["percentage"],
        "completed_fields": details["completed_fields"],
        "missing_fields": details["missing_fields"],
        "section_breakdown": details["section_breakdown"],
    }

# ==================== PROFILE PICTURE ====================

@router.post("/profile/picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload or update candidate profile photo.
    Validates file format (JPEG, PNG, WebP) and maximum file size (5MB).
    Stores file securely in uploads/avatars directory and updates user record.
    """
    if not file.filename:
        raise BadRequestException("No file provided.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise BadRequestException(f"Unsupported image format '{ext}'. Allowed formats: JPG, JPEG, PNG, WEBP.")

    if file.content_type and file.content_type.lower() not in ALLOWED_IMAGE_MIMES:
        raise BadRequestException(f"Unsupported MIME type: {file.content_type}")

    contents = await file.read()
    if len(contents) > MAX_AVATAR_SIZE:
        raise BadRequestException("Profile picture must be 5MB or smaller.")

    if len(contents) == 0:
        raise BadRequestException("The uploaded image file is empty.")

    # Storage directory
    avatars_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
    os.makedirs(avatars_dir, exist_ok=True)

    # Delete previous avatar file if exists
    if current_user.avatar_url and "/uploads/avatars/" in current_user.avatar_url:
        old_filename = os.path.basename(current_user.avatar_url)
        old_path = os.path.join(avatars_dir, old_filename)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    # Save new file
    unique_name = f"cand_{candidate.id}_{uuid.uuid4().hex[:8]}{ext}"
    target_path = os.path.join(avatars_dir, unique_name)
    with open(target_path, "wb") as f:
        f.write(contents)

    # Update database record
    current_user.avatar_url = f"/uploads/avatars/{unique_name}"
    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()

    return {
        "message": "Profile picture uploaded successfully.",
        "avatar_url": current_user.avatar_url,
        "profile_percentage": candidate.profile_percentage
    }

@router.delete("/profile/picture")
def delete_profile_picture(
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove candidate profile picture and delete image file from server."""
    if current_user.avatar_url and "/uploads/avatars/" in current_user.avatar_url:
        filename = os.path.basename(current_user.avatar_url)
        filepath = os.path.join(settings.UPLOAD_DIR, "avatars", filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass

    current_user.avatar_url = None
    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()

    return {"message": "Profile picture removed successfully.", "profile_percentage": candidate.profile_percentage}

# ==================== PROFILE VISIBILITY & PRIVACY ====================

@router.get("/profile/visibility", response_model=ProfileVisibilityResponse)
def get_profile_visibility(
    candidate: Candidate = Depends(get_current_candidate)
):
    """Retrieve candidate's profile visibility status (PUBLIC_TO_RECRUITERS vs PRIVATE)."""
    return {
        "visibility": candidate.visibility or "PUBLIC_TO_RECRUITERS",
        "is_open_to_work": candidate.is_open_to_work if candidate.is_open_to_work is not None else True
    }

@router.put("/profile/visibility", response_model=ProfileVisibilityResponse)
def update_profile_visibility(
    req: ProfileVisibilityUpdate,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Set profile visibility to 'PUBLIC_TO_RECRUITERS' or 'PRIVATE'."""
    val = req.visibility.strip().upper()
    if val not in ["PUBLIC_TO_RECRUITERS", "PRIVATE"]:
        raise BadRequestException("Visibility must be either 'PUBLIC_TO_RECRUITERS' or 'PRIVATE'.")

    candidate.visibility = val
    db.commit()
    return {
        "visibility": candidate.visibility,
        "is_open_to_work": candidate.is_open_to_work
    }

# ==================== CAREER PREFERENCES ====================

@router.get("/career-preferences", response_model=CareerPreferencesResponse)
def get_career_preferences(
    candidate: Candidate = Depends(get_current_candidate)
):
    """Retrieve candidate's saved career preferences."""
    return {
        "preferred_job_titles": candidate.preferred_job_titles or [],
        "preferred_skills": [cs.skill.name for cs in candidate.skills if cs.skill] if candidate.skills else [],
        "preferred_locations": candidate.preferred_locations or [],
        "work_modes": candidate.work_modes or [],
        "employment_types": candidate.employment_types or [],
        "expected_salary_min": float(candidate.expected_salary_min) if candidate.expected_salary_min else None,
        "expected_salary_max": float(candidate.expected_salary_max) if candidate.expected_salary_max else None,
        "salary_currency": candidate.salary_currency or "USD",
        "notice_period_days": candidate.notice_period_days or 0,
        "availability_status": candidate.availability_status or "Immediately",
        "is_open_to_work": candidate.is_open_to_work if candidate.is_open_to_work is not None else True
    }

@router.put("/career-preferences", response_model=CareerPreferencesResponse)
def update_career_preferences(
    req: CareerPreferencesUpdate,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update candidate career preferences."""
    if req.preferred_job_titles is not None:
        candidate.preferred_job_titles = req.preferred_job_titles
    if req.preferred_locations is not None:
        candidate.preferred_locations = req.preferred_locations
    if req.work_modes is not None:
        candidate.work_modes = req.work_modes
    if req.employment_types is not None:
        candidate.employment_types = req.employment_types
    if req.expected_salary_min is not None:
        candidate.expected_salary_min = req.expected_salary_min
    if req.expected_salary_max is not None:
        candidate.expected_salary_max = req.expected_salary_max
    if req.salary_currency is not None:
        candidate.salary_currency = req.salary_currency
    if req.notice_period_days is not None:
        candidate.notice_period_days = req.notice_period_days
    if req.availability_status is not None:
        candidate.availability_status = req.availability_status
    if req.is_open_to_work is not None:
        candidate.is_open_to_work = req.is_open_to_work

    # Also sync preferred skills if provided
    if req.preferred_skills is not None:
        for s_name in req.preferred_skills:
            clean = s_name.strip()
            if not clean:
                continue
            skill_obj = db.query(Skill).filter(Skill.name.ilike(clean)).first()
            if not skill_obj:
                skill_obj = Skill(name=clean, category="General")
                db.add(skill_obj)
                db.commit()
                db.refresh(skill_obj)
            existing = db.query(CandidateSkill).filter(
                CandidateSkill.candidate_id == candidate.id,
                CandidateSkill.skill_id == skill_obj.id
            ).first()
            if not existing:
                db.add(CandidateSkill(candidate_id=candidate.id, skill_id=skill_obj.id, proficiency="Intermediate"))

    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()

    return get_career_preferences(candidate)

# ==================== EDUCATION CRUD ====================

@router.post("/education", status_code=status.HTTP_201_CREATED)
def add_education(
    item: EducationItem,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    edu = CandidateEducation(
        candidate_id=candidate.id,
        institution=item.institution,
        degree=item.degree,
        field_of_study=item.field_of_study,
        graduation_year=item.graduation_year,
        grade=item.grade
    )
    db.add(edu)
    db.commit()
    db.refresh(edu)

    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    return {"message": "Education record added successfully", "id": edu.id}

@router.put("/education/{edu_id}")
def update_education(
    edu_id: int,
    item: EducationItem,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    edu = db.query(CandidateEducation).filter(
        CandidateEducation.id == edu_id,
        CandidateEducation.candidate_id == candidate.id
    ).first()
    if not edu:
        raise NotFoundException("Education record")

    edu.institution = item.institution
    edu.degree = item.degree
    edu.field_of_study = item.field_of_study
    edu.graduation_year = item.graduation_year
    edu.grade = item.grade

    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    return {"message": "Education record updated successfully"}

@router.delete("/education/{edu_id}")
def delete_education(
    edu_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    edu = db.query(CandidateEducation).filter(
        CandidateEducation.id == edu_id,
        CandidateEducation.candidate_id == candidate.id
    ).first()
    if not edu:
        raise NotFoundException("Education record")
    db.delete(edu)
    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    return {"message": "Education record deleted"}

# ==================== EXPERIENCE CRUD ====================

@router.post("/experience", status_code=status.HTTP_201_CREATED)
def add_experience(
    item: ExperienceItem,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    exp = CandidateExperience(
        candidate_id=candidate.id,
        company=item.company,
        position=item.position,
        location=item.location,
        start_date=item.start_date,
        end_date=item.end_date,
        is_current=item.is_current,
        description=item.description
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)

    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    return {"message": "Experience record added successfully", "id": exp.id}

@router.put("/experience/{exp_id}")
def update_experience(
    exp_id: int,
    item: ExperienceItem,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    exp = db.query(CandidateExperience).filter(
        CandidateExperience.id == exp_id,
        CandidateExperience.candidate_id == candidate.id
    ).first()
    if not exp:
        raise NotFoundException("Experience record")

    exp.company = item.company
    exp.position = item.position
    exp.location = item.location
    exp.start_date = item.start_date
    exp.end_date = item.end_date
    exp.is_current = item.is_current
    exp.description = item.description

    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    return {"message": "Experience record updated successfully"}

@router.delete("/experience/{exp_id}")
def delete_experience(
    exp_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    exp = db.query(CandidateExperience).filter(
        CandidateExperience.id == exp_id,
        CandidateExperience.candidate_id == candidate.id
    ).first()
    if not exp:
        raise NotFoundException("Experience record")
    db.delete(exp)
    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    return {"message": "Experience record deleted"}

# ==================== SKILLS CRUD ====================

@router.post("/skills")
def add_or_update_skill(
    skill_name: str,
    proficiency: str = "Intermediate",
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    clean_name = skill_name.strip()
    skill = db.query(Skill).filter(Skill.name.ilike(clean_name)).first()
    if not skill:
        skill = Skill(name=clean_name, category="General")
        db.add(skill)
        db.commit()
        db.refresh(skill)

    cand_skill = db.query(CandidateSkill).filter(
        CandidateSkill.candidate_id == candidate.id,
        CandidateSkill.skill_id == skill.id
    ).first()

    if not cand_skill:
        cand_skill = CandidateSkill(
            candidate_id=candidate.id,
            skill_id=skill.id,
            proficiency=proficiency
        )
        db.add(cand_skill)
    else:
        cand_skill.proficiency = proficiency

    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    return {"message": f"Skill '{skill.name}' saved to profile"}

@router.delete("/skills/{skill_id}")
def remove_skill(
    skill_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cs = db.query(CandidateSkill).filter(
        CandidateSkill.candidate_id == candidate.id,
        CandidateSkill.skill_id == skill_id
    ).first()
    if not cs:
        raise NotFoundException("Candidate skill")
    db.delete(cs)
    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    return {"message": "Skill removed from profile"}

# ==================== PROJECTS CRUD ====================

@router.post("/projects", status_code=status.HTTP_201_CREATED)
def add_project(
    item: ProjectItem,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    proj = CandidateProject(
        candidate_id=candidate.id,
        title=item.title,
        description=item.description,
        technologies=item.technologies,
        project_url=item.project_url,
        github_url=item.github_url,
        image_url=item.image_url,
        start_date=item.start_date,
        end_date=item.end_date,
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)

    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    return {"message": "Project added successfully", "id": proj.id}

@router.put("/projects/{project_id}")
def update_project(
    project_id: int,
    item: ProjectItem,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    proj = db.query(CandidateProject).filter(
        CandidateProject.id == project_id,
        CandidateProject.candidate_id == candidate.id
    ).first()
    if not proj:
        raise NotFoundException("Project record")

    proj.title = item.title
    proj.description = item.description
    proj.technologies = item.technologies
    proj.project_url = item.project_url
    proj.github_url = item.github_url
    proj.image_url = item.image_url
    proj.start_date = item.start_date
    proj.end_date = item.end_date

    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    return {"message": "Project updated successfully"}

@router.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    proj = db.query(CandidateProject).filter(
        CandidateProject.id == project_id,
        CandidateProject.candidate_id == candidate.id
    ).first()
    if not proj:
        raise NotFoundException("Project record")
    db.delete(proj)
    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    return {"message": "Project deleted successfully"}

# ==================== CERTIFICATIONS CRUD ====================

@router.post("/certifications", status_code=status.HTTP_201_CREATED)
def add_certification(
    item: CertificationItem,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cert = CandidateCertification(
        candidate_id=candidate.id,
        name=item.name,
        issuing_organization=item.issuing_organization,
        issue_date=item.issue_date,
        credential_url=item.credential_url
    )
    db.add(cert)
    db.commit()
    db.refresh(cert)

    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    return {"message": "Certification added successfully", "id": cert.id}

@router.put("/certifications/{cert_id}")
def update_certification(
    cert_id: int,
    item: CertificationItem,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cert = db.query(CandidateCertification).filter(
        CandidateCertification.id == cert_id,
        CandidateCertification.candidate_id == candidate.id
    ).first()
    if not cert:
        raise NotFoundException("Certification record")

    cert.name = item.name
    cert.issuing_organization = item.issuing_organization
    cert.issue_date = item.issue_date
    cert.credential_url = item.credential_url

    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    return {"message": "Certification updated successfully"}

@router.delete("/certifications/{cert_id}")
def delete_certification(
    cert_id: int,
    candidate: Candidate = Depends(get_current_candidate),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cert = db.query(CandidateCertification).filter(
        CandidateCertification.id == cert_id,
        CandidateCertification.candidate_id == candidate.id
    ).first()
    if not cert:
        raise NotFoundException("Certification record")
    db.delete(cert)
    candidate.profile_percentage = calculate_profile_percentage(candidate, current_user)
    db.commit()
    return {"message": "Certification deleted successfully"}

# ==================== JOB ALERTS & PREFERENCES ====================

@router.get("/alert-preferences", response_model=Optional[JobAlertPreferenceResponse])
@router.get("/job-alerts", response_model=Optional[JobAlertPreferenceResponse])
def get_alert_preferences(
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    pref = db.query(JobAlertPreference).filter(JobAlertPreference.candidate_id == candidate.id).first()
    return pref

@router.put("/alert-preferences", response_model=JobAlertPreferenceResponse)
@router.put("/job-alerts", response_model=JobAlertPreferenceResponse)
def update_alert_preferences(
    req: JobAlertPreferenceUpdate,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    pref = db.query(JobAlertPreference).filter(JobAlertPreference.candidate_id == candidate.id).first()
    if not pref:
        pref = JobAlertPreference(candidate_id=candidate.id)
        db.add(pref)

    pref.keywords = req.keywords
    pref.preferred_location = req.preferred_location
    pref.preferred_job_type = req.preferred_job_type
    pref.experience_level = req.experience_level
    pref.is_active = req.is_active
    db.commit()
    db.refresh(pref)
    return pref

@router.get("/smart-alerts")
@router.get("/job-alerts/matches")
def get_smart_alerts(
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Generate intelligent job notifications based on candidate profile skills, preferred titles and alert preferences."""
    candidate_skill_ids = [cs.skill_id for cs in candidate.skills if cs.skill]
    query = db.query(Job).filter(Job.status == JobStatusEnum.PUBLISHED)

    # 1. Check alert preference keywords and locations
    pref = db.query(JobAlertPreference).filter(JobAlertPreference.candidate_id == candidate.id).first()
    if pref and pref.is_active:
        if pref.preferred_location:
            query = query.filter(Job.location.ilike(f"%{pref.preferred_location.strip()}%"))
        if pref.preferred_job_type:
            query = query.filter(Job.employment_type.ilike(f"%{pref.preferred_job_type.strip()}%"))
        if pref.experience_level:
            query = query.filter(Job.experience_level.ilike(f"%{pref.experience_level.strip()}%"))

    # 2. Check candidate skill matches if skills available
    if candidate_skill_ids:
        query = query.join(JobSkill).filter(JobSkill.skill_id.in_(candidate_skill_ids))

    jobs = query.distinct().order_by(Job.created_at.desc()).limit(15).all()
    return [
        {
            "id": j.id,
            "title": j.title,
            "company_name": j.company.name if j.company else "",
            "location": j.location,
            "employment_type": j.employment_type,
            "created_at": j.created_at,
            "matching_skills": [js.skill.name for js in j.required_skills if js.skill_id in candidate_skill_ids]
        }
        for j in jobs
    ]

# ==================== RESUME BUILDER PDF EXPORT ====================

RESUME_BUILDER_SECTIONS = [
    "summary", "skills", "experience", "projects", "education",
    "certifications", "links",
]


def _resolve_resume_builder_sections(sections: Optional[str]) -> List[str]:
    """Preserve an explicitly empty selection while defaulting omitted options."""
    if sections is None:
        return list(RESUME_BUILDER_SECTIONS)
    return [
        item.strip()
        for item in sections.split(",")
        if item.strip() in RESUME_BUILDER_SECTIONS
    ]

@router.get("/resume-builder/download-pdf")
@router.get("/resume-builder/pdf")
def download_built_resume(
    current_user: User = Depends(get_current_user),
    candidate: Candidate = Depends(get_current_candidate),
    template: str = Query("classic_ats"),
    accent: str = Query("#5B7C3C"),
    font: str = Query("Arial"),
    spacing: float = Query(1.0, ge=0.75, le=1.2),
    sections: Optional[str] = Query(None, max_length=160),
):
    """Generate a template-aware multi-page PDF from the shared profile data."""
    allowed_templates = {
        "classic_ats", "modern_professional", "minimalist",
        "two_column", "executive", "fresh_graduate",
    }
    if template not in allowed_templates:
        template = "classic_ats"
    if not (len(accent) == 7 and accent.startswith("#") and all(ch in "0123456789abcdefABCDEF" for ch in accent[1:])):
        accent = "#5B7C3C"
    font_map = {
        "Arial": "Helvetica", "Calibri": "Helvetica", "Helvetica": "Helvetica",
        "Georgia": "Times-Roman", "Garamond": "Times-Roman",
    }
    body_font = font_map.get(font, "Helvetica")
    bold_font = "Times-Bold" if body_font == "Times-Roman" else "Helvetica-Bold"
    italic_font = "Times-Italic" if body_font == "Times-Roman" else "Helvetica-Oblique"
    visible_sections = _resolve_resume_builder_sections(sections)

    output = io.BytesIO()
    p = canvas.Canvas(output, pagesize=letter)
    p.setTitle(f"{current_user.full_name or 'Candidate'} - SkillSphere Resume")

    page_width, page_height = letter
    left, right = (190, page_width - 38) if template == "two_column" else (50, page_width - 50)
    max_width = right - left
    y = page_height - 55
    sidebar_y = page_height - 55
    accent_color = HexColor(accent)

    def draw_page_background():
        if template == "two_column":
            p.setFillColor(HexColor("#EEF1E8"))
            p.rect(0, 0, 164, page_height, fill=1, stroke=0)
        if template == "modern_professional":
            p.setFillColor(HexColor("#F5F7F1"))
            p.rect(0, page_height - 24, page_width, 24, fill=1, stroke=0)

    def new_page():
        nonlocal y, sidebar_y
        p.showPage()
        draw_page_background()
        y = page_height - 55
        sidebar_y = page_height - 55

    def ensure_space(height=20):
        nonlocal y
        if y - height < 50:
            new_page()

    def draw_wrapped(value, font=None, size=9, indent=0, line_gap=None):
        """Draw text with wrapping and automatic page breaks."""
        nonlocal y
        if value is None:
            return
        text = str(value).strip()
        if not text:
            return
        font = font or body_font
        line_gap = line_gap if line_gap is not None else 3 * spacing
        # ReportLab's built-in Helvetica fonts use WinAnsi; replace unsupported
        # characters safely so a candidate's data cannot break PDF generation.
        text = text.encode("cp1252", errors="replace").decode("cp1252")
        words = text.split()
        p.setFont(font, size)
        line = ""
        for word in words:
            trial = f"{line} {word}".strip()
            if p.stringWidth(trial, font, size) <= max_width - indent:
                line = trial
            else:
                if line:
                    ensure_space(size + line_gap)
                    p.drawString(left + indent, y, line)
                    y -= size + line_gap
                # Split exceptionally long URLs/tokens to avoid drawing off-page.
                if p.stringWidth(word, font, size) > max_width - indent:
                    chunk = ""
                    for char in word:
                        if p.stringWidth(chunk + char, font, size) <= max_width - indent:
                            chunk += char
                        else:
                            ensure_space(size + line_gap)
                            p.drawString(left + indent, y, chunk)
                            y -= size + line_gap
                            chunk = char
                    line = chunk
                else:
                    line = word
        if line:
            ensure_space(size + line_gap)
            p.drawString(left + indent, y, line)
            y -= size + line_gap

    def draw_section(title):
        nonlocal y
        ensure_space(34)
        y -= 6
        p.setFillColor(accent_color if template != "executive" else HexColor("#222222"))
        p.setFont(bold_font, 11)
        p.drawString(left, y, title.upper())
        y -= 5
        p.setStrokeColor(accent_color)
        p.line(left, y, right, y)
        y -= 14
        p.setFillColor(HexColor("#222222"))

    def draw_item_title(title, subtitle=None):
        nonlocal y
        ensure_space(28)
        draw_wrapped(title, bold_font, 9.5)
        if subtitle:
            draw_wrapped(subtitle, body_font, 9)

    def draw_link(label, url, indent=8):
        nonlocal y
        parsed = urlsplit(str(url or ""))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return
        top = y + 10
        draw_wrapped(f"{label}: {url}", body_font, 8, indent=indent)
        p.linkURL(str(url), (left + indent, max(45, y), right, min(page_height - 24, top)), relative=0, thickness=0)

    def draw_sidebar(values, title):
        nonlocal sidebar_y
        sidebar_x, sidebar_width = 30, 112
        p.setFont(bold_font, 9)
        p.setFillColor(accent_color)
        if sidebar_y < 66:
            return
        p.drawString(sidebar_x, sidebar_y, title.upper())
        sidebar_y -= 17
        p.setFont(body_font, 8)
        p.setFillColor(HexColor("#303329"))
        for value in values:
            for line in simpleSplit(str(value), body_font, 8, sidebar_width):
                if sidebar_y < 48:
                    return
                p.drawString(sidebar_x, sidebar_y, line)
                sidebar_y -= 11
            sidebar_y -= 4

    draw_page_background()

    # Header and contact details
    name = current_user.full_name or "Candidate"
    if template in {"classic_ats", "minimalist"}:
        draw_wrapped(name, bold_font, 20)
    else:
        p.setFillColor(accent_color)
        draw_wrapped(name, bold_font, 22 if template == "executive" else 20)
        p.setFillColor(HexColor("#222222"))
    if candidate.headline:
        draw_wrapped(candidate.headline, italic_font, 10)
    contacts = [candidate.contact_email or current_user.email, candidate.phone, candidate.location]
    contacts = [str(item).strip() for item in contacts if item]
    if template == "two_column":
        draw_sidebar(contacts, "Contact")
    elif contacts:
        draw_wrapped(" | ".join(contacts), body_font, 8.5)
    y -= 4
    p.setStrokeColorRGB(0.15, 0.18, 0.22)
    p.line(left, y, right, y)
    y -= 16

    skill_names = [cs.skill.name for cs in candidate.skills if cs.skill and cs.skill.name]
    if template == "two_column":
        draw_sidebar(skill_names, "Skills")

    def render_summary():
        nonlocal y
        summary = candidate.bio or candidate.headline
        if summary:
            draw_section("Professional Summary")
            draw_wrapped(summary)
            y_spacing = 6 * spacing
            y -= y_spacing

    def render_skills():
        nonlocal y
        if skill_names and template != "two_column":
            draw_section("Technical Skills")
            draw_wrapped(" | ".join(skill_names))
            y -= 6 * spacing

    def render_experience():
        nonlocal y
        if candidate.experiences:
            draw_section("Work Experience")
            for exp in candidate.experiences:
                title = " - ".join(str(value) for value in (exp.position, exp.company) if value)
                if title:
                    draw_item_title(title)
                dates = " - ".join(str(value) for value in (exp.start_date, "Present" if exp.is_current else exp.end_date) if value)
                if dates:
                    draw_wrapped(dates, italic_font, 8)
                if exp.location:
                    draw_wrapped(exp.location, body_font, 8)
                if exp.description:
                    draw_wrapped(exp.description, body_font, 9, indent=8)
                y -= 6 * spacing

    def render_projects():
        nonlocal y
        if candidate.projects:
            draw_section("Projects")
            for project in candidate.projects:
                if project.title:
                    draw_item_title(project.title)
                if project.start_date or project.end_date:
                    draw_wrapped(" – ".join(item for item in (project.start_date, project.end_date) if item), italic_font, 8)
                if project.description:
                    draw_wrapped(project.description, body_font, 9, indent=8)
                if project.technologies:
                    draw_wrapped(f"Technologies: {project.technologies}", bold_font, 8, indent=8)
                if project.project_url:
                    draw_link("Live project", project.project_url)
                if project.github_url:
                    draw_link("GitHub", project.github_url)
                y -= 6 * spacing

    def render_education():
        nonlocal y
        if candidate.educations:
            draw_section("Education")
            for edu in candidate.educations:
                degree = " - ".join(str(value) for value in (edu.degree, edu.field_of_study) if value)
                if degree:
                    draw_item_title(degree, edu.institution)
                details = [str(edu.graduation_year)] if edu.graduation_year else []
                if edu.grade:
                    details.append(f"Grade: {edu.grade}")
                if details:
                    draw_wrapped(" | ".join(details), body_font, 8)
                y -= 5 * spacing

    def render_certifications():
        nonlocal y
        if candidate.certifications:
            draw_section("Certifications")
            for cert in candidate.certifications:
                draw_item_title(cert.name, cert.issuing_organization)
                if cert.issue_date:
                    draw_wrapped(f"Issue Date: {cert.issue_date}", body_font, 8)
                if cert.credential_url:
                    draw_link("Credential", cert.credential_url)
                y -= 5 * spacing

    def render_links():
        professional_links = [
            ("LinkedIn", candidate.linkedin_url), ("GitHub", candidate.github_url),
            ("Portfolio", candidate.portfolio_url), ("Professional link", candidate.additional_url),
        ]
        professional_links = [(label, url) for label, url in professional_links if url]
        if professional_links and template != "two_column":
            draw_section("Professional Links")
            for label, url in professional_links:
                draw_link(label, url)

    # Keep the vertical cursor mutable so small section renderers stay readable.
    nonlocal_y = [y]
    renderer_map = {
        "summary": render_summary, "skills": render_skills, "experience": render_experience,
        "projects": render_projects, "education": render_education,
        "certifications": render_certifications, "links": render_links,
    }
    # Section helpers update the shared cursor after each rendered section.
    for section_key in visible_sections:
        y = nonlocal_y[0]
        renderer_map[section_key]()
        nonlocal_y[0] = y

    if template == "two_column":
        professional_links = [url for url in (candidate.linkedin_url, candidate.github_url, candidate.portfolio_url, candidate.additional_url) if url]
        if professional_links:
            draw_sidebar(professional_links, "Links")

    p.save()
    output.seek(0)
    filename = f"{name.replace(' ', '_')}_Resume.pdf"
    return Response(
        content=output.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
