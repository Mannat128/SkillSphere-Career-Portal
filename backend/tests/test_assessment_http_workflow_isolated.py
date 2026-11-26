"""HTTP-level assessment workflow test backed only by in-memory SQLite."""

import datetime
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import (
    get_current_candidate,
    get_current_recruiter,
    get_current_user,
)
from app.database.base import Base
from app.database.session import get_db
from app.models.application import Application, ApplicationStatusEnum
from app.models.audit import AuditLog
from app.models.candidate import Candidate
from app.models.job import Job, JobStatusEnum
from app.models.proctoring import ProctoringSession
from app.models.recruiter import Company, Recruiter
from app.models.recruiter_assessment import AssessmentAssignment
from app.models.user import User, UserRole
from app.routers import (
    applications,
    assessment_reviews,
    candidate_assessments,
    question_bank,
    recruiter,
    recruiter_assessments,
)
from app.routers import proctoring
from app.services.storage_service import StorageService


@pytest.fixture
def assessment_http_env(monkeypatch, tmp_path):
    """Construct a lifespan-free API and ephemeral in-memory database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    db = TestSession()

    recruiter_user = User(
        email="synthetic.recruiter@example.invalid",
        hashed_password="unused-test-hash",
        full_name="Synthetic Recruiter",
        role=UserRole.RECRUITER,
    )
    candidate_user = User(
        email="synthetic.candidate@example.invalid",
        hashed_password="unused-test-hash",
        full_name="Synthetic Candidate",
        role=UserRole.CANDIDATE,
    )
    other_candidate_user = User(
        email="synthetic.other@example.invalid",
        hashed_password="unused-test-hash",
        full_name="Synthetic Other Candidate",
        role=UserRole.CANDIDATE,
    )
    outsider_user = User(
        email="synthetic.outsider@example.invalid",
        hashed_password="unused-test-hash",
        full_name="Synthetic Outsider Recruiter",
        role=UserRole.RECRUITER,
    )
    admin_user = User(
        email="synthetic.admin@example.invalid",
        hashed_password="unused-test-hash",
        full_name="Synthetic Admin",
        role=UserRole.ADMIN,
    )
    company = Company(name="Synthetic Assessment Company")
    outsider_company = Company(name="Synthetic Outsider Company")
    db.add_all([
        recruiter_user, candidate_user, other_candidate_user,
        outsider_user, admin_user, company, outsider_company,
    ])
    db.flush()

    test_recruiter = Recruiter(user_id=recruiter_user.id, company_id=company.id)
    outsider_recruiter = Recruiter(
        user_id=outsider_user.id, company_id=outsider_company.id
    )
    candidate = Candidate(user_id=candidate_user.id)
    other_candidate = Candidate(user_id=other_candidate_user.id)
    db.add_all([test_recruiter, outsider_recruiter, candidate, other_candidate])
    db.flush()

    job = Job(
        recruiter_id=test_recruiter.id,
        company_id=company.id,
        title="Synthetic Backend Engineer",
        description="Synthetic test job.",
        location="Synthetic",
        status=JobStatusEnum.PUBLISHED,
    )
    db.add(job)
    db.commit()
    db.close()

    auth = SimpleNamespace(
        user=recruiter_user,
        candidate=candidate,
        recruiter=test_recruiter,
        admin=admin_user,
    )
    test_app = FastAPI()
    test_app.include_router(question_bank.router, prefix="/api/v1")
    test_app.include_router(applications.router, prefix="/api/v1")
    test_app.include_router(recruiter.router, prefix="/api/v1")
    test_app.include_router(recruiter_assessments.router, prefix="/api/v1")
    test_app.include_router(assessment_reviews.router, prefix="/api/v1")
    test_app.include_router(candidate_assessments.router, prefix="/api/v1")
    test_app.include_router(proctoring.router, prefix="/api/v1")
    test_app.include_router(proctoring.recruiter_router, prefix="/api/v1")
    test_app.include_router(proctoring.admin_router, prefix="/api/v1")

    def override_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    test_app.dependency_overrides[get_db] = override_db
    test_app.dependency_overrides[get_current_candidate] = lambda: auth.candidate
    test_app.dependency_overrides[get_current_recruiter] = lambda: auth.recruiter
    test_app.dependency_overrides[get_current_user] = lambda: auth.user
    test_app.dependency_overrides[proctoring.get_recording_recruiter] = (
        lambda: auth.recruiter
    )
    test_app.dependency_overrides[proctoring.get_recording_admin] = (
        lambda: auth.admin
    )

    private_dir = tmp_path / "private-recordings"
    private_dir.mkdir()
    monkeypatch.setattr(proctoring, "PRIVATE_RECORDING_DIR", private_dir)
    monkeypatch.setattr(StorageService, "PRIVATE_RECORDING_DIR", private_dir, raising=False)

    def save_synthetic_recording(
        cls,
        source_path,
        destination_filename,
        content_type="video/webm",
        idempotency_key=None,
        content_sha256=None,
    ):
        target = private_dir / destination_filename
        if Path(source_path).resolve() != target.resolve():
            shutil.copyfile(source_path, target)
        return {"storage_reference": str(target), "provider": "local"}

    monkeypatch.setattr(
        StorageService,
        "save_recording_with_metadata",
        classmethod(save_synthetic_recording),
    )

    # Trio avoids the Windows Proactor socket-pair startup issue documented in
    # the assistant HTTP integration harness; the supported connection uses
    # loopback and the process has permission for this isolated local test.
    client = TestClient(test_app, backend="trio")
    try:
        with client:
            yield {
                "client": client,
                "app": test_app,
                "auth": auth,
                "db_factory": TestSession,
                "candidate": candidate,
                "other_candidate": other_candidate,
                "other_candidate_user": other_candidate_user,
                "recruiter": test_recruiter,
                "outsider_recruiter": outsider_recruiter,
                "job": job,
                "company": company,
                "outsider_company": outsider_company,
                "private_dir": private_dir,
            }
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_recruiter_to_candidate_to_recruiter_assessment_http_flow(
    assessment_http_env,
):
    env = assessment_http_env
    client = env["client"]
    base = "/api/v1"

    # Candidate applies; no assessment is assigned until recruiter shortlists.
    response = client.post(
        f"{base}/applications/jobs/{env['job'].id}/apply",
        json={"cover_letter": "Synthetic application"},
    )
    assert response.status_code == 201, response.text
    application_id = response.json()["id"]
    assert client.get(f"{base}/candidate/first-round-assessments").json() == []

    # Recruiter creates a real Question Bank item and job-specific config.
    response = client.post(
        f"{base}/question-bank",
        json={
            "question_text": "Which option is correct in this synthetic test?",
            "category": "Python",
            "difficulty": "Easy",
            "option_a": "Correct option",
            "option_b": "Wrong option one",
            "option_c": "Wrong option two",
            "option_d": "Wrong option three",
            "correct_answer": "A",
            "marks": 2,
            "save_to_bank": True,
        },
    )
    assert response.status_code == 201, response.text
    question_id = response.json()["id"]
    now = datetime.datetime.now(datetime.timezone.utc)
    config = {
        "is_enabled": True,
        "title": "Synthetic First Round",
        "instructions": "Synthetic instructions.",
        "total_questions": 1,
        "duration_minutes": 5,
        "total_marks": 2,
        "passing_marks": 1,
        "qualification_rule": ">",
        "negative_marking": False,
        "negative_marks": 0,
        "categories": ["Python"],
        "difficulty_distribution": None,
        "selection_mode": "SPECIFIC",
        "selected_question_ids": [question_id],
        "available_from": (now - datetime.timedelta(minutes=1)).isoformat(),
        "available_until": (now + datetime.timedelta(minutes=10)).isoformat(),
    }
    response = client.post(
        f"{base}/jobs/{env['job'].id}/assessment", json=config
    )
    assert response.status_code == 200, response.text
    assert response.json()["duration_minutes"] == 5
    assert response.json()["passing_marks"] == 1

    # Application remains APPLIED until the recruiter shortlists it.
    response = client.put(
        f"{base}/recruiter/applicants/{application_id}/status",
        json={"status": "SHORTLISTED", "notes": "Synthetic shortlist"},
    )
    assert response.status_code == 200, response.text
    assignments = client.get(
        f"{base}/candidate/first-round-assessments"
    ).json()
    assert len(assignments) == 1
    assignment_id = assignments[0]["id"]

    # Retrying the same shortlist operation remains assignment-idempotent.
    repeat_shortlist = client.put(
        f"{base}/recruiter/applicants/{application_id}/status",
        json={"status": "SHORTLISTED", "notes": "Synthetic retry"},
    )
    assert repeat_shortlist.status_code == 200, repeat_shortlist.text
    assert len(client.get(
        f"{base}/candidate/first-round-assessments"
    ).json()) == 1

    response = client.get(
        f"{base}/candidate/first-round-assessments/{assignment_id}"
    )
    assert response.status_code == 200, response.text
    assert response.json()["can_start"] is True

    response = client.post(
        f"{base}/candidate/first-round-assessments/{assignment_id}/proctoring/consent",
        json={
            "consent_given": True,
            "camera_permission_granted": True,
            "microphone_permission_granted": True,
        },
    )
    assert response.status_code == 200, response.text

    response = client.post(
        f"{base}/candidate/first-round-assessments/{assignment_id}/start"
    )
    assert response.status_code == 200, response.text
    start = response.json()
    assert len(start["questions"]) == 1
    assert "correct_answer" not in start["questions"][0]
    question_id = start["questions"][0]["id"]
    with env["db_factory"]() as db:
        assigned = db.query(AssessmentAssignment).filter(
            AssessmentAssignment.id == assignment_id
        ).one()
        correct_option = assigned.private_answer_key[str(question_id)]

    response = client.post(
        f"{base}/candidate/first-round-assessments/{assignment_id}/proctoring/recording/start"
    )
    assert response.status_code == 200, response.text

    response = client.post(
        f"{base}/candidate/first-round-assessments/{assignment_id}/save-answer",
        json={"question_id": question_id, "selected_option": correct_option},
    )
    assert response.status_code == 200, response.text

    # This is a tiny synthetic WebM container marker, never candidate media.
    response = client.post(
        f"{base}/candidate/first-round-assessments/{assignment_id}/proctoring/recording/upload",
        files={"file": ("synthetic.webm", bytes.fromhex("1A45DFA3") + b"synthetic", "video/webm")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["delete_after"] is None

    response = client.post(
        f"{base}/candidate/first-round-assessments/{assignment_id}/submit",
        json={"final_answers": {str(question_id): correct_option}},
    )
    assert response.status_code == 200, response.text
    assert "obtained_marks" not in response.json()
    assert "review_status" not in response.json()

    db = env["db_factory"]()
    try:
        submitted_attempt = db.query(AssessmentAssignment).filter(
            AssessmentAssignment.id == assignment_id
        ).one().attempt
        recording_session = db.query(ProctoringSession).filter(
            ProctoringSession.assignment_id == assignment_id
        ).one()
        assert submitted_attempt.submitted_at is not None
        assert recording_session.delete_after == submitted_attempt.submitted_at + datetime.timedelta(days=15)
    finally:
        db.close()

    candidate_assignments = client.get(
        f"{base}/candidate/first-round-assessments"
    )
    assert candidate_assignments.status_code == 200
    assert candidate_assignments.json()[0]["status"] == "PENDING_REVIEW"

    candidate_result = client.get(
        f"{base}/candidate/first-round-assessments/{assignment_id}/result"
    )
    assert candidate_result.status_code == 200
    assert "obtained_marks" not in candidate_result.json()
    assert "is_qualified" not in candidate_result.json()

    # Recruiter can inspect the submitted result and make one final decision.
    reviews = client.get(f"{base}/recruiter/assessments/reviews")
    assert reviews.status_code == 200, reviews.text
    assert len(reviews.json()) == 1
    result_id = reviews.json()[0]["id"]
    assert reviews.json()[0]["obtained_marks"] == 2
    assert reviews.json()[0]["review_status"] == "PENDING_REVIEW"

    playback = client.get(
        f"{base}/recruiter/proctoring/assignments/{assignment_id}/recording"
    )
    assert playback.status_code == 200
    assert playback.content.startswith(bytes.fromhex("1A45DFA3"))

    env["auth"].recruiter = env["outsider_recruiter"]
    denied_playback = client.get(
        f"{base}/recruiter/proctoring/assignments/{assignment_id}/recording"
    )
    assert denied_playback.status_code == 403
    env["auth"].recruiter = env["recruiter"]

    admin_playback = client.get(
        f"{base}/admin/proctoring/assignments/{assignment_id}/recording"
    )
    assert admin_playback.status_code == 200
    audit = env["db_factory"]()
    try:
        assert audit.query(AuditLog).filter(
            AuditLog.user_id == env["auth"].admin.id,
            AuditLog.action == "PROCTORING_RECORDING_ACCESSED",
            AuditLog.entity_id == assignment_id,
        ).count() == 1
    finally:
        audit.close()

    response = client.post(
        f"{base}/recruiter/assessments/reviews/{result_id}/review",
        json={"decision": "QUALIFIED", "review_notes": "Synthetic review"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["review_status"] == "QUALIFIED"

    # One-attempt enforcement and candidate-private result fields remain intact.
    response = client.post(
        f"{base}/candidate/first-round-assessments/{assignment_id}/start"
    )
    assert response.status_code == 400
    final_result = client.get(
        f"{base}/candidate/first-round-assessments/{assignment_id}/result"
    )
    assert final_result.status_code == 200
    assert "obtained_marks" not in final_result.json()


def test_assessment_is_not_assigned_to_non_shortlisted_candidate(
    assessment_http_env,
):
    env = assessment_http_env
    env["auth"].candidate = env["other_candidate"]
    env["auth"].user = env["other_candidate_user"]
    response = env["client"].post(
        f"/api/v1/applications/jobs/{env['job'].id}/apply",
        json={"cover_letter": "Synthetic non-shortlisted application"},
    )
    assert response.status_code == 201, response.text
    assert env["client"].get(
        "/api/v1/candidate/first-round-assessments"
    ).json() == []


def test_expired_assessment_http_blocks_camera_consent_and_start(
    assessment_http_env,
):
    env = assessment_http_env
    from app.models.recruiter_assessment import (
        CandidateAssessmentAttempt,
        JobAssessment,
    )

    db = env["db_factory"]()
    try:
        job = Job(
            recruiter_id=env["recruiter"].id,
            company_id=env["company"].id,
            title="Synthetic Expired Assessment Job",
            description="Synthetic test only.",
            location="Synthetic",
            status=JobStatusEnum.PUBLISHED,
        )
        db.add(job)
        db.flush()
        config = JobAssessment(
            job_id=job.id,
            is_enabled=True,
            title="Synthetic Expired Assessment",
            total_questions=1,
            duration_minutes=5,
            total_marks=1,
            passing_marks=0,
        )
        db.add(config)
        application = Application(
            job_id=job.id,
            candidate_id=env["candidate"].id,
            current_status=ApplicationStatusEnum.SHORTLISTED,
        )
        db.add(application)
        db.flush()
        assignment = AssessmentAssignment(
            application_id=application.id,
            job_id=job.id,
            candidate_id=env["candidate"].id,
            job_assessment_id=config.id,
            status="IN_PROGRESS",
            config_snapshot={
                "title": "Synthetic Expired Assessment",
                "duration_minutes": 5,
                "available_until": (
                    datetime.datetime.now(datetime.timezone.utc)
                    - datetime.timedelta(seconds=2)
                ).isoformat(),
            },
            assigned_questions=[],
            private_answer_key={},
        )
        db.add(assignment)
        db.flush()
        db.add(CandidateAssessmentAttempt(
            assignment_id=assignment.id,
            candidate_id=env["candidate"].id,
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
            is_submitted=False,
            saved_answers={},
        ))
        db.commit()
        assignment_id = assignment.id
    finally:
        db.close()

    client = env["client"]
    base = "/api/v1/candidate/first-round-assessments"
    instructions = client.get(f"{base}/{assignment_id}")
    assert instructions.status_code == 200, instructions.text
    assert instructions.json()["assignment_id"] == assignment_id
    assert instructions.json()["availability_status"] == "expired"
    assert instructions.json()["can_start"] is False
    assert instructions.json()["can_access_camera"] is False

    consent = client.post(
        f"{base}/{assignment_id}/proctoring/consent",
        json={
            "consent_given": True,
            "camera_permission_granted": True,
            "microphone_permission_granted": True,
        },
    )
    assert consent.status_code == 400
    start = client.post(f"{base}/{assignment_id}/start")
    assert start.status_code == 400
    recording_start = client.post(
        f"{base}/{assignment_id}/proctoring/recording/start"
    )
    assert recording_start.status_code == 400


def test_recruiter_cannot_review_or_view_another_recruiters_result(
    assessment_http_env,
):
    env = assessment_http_env
    session = env["db_factory"]()
    try:
        # A result owned by a different recruiter is represented through a
        # job whose recruiter_id differs; endpoint ownership must hide it.
        outsider = env["outsider_recruiter"]
        outsider_job = Job(
            recruiter_id=outsider.id,
            company_id=env["outsider_company"].id,
            title="Synthetic Outsider Job",
            description="Synthetic test only.",
            location="Synthetic",
            status=JobStatusEnum.PUBLISHED,
        )
        session.add(outsider_job)
        session.flush()
        # Test only the endpoint's result ownership filter with a real result
        # row assembled from the synthetic isolated schema.
        from app.models.recruiter_assessment import (
            CandidateAssessmentAttempt,
            CandidateAssessmentResult,
            JobAssessment,
        )

        config = JobAssessment(job_id=outsider_job.id, title="Synthetic", total_questions=0, total_marks=1, passing_marks=0)
        session.add(config)
        session.flush()
        application = Application(
            job_id=outsider_job.id,
            candidate_id=env["candidate"].id,
            current_status=ApplicationStatusEnum.SHORTLISTED,
        )
        session.add(application)
        session.flush()
        assignment = AssessmentAssignment(
            application_id=application.id,
            job_id=outsider_job.id,
            candidate_id=env["candidate"].id,
            job_assessment_id=config.id,
            status="PENDING_REVIEW",
            config_snapshot={"title": "Synthetic"},
            assigned_questions=[],
            private_answer_key={},
        )
        session.add(assignment)
        session.flush()
        attempt = CandidateAssessmentAttempt(
            assignment_id=assignment.id,
            candidate_id=env["candidate"].id,
            expires_at=datetime.datetime.utcnow(),
            is_submitted=True,
            submitted_at=datetime.datetime.utcnow(),
        )
        session.add(attempt)
        session.flush()
        result = CandidateAssessmentResult(
            attempt_id=attempt.id,
            assignment_id=assignment.id,
            candidate_id=env["candidate"].id,
            job_id=outsider_job.id,
            obtained_marks=0,
            total_marks=1,
            percentage=0,
            correct_count=0,
            incorrect_count=0,
            unanswered_count=0,
            passing_marks=0,
            qualification_rule=">",
            is_qualified=False,
            qualification_message="Pending review",
            review_status="PENDING_REVIEW",
        )
        session.add(result)
        session.commit()
        result_id = result.id
    finally:
        session.close()

    response = env["client"].get(
        f"/api/v1/recruiter/assessments/reviews?review_status=ALL"
    )
    assert response.status_code == 200, response.text
    assert all(item["candidate_id"] != env["candidate"].id for item in response.json())

    response = env["client"].post(
        f"/api/v1/recruiter/assessments/reviews/{result_id}/review",
        json={"decision": "QUALIFIED"},
    )
    assert response.status_code == 404
