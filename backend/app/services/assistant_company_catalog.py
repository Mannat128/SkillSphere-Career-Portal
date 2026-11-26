"""Verified, public company and job retrieval for Sphera Career Assistant.

This service deliberately reads only SkillSphere's Company, Job, JobSkill and Skill
records. It has no web-search client and never returns recruiter or applicant data.
"""

import re
from typing import Any, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.job import Job, JobSkill, JobStatusEnum
from app.models.recruiter import Company
from app.models.skill import Skill
from app.services.assistant_knowledge import detect_language, normalize_text


COMPANY_NOT_FOUND = (
    "I couldn't find this company in SkillSphere's registered companies. "
    "I can only provide verified company information available on this platform."
)


def _published_jobs(db: Session):
    # Match the existing public job search and application rule: only PUBLISHED
    # postings are available; drafts, moderation states and closed jobs are excluded.
    return db.query(Job).filter(Job.status == JobStatusEnum.PUBLISHED)


def _like_pattern(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip()
    if not value:
        return None
    # Treat user search text literally instead of allowing SQL LIKE wildcards.
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _company_data(company: Company, active_job_count: int = 0) -> dict[str, Any]:
    # Contact email, phone, recruiter relationships and logos are intentionally
    # omitted: the Career Assistant only needs public company profile fields.
    return {
        "id": company.id,
        "name": company.name,
        "description": company.description,
        "industry": company.industry,
        "location": company.location,
        "website": company.website,
        "active_job_count": active_job_count,
    }


def _job_data(job: Job) -> dict[str, Any]:
    salary = None
    if job.min_salary is not None or job.max_salary is not None:
        salary = {
            "minimum": float(job.min_salary) if job.min_salary is not None else None,
            "maximum": float(job.max_salary) if job.max_salary is not None else None,
            "currency": job.salary_currency,
        }
    return {
        "id": job.id,
        "title": job.title,
        "company_id": job.company_id,
        "company_name": job.company.name if job.company else "",
        "description": job.description,
        "responsibilities": job.responsibilities,
        "qualifications": job.qualifications,
        "required_skills": [
            relation.skill.name
            for relation in job.required_skills
            if relation.skill and relation.skill.name
        ],
        "experience_requirement": job.experience_level,
        "location": job.location,
        "job_type": job.employment_type,
        "salary": salary,
        "application_deadline": (
            job.application_deadline.isoformat() if job.application_deadline else None
        ),
    }


def catalog_options(db: Session) -> dict[str, list[dict[str, Any]]]:
    companies = db.query(Company).order_by(Company.name.asc()).limit(300).all()
    titles = [
        title
        for (title,) in _published_jobs(db)
        .with_entities(Job.title)
        .distinct()
        .order_by(Job.title.asc())
        .limit(300)
        .all()
    ]
    locations = [
        location
        for (location,) in _published_jobs(db)
        .with_entities(Job.location)
        .distinct()
        .order_by(Job.location.asc())
        .limit(300)
        .all()
        if location
    ]
    skills = [
        name
        for (name,) in db.query(Skill.name)
        .join(JobSkill, JobSkill.skill_id == Skill.id)
        .join(Job, Job.id == JobSkill.job_id)
        .filter(Job.status == JobStatusEnum.PUBLISHED)
        .distinct()
        .order_by(Skill.name.asc())
        .limit(300)
        .all()
        if name
    ]
    return {
        "companies": [{"id": company.id, "name": company.name} for company in companies],
        "job_titles": titles,
        "locations": locations,
        "skills": skills,
    }


def _resolve_company(
    db: Session,
    company_id: Optional[int],
    company_name: Optional[str],
) -> tuple[Optional[Company], list[Company], str]:
    if company_id is not None:
        company = db.query(Company).filter(Company.id == company_id).first()
        return company, [], "found" if company else "not_found"

    name = (company_name or "").strip()
    if not name:
        return None, [], "none"

    company = db.query(Company).filter(func.lower(Company.name) == name.casefold()).first()
    if company:
        return company, [], "found"

    pattern = _like_pattern(name)
    candidates = db.query(Company).filter(Company.name.ilike(pattern, escape="\\")).order_by(Company.name.asc()).limit(6).all()
    if len(candidates) == 1:
        return candidates[0], [], "found"
    if len(candidates) > 1:
        return None, candidates, "ambiguous"
    return None, [], "not_found"


def _filtered_jobs(
    db: Session,
    *,
    company_id: Optional[int] = None,
    target_role: Optional[str] = None,
    location: Optional[str] = None,
    skill: Optional[str] = None,
    limit: int = 30,
) -> list[Job]:
    query = _published_jobs(db)
    if company_id is not None:
        query = query.filter(Job.company_id == company_id)
    if pattern := _like_pattern(target_role):
        query = query.filter(Job.title.ilike(pattern, escape="\\"))
    if pattern := _like_pattern(location):
        query = query.filter(Job.location.ilike(pattern, escape="\\"))
    if pattern := _like_pattern(skill):
        query = query.join(JobSkill, JobSkill.job_id == Job.id).join(Skill, Skill.id == JobSkill.skill_id).filter(
            Skill.name.ilike(pattern, escape="\\")
        )
    return query.distinct().order_by(Job.created_at.desc(), Job.id.desc()).limit(limit).all()


def lookup_catalog(
    db: Session,
    *,
    company_id: Optional[int] = None,
    company_name: Optional[str] = None,
    target_role: Optional[str] = None,
    location: Optional[str] = None,
    skill: Optional[str] = None,
    show_jobs: bool = False,
) -> dict[str, Any]:
    company, candidates, company_status = _resolve_company(db, company_id, company_name)
    result: dict[str, Any] = {
        "source": "skillsphere_database",
        "match_status": company_status,
        "company": None,
        "companies": [],
        "jobs": [],
        "message": "",
    }

    if company_status == "ambiguous":
        result["companies"] = [_company_data(item) for item in candidates]
        result["message_key"] = "company_ambiguous"
        result["message"] = "I found several registered companies matching that name. Please choose one from the company list."
        return result
    if company_status == "not_found" and (company_id is not None or company_name):
        result["message_key"] = "company_not_found"
        result["message"] = COMPANY_NOT_FOUND
        return result

    if company:
        jobs = _filtered_jobs(
            db,
            company_id=company.id,
            target_role=target_role,
            location=location,
            skill=skill,
        )
        result["company"] = _company_data(company, len(_filtered_jobs(db, company_id=company.id, limit=300)))
        result["jobs"] = [_job_data(job) for job in jobs]
        if not result["company"]["active_job_count"]:
            result["message_key"] = "company_no_openings"
            result["message"] = f"{company.name} is registered on SkillSphere, but there are currently no active job openings."
        elif not jobs:
            result["message_key"] = "company_no_filtered_jobs"
            result["message"] = f"No active SkillSphere job openings at {company.name} match those filters."
        else:
            result["message_key"] = "company_verified"
            result["message"] = f"Verified SkillSphere company and published job information for {company.name}."
        return result

    has_job_filter = bool(target_role or location or skill or show_jobs)
    if has_job_filter:
        jobs = _filtered_jobs(db, target_role=target_role, location=location, skill=skill)
        result["jobs"] = [_job_data(job) for job in jobs]
        result["message_key"] = "matching_jobs" if jobs else "no_matching_jobs"
        result["message"] = (
            "Matching published SkillSphere job openings are listed below."
            if jobs else "No published SkillSphere jobs match those filters."
        )
        return result

    companies = db.query(Company).order_by(Company.name.asc()).limit(100).all()
    result["companies"] = [
        _company_data(company, len(_filtered_jobs(db, company_id=company.id, limit=300)))
        for company in companies
    ]
    result["match_status"] = "listed"
    result["message_key"] = "companies_list" if companies else "no_companies"
    result["message"] = (
        "Registered SkillSphere companies and their published opening counts are listed below."
        if companies else "There are no registered companies in SkillSphere yet."
    )
    return result


def _company_hint(db: Session, normalized_message: str) -> Optional[str]:
    companies = db.query(Company.name).order_by(func.length(Company.name).desc()).limit(300).all()
    for (name,) in companies:
        normalized_name = normalize_text(name)
        if normalized_name and normalized_name in normalized_message:
            return name

    patterns = (
        r"(?:tell me about|what about|details about|company named|company called|about|at)\s+(.+?)\s*$",
        r"(?:registered company|company)\s+(.+?)\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized_message)
        if match:
            candidate = match.group(1).strip(" ?.!,:;")
            candidate = re.sub(r"\s+(?:jobs?|openings?|roles?|hiring|in|near|with)\b.*$", "", candidate)
            if len(candidate) >= 2:
                return candidate[:120]
    return None


def lookup_from_message(db: Session, message: str, history=None) -> Optional[dict[str, Any]]:
    normalized = normalize_text(message)
    company_name = _company_hint(db, normalized)
    follow_up_markers = (
        "their jobs", "their openings", "jobs there", "roles there", "what about them",
        "what about there", "and there", "more about it", "aur jobs", "hor jobs",
        "ਉੱਥੇ ਨੌਕਰੀਆਂ", "वहाँ की नौकरियां", "वहां की नौकरियां",
    )
    # The generic "what about X" company-name pattern can mistake pronouns such
    # as "their jobs" for a company. Let conversational context resolve those.
    generic_follow_up_names = {normalize_text(marker) for marker in follow_up_markers}
    if company_name and (
        normalize_text(company_name) in generic_follow_up_names
        or (
            normalize_text(company_name) in {"their", "there", "them", "it"}
            and any(normalize_text(marker) in normalized for marker in follow_up_markers)
        )
    ):
        company_name = None
    if not company_name and any(normalize_text(marker) in normalized for marker in follow_up_markers):
        for item in reversed(history or []):
            role = item.get("role") if isinstance(item, dict) else getattr(item, "role", None)
            text = item.get("text", "") if isinstance(item, dict) else getattr(item, "text", "")
            if role != "user":
                continue
            company_name = _company_hint(db, normalize_text(text))
            if company_name:
                break
    markers = (
        "company", "companies", "registered", "hiring", "job", "jobs", "opening",
        "openings", "vacancy", "vacancies", "role", "roles", "कंपनी", "कंपनियां",
        "कंपनियाँ", "नौकरी", "नौकरियां", "ਨੌਕਰੀ", "ਕੰਪਨੀ", "jobs dikhao",
        "companies dikhao", "kehri company", "kaun si company", "naukri",
    )
    if not company_name and not any(normalize_text(marker) in normalized for marker in markers):
        return None

    has_company_marker = any(
        normalize_text(marker) in normalized
        for marker in ("company", "companies", "registered", "कंपनी", "कंपनियां", "कंपनियाँ", "ਕੰਪਨੀ")
    )
    has_job_marker = any(
        normalize_text(marker) in normalized
        for marker in ("job", "jobs", "opening", "vacancy", "role", "hiring", "नौकरी", "ਨੌਕਰੀ", "naukri")
    )

    role_query = None
    location_query = None
    skill_query = None
    if not company_name or any(normalize_text(marker) in normalized for marker in ("job", "jobs", "opening", "vacancy", "role", "hiring", "नौकरी", "ਨੌਕਰੀ", "naukri")):
        for (title,) in _published_jobs(db).with_entities(Job.title).distinct().limit(500).all():
            if normalize_text(title) in normalized:
                role_query = title
                break
        for (city,) in _published_jobs(db).with_entities(Job.location).distinct().limit(300).all():
            if city and normalize_text(city) in normalized:
                location_query = city
                break
        for (name,) in db.query(Skill.name).join(JobSkill, JobSkill.skill_id == Skill.id).join(Job, Job.id == JobSkill.job_id).filter(Job.status == JobStatusEnum.PUBLISHED).distinct().limit(500).all():
            if name and normalize_text(name) in normalized:
                skill_query = name
                break

    if company_name:
        return lookup_catalog(
            db,
            company_name=company_name,
            target_role=role_query,
            location=location_query,
            skill=skill_query,
        )
    return lookup_catalog(
        db,
        target_role=role_query,
        location=location_query,
        skill=skill_query,
        show_jobs=has_job_marker and not has_company_marker,
    )


_CATALOG_COPY = {
    "en": {
        "header": "Verified SkillSphere information:",
        "labels": {"description": "Description", "industry": "Industry", "location": "Location", "website": "Official website", "active_openings": "Active openings", "active_count": "{count} active openings", "job_type": "Job type", "experience": "Experience", "salary": "Salary", "required_skills": "Required skills", "not_specified": "Not specified"},
        "messages": {"company_ambiguous": "I found several registered companies matching that name. Please choose one from the list.", "company_not_found": COMPANY_NOT_FOUND, "company_no_openings": "{company} is registered on SkillSphere, but has no active job openings right now.", "company_no_filtered_jobs": "No active SkillSphere openings at {company} match those filters.", "company_verified": "Verified SkillSphere company and published job information for {company}.", "matching_jobs": "Matching published SkillSphere job openings are listed below.", "no_matching_jobs": "No published SkillSphere jobs match those filters.", "companies_list": "Registered SkillSphere companies and their published opening counts are listed below.", "no_companies": "There are no registered companies in SkillSphere yet."},
    },
    "hi": {
        "header": "SkillSphere की सत्यापित जानकारी:",
        "labels": {"description": "विवरण", "industry": "उद्योग", "location": "स्थान", "website": "आधिकारिक वेबसाइट", "active_openings": "सक्रिय openings", "active_count": "{count} सक्रिय openings", "job_type": "नौकरी का प्रकार", "experience": "अनुभव", "salary": "वेतन", "required_skills": "आवश्यक skills", "not_specified": "उल्लेख नहीं है"},
        "messages": {"company_ambiguous": "इस नाम से कई registered companies मिली हैं। सूची से एक चुनें।", "company_not_found": "यह company SkillSphere की registered companies में नहीं मिली। मैं केवल यहाँ उपलब्ध verified company information दे सकता हूँ।", "company_no_openings": "{company} SkillSphere पर registered है, लेकिन अभी कोई active job opening नहीं है।", "company_no_filtered_jobs": "दिए गए filters से {company} की कोई active SkillSphere opening नहीं मिली।", "company_verified": "{company} की verified company और published job जानकारी नीचे है।", "matching_jobs": "मिलती-जुलती published SkillSphere job openings नीचे दी गई हैं।", "no_matching_jobs": "दिए गए filters से कोई published SkillSphere job नहीं मिली।", "companies_list": "Registered SkillSphere companies और उनकी published openings की संख्या नीचे है।", "no_companies": "SkillSphere में अभी कोई company registered नहीं है।"},
    },
    "hinglish": {
        "header": "SkillSphere ki verified jaankari:",
        "labels": {"description": "Description", "industry": "Industry", "location": "Location", "website": "Official website", "active_openings": "Active openings", "active_count": "{count} active openings", "job_type": "Job type", "experience": "Experience", "salary": "Salary", "required_skills": "Required skills", "not_specified": "mention nahi hai"},
        "messages": {"company_ambiguous": "Is naam se kai registered companies mili hain. List se ek choose karein.", "company_not_found": "Yeh company SkillSphere ki registered companies mein nahi mili. Main sirf platform par available verified company information de sakta hoon.", "company_no_openings": "{company} SkillSphere par registered hai, lekin abhi koi active job opening nahi hai.", "company_no_filtered_jobs": "Diye gaye filters se {company} ki koi active SkillSphere opening nahi mili.", "company_verified": "{company} ki verified company aur published job information neeche hai.", "matching_jobs": "Matching published SkillSphere job openings neeche listed hain.", "no_matching_jobs": "Diye gaye filters se koi published SkillSphere job nahi mili.", "companies_list": "Registered SkillSphere companies aur unki published openings ki count neeche hai.", "no_companies": "SkillSphere mein abhi koi company registered nahi hai."},
    },
    "pa": {
        "header": "SkillSphere ਦੀ ਪ੍ਰਮਾਣਿਤ ਜਾਣਕਾਰੀ:",
        "labels": {"description": "ਵੇਰਵਾ", "industry": "ਉਦਯੋਗ", "location": "ਟਿਕਾਣਾ", "website": "ਅਧਿਕਾਰਤ ਵੈੱਬਸਾਈਟ", "active_openings": "ਸਰਗਰਮ openings", "active_count": "{count} ਸਰਗਰਮ openings", "job_type": "ਨੌਕਰੀ ਦੀ ਕਿਸਮ", "experience": "ਤਜਰਬਾ", "salary": "ਤਨਖਾਹ", "required_skills": "ਲੋੜੀਂਦੇ ਹੁਨਰ", "not_specified": "ਦਰਜ ਨਹੀਂ"},
        "messages": {"company_ambiguous": "ਇਸ ਨਾਮ ਨਾਲ ਕਈ registered companies ਮਿਲੀਆਂ ਹਨ। ਸੂਚੀ ਵਿੱਚੋਂ ਇੱਕ ਚੁਣੋ।", "company_not_found": "ਇਹ company SkillSphere ਦੀਆਂ registered companies ਵਿੱਚ ਨਹੀਂ ਮਿਲੀ। ਮੈਂ ਸਿਰਫ਼ platform ਉੱਤੇ ਉਪਲਬਧ verified ਜਾਣਕਾਰੀ ਦੇ ਸਕਦਾ ਹਾਂ।", "company_no_openings": "{company} SkillSphere ਉੱਤੇ registered ਹੈ, ਪਰ ਇਸ ਵੇਲੇ ਕੋਈ active job opening ਨਹੀਂ ਹੈ।", "company_no_filtered_jobs": "ਇਨ੍ਹਾਂ filters ਨਾਲ {company} ਦੀ ਕੋਈ active SkillSphere opening ਨਹੀਂ ਮਿਲੀ।", "company_verified": "{company} ਦੀ verified company ਅਤੇ published job ਜਾਣਕਾਰੀ ਹੇਠਾਂ ਹੈ।", "matching_jobs": "ਮਿਲਦੀਆਂ published SkillSphere job openings ਹੇਠਾਂ ਹਨ।", "no_matching_jobs": "ਇਨ੍ਹਾਂ filters ਨਾਲ ਕੋਈ published SkillSphere job ਨਹੀਂ ਮਿਲੀ।", "companies_list": "Registered SkillSphere companies ਅਤੇ ਉਨ੍ਹਾਂ ਦੀਆਂ published openings ਦੀ ਗਿਣਤੀ ਹੇਠਾਂ ਹੈ।", "no_companies": "SkillSphere ਵਿੱਚ ਹਾਲੇ ਕੋਈ company registered ਨਹੀਂ ਹੈ।"},
    },
    "pa_latn": {
        "header": "SkillSphere di verified jaankari:",
        "labels": {"description": "Verva", "industry": "Industry", "location": "Thaan", "website": "Official website", "active_openings": "Active openings", "active_count": "{count} active openings", "job_type": "Job type", "experience": "Tajurba", "salary": "Tankhaah", "required_skills": "Lohinde skills", "not_specified": "darj nahi"},
        "messages": {"company_ambiguous": "Is naam naal kai registered companies miliyan han. List vichon ikk chuno.", "company_not_found": "Eh company SkillSphere di registered companies vich nahi mili. Main sirf platform te available verified jaankari de sakda haan.", "company_no_openings": "{company} SkillSphere te registered hai, par hun koi active job opening nahi hai.", "company_no_filtered_jobs": "Ehna filters naal {company} di koi active SkillSphere opening nahi mili.", "company_verified": "{company} di verified company ate published job jaankari hethaan hai.", "matching_jobs": "Matching published SkillSphere job openings hethaan listed han.", "no_matching_jobs": "Ehna filters naal koi published SkillSphere job nahi mili.", "companies_list": "Registered SkillSphere companies ate ohna di published openings di ginti hethaan hai.", "no_companies": "SkillSphere vich hale koi company registered nahi hai."},
    },
}


def format_catalog_reply(result: dict[str, Any], language: str) -> str:
    locale = {"hi_latn": "hinglish"}.get(language, language)
    copy = _CATALOG_COPY.get(locale, _CATALOG_COPY["en"])
    key = result.get("message_key")
    company_name = (result.get("company") or {}).get("name", "")
    message = copy["messages"].get(key, result.get("message", ""))
    if "{company}" in message:
        message = message.format(company=company_name)
    if result.get("match_status") == "not_found" and not key:
        message = copy["messages"]["company_not_found"]
    lines = [copy["header"], message]
    company = result.get("company")
    if company:
        lines.append(f"\n{company['name']}")
        for field, label_key in (("description", "description"), ("industry", "industry"), ("location", "location"), ("website", "website")):
            if company.get(field):
                lines.append(f"{copy['labels'][label_key]}: {company[field]}")
        lines.append(f"{copy['labels']['active_openings']}: {company.get('active_job_count', 0)}")
    for item in result.get("companies", []):
        parts = [item["name"]]
        if item.get("industry"):
            parts.append(item["industry"])
        if item.get("location"):
            parts.append(item["location"])
        parts.append(copy["labels"]["active_count"].format(count=item.get("active_job_count", 0)))
        lines.append("• " + " · ".join(parts))
    for job in result.get("jobs", []):
        lines.append(f"\n{job['title']} — {job['company_name']}")
        for field, label_key in (("location", "location"), ("job_type", "job_type"), ("experience_requirement", "experience")):
            if job.get(field):
                lines.append(f"{copy['labels'][label_key]}: {job[field]}")
        salary = job.get("salary")
        if salary:
            minimum = salary.get("minimum")
            maximum = salary.get("maximum")
            amount = "–".join(str(value) for value in (minimum, maximum) if value is not None)
            if amount:
                lines.append(f"{copy['labels']['salary']}: {amount} {salary.get('currency') or ''}".strip())
        else:
            lines.append(f"{copy['labels']['salary']}: {copy['labels']['not_specified']}")
        skills = job.get("required_skills") or []
        lines.append(f"{copy['labels']['required_skills']}: " + (", ".join(skills) if skills else copy['labels']['not_specified']))
        if job.get("experience_requirement") is None:
            lines.append(f"{copy['labels']['experience']}: {copy['labels']['not_specified']}")
        if job.get("description"):
            lines.append("Description: " + job["description"][:900])
    return "\n".join(line for line in lines if line)
