import io
import tempfile
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.exceptions import BadRequestException
from app.schemas.candidate import CandidateProfileUpdate, ProjectItem
from app.services.ocr_service import OCRService
from app.services.resume_parser import ResumeParser
from app.routers.resumes import validate_resume_content


def test_resume_parser_extracts_links_projects_and_confidence():
    source = """Riya Sharma
Senior Software Engineer
riya@example.com | +91 9876543210
Location: Bengaluru, India
https://linkedin.com/in/riya | https://github.com/riya | https://riya.dev

Projects:
- Skill Planner — Built a role-based learning app with React and FastAPI

Certifications:
- AWS Certified Cloud Practitioner
"""
    extracted, confidence = ResumeParser.parse(source)

    assert extracted["full_name"] == "Riya Sharma"
    assert extracted["headline"] == "Senior Software Engineer"
    assert extracted["email"] == "riya@example.com"
    assert extracted["location"] == "Bengaluru, India"
    assert extracted["linkedin_url"].startswith("https://linkedin.com/")
    assert extracted["github_url"].startswith("https://github.com/")
    assert extracted["portfolio_url"] == "https://riya.dev"
    assert extracted["projects"][0]["title"] == "Skill Planner"
    assert "AWS Certified Cloud Practitioner" in extracted["certifications"]
    assert confidence["projects"] > 0


def test_docx_extracts_paragraph_text_without_extracting_archive():
    with tempfile.NamedTemporaryFile(suffix=".docx", dir=Path(__file__).parent, delete=False) as temporary:
        document_path = Path(temporary.name)
    document_xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
      <w:body><w:p><w:r><w:t>Candidate Resume</w:t></w:r></w:p>
      <w:p><w:r><w:t>Python and React</w:t></w:r></w:p></w:body>
    </w:document>"""
    try:
        with zipfile.ZipFile(document_path, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("word/document.xml", document_xml)

        text, metadata = OCRService.process_file(
            str(document_path),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert text == "Candidate Resume\nPython and React"
        assert metadata["extraction_method"] == "DOCX XML text extraction"
    finally:
        document_path.unlink(missing_ok=True)


def test_upload_validator_checks_signatures_and_docx_structure():
    validate_resume_content(".pdf", b"%PDF-1.7 test")
    validate_resume_content(".png", b"\x89PNG\r\n\x1a\nrest")
    with pytest.raises(BadRequestException):
        validate_resume_content(".pdf", b"not a pdf")
    with pytest.raises(BadRequestException):
        validate_resume_content(".docx", b"not a zip")

    docx = io.BytesIO()
    with zipfile.ZipFile(docx, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    validate_resume_content(".docx", docx.getvalue())


def test_professional_links_normalize_https_and_reject_unsafe_schemes():
    profile = CandidateProfileUpdate(github_url="github.com/person")
    assert profile.github_url == "https://github.com/person"
    project = ProjectItem(title="Portfolio", project_url="https://example.com/demo")
    assert project.project_url == "https://example.com/demo"
    with pytest.raises(ValidationError):
        CandidateProfileUpdate(linkedin_url="javascript:alert(1)")
    with pytest.raises(ValidationError):
        ProjectItem(title="Invalid", image_url="file:///secret.png")
