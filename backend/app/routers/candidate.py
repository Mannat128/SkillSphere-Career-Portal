import os
import io
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, status, Response, UploadFile, File
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
from reportlab.pdfgen import canvas

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
        "phone": candidate.phone,
        "location": candidate.location,
        "headline": candidate.headline,
        "bio": candidate.bio,
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
    if req.phone is not None:
        candidate.phone = req.phone
    if req.location is not None:
        candidate.location = req.location
    if req.headline is not None:
        candidate.headline = req.headline
    if req.bio is not None:
        candidate.bio = req.bio

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
        project_url=item.project_url
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

@router.get("/resume-builder/download-pdf")
@router.get("/resume-builder/pdf")
def download_built_resume(
    current_user: User = Depends(get_current_user),
    candidate: Candidate = Depends(get_current_candidate)
):
    """Generate and stream a professional PDF resume using candidate's verified profile information."""
    output = io.BytesIO()
    p = canvas.Canvas(output, pagesize=letter)
    p.setTitle(f"{current_user.full_name} – SkillSphere Resume")

    # Header Name & Contact
    p.setFont("Helvetica-Bold", 20)
    p.drawString(50, 750, current_user.full_name)

    p.setFont("Helvetica", 10)
    contact_parts = [current_user.email]
    if candidate.phone:
        contact_parts.append(candidate.phone)
    if candidate.location:
        contact_parts.append(candidate.location)
    p.drawString(50, 735, " | ".join(contact_parts))
    p.line(50, 725, 560, 725)

    y = 705

    # Professional Summary
    if candidate.bio or candidate.headline:
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, "PROFESSIONAL SUMMARY")
        y -= 15
        p.setFont("Helvetica", 10)
        summary_text = candidate.bio or candidate.headline
        p.drawString(50, y, summary_text[:100])
        y -= 25

    # Technical Skills
    if candidate.skills:
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, "TECHNICAL SKILLS")
        y -= 15
        p.setFont("Helvetica", 10)
        skill_names = [cs.skill.name for cs in candidate.skills if cs.skill]
        p.drawString(50, y, ", ".join(skill_names[:12]))
        y -= 25

    # Experience
    if candidate.experiences:
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, "WORK EXPERIENCE")
        y -= 15
        p.setFont("Helvetica", 10)
        for exp in candidate.experiences[:3]:
            p.setFont("Helvetica-Bold", 10)
            p.drawString(50, y, f"{exp.position} - {exp.company}")
            y -= 12
            p.setFont("Helvetica", 9)
            if exp.description:
                p.drawString(60, y, exp.description[:90])
                y -= 15
            y -= 5

    # Education
    if candidate.educations:
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, "EDUCATION")
        y -= 15
        for edu in candidate.educations[:2]:
            p.setFont("Helvetica-Bold", 10)
            p.drawString(50, y, f"{edu.degree} in {edu.field_of_study or 'General Studies'}")
            y -= 12
            p.setFont("Helvetica", 9)
            p.drawString(60, y, f"{edu.institution} ({edu.graduation_year or 'Completed'})")
            y -= 18

    p.showPage()
    p.save()
    output.seek(0)

    filename = f"{current_user.full_name.replace(' ', '_')}_Resume.pdf"
    return Response(
        content=output.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
