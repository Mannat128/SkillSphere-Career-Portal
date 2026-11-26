from types import SimpleNamespace

import pytest

from app.core.exceptions import SkillSphereException
from app.routers import candidate
from app.routers.recruiter_ai import RecruiterToolRequest, recruiter_ai_tools
from app.services.ai_service import AIService


def _profile():
    skill = SimpleNamespace(skill=SimpleNamespace(name="Python"))
    return SimpleNamespace(
        headline="Software Engineer", contact_email="candidate@example.com",
        phone="555-0100", location="Remote", bio="Builds dependable software.",
        skills=[skill],
        experiences=[SimpleNamespace(position="Developer", company="Example Co", start_date="2022", is_current=True, end_date=None, location="Remote", description="Built APIs.")],
        projects=[SimpleNamespace(title="Portfolio", start_date="2023", end_date="2024", description="A sample project.", technologies="Python", project_url="https://example.com", github_url="https://github.com/example")],
        educations=[SimpleNamespace(degree="BSc", field_of_study="Computing", institution="Example University", graduation_year=2022, grade="A")],
        certifications=[SimpleNamespace(name="Cloud Certificate", issuing_organization="Example Org", issue_date="2024", credential_url="https://example.com/cert")],
        linkedin_url="https://linkedin.com/in/example", github_url="https://github.com/example",
        portfolio_url="https://example.com", additional_url=None,
    )


@pytest.mark.parametrize("template", ["classic_ats", "modern_professional", "minimalist", "two_column", "executive", "fresh_graduate"])
def test_all_resume_builder_templates_generate_pdf(template):
    response = candidate.download_built_resume(
        current_user=SimpleNamespace(full_name="Example Candidate", email="candidate@example.com"),
        candidate=_profile(), template=template, accent="#5B7C3C", font="Arial",
        spacing=1.0, sections="summary,skills,experience,projects,education,certifications,links",
    )
    assert response.media_type == "application/pdf"
    assert response.body.startswith(b"%PDF-")
    assert b"Example Candidate" in response.body


def test_recruiter_ai_endpoint_calls_real_provider(monkeypatch):
    monkeypatch.setattr(AIService, "_request_text", staticmethod(lambda *args, **kwargs: '{"result":"Draft JD","caveats":[]}'))
    result = recruiter_ai_tools(
        RecruiterToolRequest(tool="generate_jd", details={"role": "Engineer"}),
        current_recruiter=SimpleNamespace(id=7),
    )
    assert result["result"] == "Draft JD"


def test_recruiter_tool_provider_failure_is_not_hidden(monkeypatch):
    def unavailable(*args, **kwargs):
        raise SkillSphereException(503, "Provider unavailable")

    monkeypatch.setattr(AIService, "_request_text", staticmethod(unavailable))
    with pytest.raises(SkillSphereException, match="Provider unavailable"):
        recruiter_ai_tools(
            RecruiterToolRequest(tool="suggest_skills", details={"role": "Engineer"}),
            current_recruiter=SimpleNamespace(id=7),
        )
