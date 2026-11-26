import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models import Company, Job, JobSkill, JobStatusEnum, Recruiter, Skill, User, UserRole
from app.services.assistant_engine import answer_assistant
from app.services.assistant_company_catalog import COMPANY_NOT_FOUND, catalog_options, lookup_catalog
from app.services.ai_service import AIService


@pytest.fixture
def career_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    recruiter_user = User(
        id=8801, email="career-recruiter@example.test", hashed_password="unused",
        full_name="Synthetic Recruiter", role=UserRole.RECRUITER,
    )
    candidate = User(
        id=8802, email="career-candidate@example.test", hashed_password="unused",
        full_name="Synthetic Candidate", role=UserRole.CANDIDATE,
    )
    company = Company(
        id=8811, name="Acme Labs", description="Builds synthetic developer tools.",
        industry="Technology", location="Pune", website="https://acme.example",
        contact_email="private-contact@acme.example", contact_phone="555-0100",
    )
    no_openings = Company(
        id=8812, name="Quiet Systems", description="Registered without an opening.",
    )
    recruiter = Recruiter(user_id=recruiter_user.id, company=company)
    python = Skill(name="Python", category="Backend")
    published = Job(
        id=8821, recruiter=recruiter, company=company, title="Python Engineer",
        description="Build and maintain backend services.", location="Pune",
        employment_type="Full-time", experience_level="Mid-Level",
        min_salary=100000, max_salary=140000, salary_currency="INR",
        qualifications="Two years of API experience.", status=JobStatusEnum.PUBLISHED,
    )
    published.required_skills.append(JobSkill(skill=python, is_required=True))
    draft = Job(
        id=8822, recruiter=recruiter, company=company, title="Draft Designer",
        description="Unpublished role details must not be shown.", location="Pune",
        status=JobStatusEnum.DRAFT,
    )
    closed = Job(
        id=8823, recruiter=recruiter, company=company, title="Closed Engineer",
        description="Closed role details must not be shown.", location="Mumbai",
        status=JobStatusEnum.CLOSED,
    )
    db.add_all([recruiter_user, candidate, company, no_openings, recruiter, python, published, draft, closed])
    db.commit()
    try:
        yield db, candidate, company, no_openings
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_catalog_options_use_registered_companies_and_published_jobs_only(career_db):
    db, _candidate, _company, _no_openings = career_db
    result = catalog_options(db)
    assert {item["name"] for item in result["companies"]} == {"Acme Labs", "Quiet Systems"}
    assert result["job_titles"] == ["Python Engineer"]
    assert result["locations"] == ["Pune"]
    assert result["skills"] == ["Python"]


def test_company_lookup_excludes_private_fields_and_unpublished_jobs(career_db):
    db, _candidate, company, _no_openings = career_db
    result = lookup_catalog(db, company_id=company.id)
    assert result["source"] == "skillsphere_database"
    assert result["company"]["name"] == "Acme Labs"
    assert "contact_email" not in result["company"]
    assert "contact_phone" not in result["company"]
    assert [item["title"] for item in result["jobs"]] == ["Python Engineer"]
    assert result["jobs"][0]["required_skills"] == ["Python"]
    assert result["jobs"][0]["salary"] == {"minimum": 100000.0, "maximum": 140000.0, "currency": "INR"}


def test_job_search_filters_role_location_and_skill_and_omits_missing_salary(career_db):
    db, _candidate, _company, _no_openings = career_db
    result = lookup_catalog(db, target_role="Engineer", location="Pune", skill="Python")
    assert [item["title"] for item in result["jobs"]] == ["Python Engineer"]
    assert lookup_catalog(db, target_role="Engineer", location="Delhi")["jobs"] == []
    assert lookup_catalog(db, skill="SQL")["jobs"] == []


def test_unknown_company_and_registered_company_without_jobs_are_honest(career_db):
    db, _candidate, _company, no_openings = career_db
    missing = lookup_catalog(db, company_name="Imaginary Corporation")
    assert missing["message"] == COMPANY_NOT_FOUND
    no_jobs = lookup_catalog(db, company_id=no_openings.id)
    assert no_jobs["jobs"] == []
    assert no_jobs["message"] == (
        "Quiet Systems is registered on SkillSphere, but there are currently no active job openings."
    )


def test_company_partial_match_is_marked_ambiguous(career_db):
    db, _candidate, _company, _no_openings = career_db
    db.add(Company(name="Acme Telecom"))
    db.commit()
    result = lookup_catalog(db, company_name="Acme")
    assert result["match_status"] == "ambiguous"
    assert {item["name"] for item in result["companies"]} == {"Acme Labs", "Acme Telecom"}


def test_career_chat_catalog_answer_is_database_backed_and_role_navigation_is_safe(career_db, monkeypatch):
    db, candidate, _company, _no_openings = career_db

    def no_gemini(*_args, **_kwargs):
        raise AssertionError("Company and job facts must not depend on Gemini or external research")

    monkeypatch.setattr(AIService, "_request_text", staticmethod(no_gemini))
    response = answer_assistant(db, "What jobs are available at Acme Labs?", "candidate", user=candidate)
    assert "Python Engineer" in response["reply"]
    assert "Draft Designer" not in response["reply"]
    assert "Closed Engineer" not in response["reply"]
    assert response["actions"] == [{
        "label": "Find Jobs",
        "path": "/candidate/jobs",
    }]
    assert response["intent"] == "company_information"
    assert response["confidence"] >= 0.9


def test_career_catalog_follow_up_resolves_company_from_private_chat_history(career_db, monkeypatch):
    db, candidate, _company, _no_openings = career_db
    monkeypatch.setattr(
        AIService, "_request_text",
        staticmethod(lambda *_args, **_kwargs: pytest.fail("Catalog follow-up must use database facts directly")),
    )
    first = answer_assistant(db, "Tell me about Acme Labs", "candidate", user=candidate)
    follow_up = answer_assistant(
        db, "What about their jobs?", "candidate",
        history=[{"role": "user", "text": "Tell me about Acme Labs"}], user=candidate,
    )
    assert "Acme Labs" in follow_up["reply"]
    assert "Python Engineer" in follow_up["reply"]


def test_career_catalog_does_not_offer_candidate_navigation_to_recruiters(career_db):
    db, _candidate, company, _no_openings = career_db
    result = answer_assistant(db, "What jobs are at Acme Labs?", "recruiter")
    assert "Python Engineer" in result["reply"]
    assert result["actions"] == []


def test_database_company_answers_follow_user_language_without_gemini(career_db, monkeypatch):
    db, candidate, _company, _no_openings = career_db
    monkeypatch.setattr(
        AIService, "_request_text",
        staticmethod(lambda *_args, **_kwargs: pytest.fail("Database lookup must not call Gemini")),
    )
    response = answer_assistant(db, "कौन सी कंपनियाँ SkillSphere पर हैं?", "candidate", user=candidate)
    assert "SkillSphere" in response["reply"]
    assert "Acme Labs" in response["reply"]
    assert "की सत्यापित जानकारी" in response["reply"]


@pytest.mark.parametrize(
    "language,header,quick_reply,field_label",
    [
        ("en", "Verified SkillSphere information:", "Find jobs", "Description"),
        ("hi", "SkillSphere की सत्यापित जानकारी:", "नौकरियाँ खोजें", "विवरण"),
        ("hinglish", "SkillSphere ki verified jaankari:", "Jobs dekhein", "Description"),
        ("pa", "SkillSphere ਦੀ ਪ੍ਰਮਾਣਿਤ ਜਾਣਕਾਰੀ:", "ਨੌਕਰੀਆਂ ਲੱਭੋ", "ਵੇਰਵਾ"),
        ("pa_latn", "SkillSphere di verified jaankari:", "Jobs labho", "Verva"),
    ],
)
def test_company_catalog_reply_and_quick_replies_follow_selected_language(
    career_db, language, header, quick_reply, field_label,
):
    db, candidate, *_ = career_db
    response = answer_assistant(
        db, "Tell me about Acme Labs", "candidate", user=candidate,
        selected_language=language,
    )

    assert response["language"] == language
    assert response["reply"].startswith(header)
    assert f"{field_label}:" in response["reply"]
    assert "Acme Labs" in response["reply"]
    assert "Builds synthetic developer tools." in response["reply"]
    assert response["actions"] == [{"label": "Find Jobs", "path": "/candidate/jobs"}]
    assert response["suggestions"][0] == quick_reply
