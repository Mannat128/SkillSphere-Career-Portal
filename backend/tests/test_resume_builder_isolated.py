import pytest

from app.models.candidate import Candidate
from app.models.user import User, UserRole
from app.routers.candidate import (
    RESUME_BUILDER_SECTIONS,
    _resolve_resume_builder_sections,
    download_built_resume,
)


@pytest.mark.parametrize(
    "template",
    [
        "classic_ats",
        "modern_professional",
        "minimalist",
        "two_column",
        "executive",
        "fresh_graduate",
    ],
)
def test_all_resume_builder_templates_generate_pdf(template):
    user = User(
        id=1,
        email="synthetic-candidate@example.test",
        full_name="Synthetic Candidate",
        hashed_password="unused",
        role=UserRole.CANDIDATE,
    )
    candidate = Candidate(
        id=1,
        user_id=user.id,
        headline="Synthetic Software Engineer",
        bio="Synthetic profile summary for template rendering.",
        linkedin_url="https://linkedin.example.test/synthetic",
    )

    response = download_built_resume(
        current_user=user,
        candidate=candidate,
        template=template,
        accent="#5B7C3C",
        font="Arial",
        spacing=1.0,
        sections=None,
    )

    assert response.media_type == "application/pdf"
    assert response.body.startswith(b"%PDF-")
    assert len(response.body) > 500


def test_resume_builder_distinguishes_no_selection_from_default_sections():
    assert _resolve_resume_builder_sections(None) == RESUME_BUILDER_SECTIONS
    assert _resolve_resume_builder_sections("") == []
    assert _resolve_resume_builder_sections("summary,unknown,links") == ["summary", "links"]
