"""Isolated tests for the database-backed rule assistant and private sessions."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.core.dependencies import get_current_admin, get_current_user, get_db, get_optional_current_user
from app.core.exceptions import ForbiddenException
from app.core.exceptions import UnauthorizedException
from app.models.audit import AuditLog
from app.database.base import Base
from app.models import (
    Application, ApplicationStatusEnum, AssistantFeedback, AssistantUnansweredQuestion,
    Candidate, Company, Job, JobStatusEnum, Recruiter, User, UserRole,
)
from app.models.recruiter_assessment import AssessmentAssignment, CandidateAssessmentResult, JobAssessment
from app.models.interview import Interview, InterviewStatusEnum
from app.models.sphera import AssistantKnowledgeSuggestion, SpheraConversation, SpheraMessage
from app.routers.assistant import (
    AdminFeedbackUpdate, ChatRequest, FeedbackRequest, admin_analytics,
    admin_feedback_history, admin_unanswered, assistant_chat,
    create_guest_session, get_conversation, router, submit_feedback,
    update_feedback,
)
from app.routers import assistant as assistant_router
from app.routers.support_tickets import router as support_ticket_router
from app.services.assistant_engine import _suggestions, answer_assistant, record_unanswered, redact_sensitive_data
from app.services.assistant_knowledge import answer_website_help, detect_language, match_intent


@pytest.fixture
def assistant_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    candidate_user = User(id=9101, email="assistant-candidate@example.test", full_name="Synthetic Candidate", hashed_password="unused", role=UserRole.CANDIDATE)
    other_user = User(id=9102, email="assistant-other@example.test", full_name="Other Candidate", hashed_password="unused", role=UserRole.CANDIDATE)
    recruiter_user = User(id=9103, email="assistant-recruiter@example.test", full_name="Synthetic Recruiter", hashed_password="unused", role=UserRole.RECRUITER)
    admin_user = User(id=9104, email="assistant-admin@example.test", full_name="Synthetic Admin", hashed_password="unused", role=UserRole.ADMIN)
    candidate = Candidate(id=9111, user=candidate_user, profile_percentage=72)
    company = Company(id=9121, name="Example Labs", description="Synthetic public company profile.", industry="Technology", location="Pune", contact_email="private@example.test", contact_phone="555-123-4567")
    recruiter = Recruiter(id=9131, user=recruiter_user, company=company)
    job = Job(id=9141, recruiter=recruiter, company=company, title="Backend Engineer", description="Build platform services.", location="Pune", status=JobStatusEnum.PUBLISHED, application_deadline=datetime.utcnow() + timedelta(days=10))
    closed_job = Job(id=9142, recruiter=recruiter, company=company, title="Closed Engineer", description="Must not appear.", location="Pune", status=JobStatusEnum.CLOSED)
    db.add_all([candidate_user, other_user, recruiter_user, admin_user, candidate, company, recruiter, job, closed_job])
    db.commit()
    try:
        yield db, candidate_user, other_user, recruiter_user, admin_user, candidate, job
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_local_matching_and_language_selection_without_external_providers():
    cases = [
        ("How do I upload my resmue?", "en"),
        ("मेरा resume कैसे upload करूँ?", "hi"),
        ("yr mera resume upload ni hora", "hinglish"),
        ("ਮੇਰਾ resume ਕਿਵੇਂ upload ਕਰਾਂ?", "pa"),
        ("mai apna resume kive upload kara", "pa_latn"),
    ]
    for message, language in cases:
        result = answer_assistant(None, message, "candidate", selected_language="auto")
        assert result["language"] == language
        assert result["reply"]
        assert result["confidence"] >= 0.7
    forced = answer_assistant(None, "How do I upload my resume?", "candidate", selected_language="hi")
    assert forced["language"] == "hi"
    assert "नीचे दिए गए बटन" in forced["reply"]


@pytest.mark.parametrize("language", ["en", "hi", "hinglish", "pa", "pa_latn"])
def test_admin_gets_role_specific_localized_welcome_suggestions(language):
    suggestions = _suggestions("admin", language)

    assert suggestions
    assert suggestions != _suggestions("visitor", language)
    assert any("feedback" in item.lower() or "ਫੀਡਬੈਕ" in item or "feedback" in item for item in suggestions)


def test_ambiguous_and_unknown_queries_are_honest():
    ambiguous = answer_assistant(None, "Help with my profile and resume", "candidate")
    unknown = answer_assistant(None, "Give me private salary database access", "candidate")
    assert ambiguous["confidence"] < 0.7 or ambiguous["reply"]
    assert unknown["actions"] == []
    assert "verified" in unknown["reply"].lower()


def test_account_scoped_live_data_and_recruiter_ownership(assistant_db):
    db, candidate_user, other_user, recruiter_user, _admin, candidate, job = assistant_db
    application = Application(job_id=job.id, candidate_id=candidate.id, current_status=ApplicationStatusEnum.SHORTLISTED)
    db.add(application)
    db.commit()
    candidate_answer = answer_assistant(db, "What is my application status?", "candidate", user=candidate_user)
    assert "SHORTLISTED" in candidate_answer["reply"]
    other_candidate = answer_assistant(db, "What is my application status?", "candidate", user=other_user)
    assert "no applications" in other_candidate["reply"].lower()
    other_candidate_hi = answer_assistant(db, "What is my application status?", "candidate", user=other_user, selected_language="hi")
    assert "आवेदन" in other_candidate_hi["reply"]
    assert "Backend Engineer" not in other_candidate_hi["reply"]
    assert "SHORTLISTED" not in other_candidate_hi["reply"]
    recruiter_answer = answer_assistant(db, "Show my applicants", "recruiter", user=recruiter_user)
    assert "Synthetic Candidate" in recruiter_answer["reply"]
    assert "Example Labs" not in recruiter_answer["reply"] or "Backend Engineer" in recruiter_answer["reply"]


def test_guest_session_history_is_signed_and_isolated(assistant_db):
    db = assistant_db[0]
    token_a = create_guest_session()["session_token"]
    token_b = create_guest_session()["session_token"]
    response = assistant_chat(ChatRequest(message="What is SkillSphere?"), None, db, token_a)
    conversation_id = response["conversation_id"]
    assert db.query(SpheraConversation).filter_by(id=conversation_id, user_id=None).count() == 1
    own = get_conversation(conversation_id, None, db, token_a)
    assert len(own["messages"]) == 2
    with pytest.raises(Exception) as foreign:
        get_conversation(conversation_id, None, db, token_b)
    assert getattr(foreign.value, "status_code", None) == 404
    with pytest.raises(Exception) as missing_session:
        get_conversation(conversation_id, None, db, None)
    assert getattr(missing_session.value, "status_code", None) == 403


def test_sensitive_chat_content_is_redacted_after_intent_processing(assistant_db):
    db = assistant_db[0]
    token = create_guest_session()["session_token"]
    message = (
        "How do I sign in? email alice@example.test phone +1 (415) 555-0132 "
        "password: SecretPass9 Bearer abc.def.ghi api_key=sk-proj-ABCDEFGHIJKLMNOPQRSTUV"
    )
    response = assistant_chat(ChatRequest(message=message), None, db, token)

    assert response["intent"] == "login"
    stored = db.query(SpheraMessage).filter_by(conversation_id=response["conversation_id"], role="user").one()
    conversation = db.query(SpheraConversation).filter_by(id=response["conversation_id"]).one()
    assert "alice@example.test" not in stored.text
    assert "415" not in stored.text
    assert "SecretPass9" not in stored.text
    assert "abc.def.ghi" not in stored.text
    assert "ABCDEFGHIJKLMNOPQRSTUV" not in stored.text
    assert "alice@example.test" not in conversation.title
    assert "sign in" in stored.text


@pytest.mark.parametrize(
    "value,secret",
    [
        ("Contact alice@example.test", "alice@example.test"),
        ("Call +1 (415) 555-0132", "415) 555-0132"),
        ("password: SecretPass9", "SecretPass9"),
        ("Bearer abc.def.ghi", "abc.def.ghi"),
        ("api_key=sk-proj-ABCDEFGHIJKLMNOPQRSTUV", "ABCDEFGHIJKLMNOPQRSTUV"),
        ("Card number: 4111111111111111", "4111111111111111"),
    ],
)
def test_sensitive_data_redactor_preserves_non_sensitive_text(value, secret):
    redacted = redact_sensitive_data(value)
    assert secret not in redacted
    assert "[REDACTED" in redacted
    assert "Contact" in redacted or "Call" in redacted or "password" in redacted or "Bearer" in redacted or "api_key" in redacted or "Card number" in redacted


def test_normal_chat_message_remains_readable_in_private_history(assistant_db):
    db = assistant_db[0]
    token = create_guest_session()["session_token"]
    response = assistant_chat(ChatRequest(message="How do I sign in?"), None, db, token)
    history = get_conversation(response["conversation_id"], None, db, token)
    user_message = next(item for item in history["messages"] if item["role"] == "user")
    assert user_message["text"] == "How do I sign in?"


def test_feedback_single_submission_and_admin_analytics_authorization(assistant_db):
    db, _candidate, _other, _recruiter, admin, *_ = assistant_db
    token = create_guest_session()["session_token"]
    chat = assistant_chat(ChatRequest(message="Tell me about SkillSphere"), None, db, token)
    comment = "alice@example.test called +1 (415) 555-0132; password: SecretPass9; Bearer abc.def.ghi; api_key=sk-proj-ABCDEFGHIJKLMNOPQRSTUV"
    feedback = submit_feedback(FeedbackRequest(message_id=chat["message_id"], rating="not_helpful", category="incomplete", comment=comment), None, db, token)
    assert feedback["submitted"] is True
    stored_feedback = db.query(AssistantFeedback).one()
    assert "alice@example.test" not in stored_feedback.comment
    assert "415" not in stored_feedback.comment
    assert "SecretPass9" not in stored_feedback.comment
    assert "abc.def.ghi" not in stored_feedback.comment
    assert "ABCDEFGHIJKLMNOPQRSTUV" not in stored_feedback.comment
    assert stored_feedback.category == "incomplete"
    with pytest.raises(Exception) as duplicate:
        submit_feedback(FeedbackRequest(message_id=chat["message_id"], rating="helpful"), None, db, token)
    assert getattr(duplicate.value, "status_code", None) == 400
    analytics = admin_analytics(admin, db)
    assert analytics["negative_count"] == 1
    assert db.query(AssistantFeedback).count() == 1


def test_database_unique_index_rejects_duplicate_authenticated_feedback(assistant_db):
    db, candidate_user = assistant_db[0], assistant_db[1]
    chat = assistant_chat(ChatRequest(message="How do I sign in?"), candidate_user, db, None)
    values = dict(
        message_id=chat["message_id"], user_id=candidate_user.id,
        guest_session_hash=None, user_role="candidate", rating="helpful",
        match_score=1.0, status="CLOSED", priority="LOW", created_at=datetime.utcnow(),
    )
    db.add(AssistantFeedback(**values)); db.commit()
    db.add(AssistantFeedback(**values))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_database_unique_index_rejects_duplicate_guest_feedback(assistant_db):
    db = assistant_db[0]
    token = create_guest_session()["session_token"]
    chat = assistant_chat(ChatRequest(message="How do I sign in?"), None, db, token)
    values = dict(
        message_id=chat["message_id"], user_id=None,
        guest_session_hash=assistant_router._guest_hash(token), user_role="visitor",
        rating="helpful", match_score=1.0, status="CLOSED", priority="LOW",
        created_at=datetime.utcnow(),
    )
    db.add(AssistantFeedback(**values)); db.commit()
    db.add(AssistantFeedback(**values))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_assessment_result_answer_is_scoped_to_authenticated_candidate(assistant_db):
    db, candidate_user, other_user, _recruiter, _admin, candidate, job = assistant_db
    assessment = JobAssessment(job_id=job.id, is_enabled=True, title="Synthetic assessment")
    db.add(assessment); db.flush()
    assignment = AssessmentAssignment(
        application_id=1, job_id=job.id, candidate_id=candidate.id,
        job_assessment_id=assessment.id, status="SUBMITTED", config_snapshot={},
        assigned_questions=[], private_answer_key=[],
    )
    db.add(assignment); db.flush()
    db.add(CandidateAssessmentResult(
        attempt_id=1, assignment_id=assignment.id, candidate_id=candidate.id, job_id=job.id,
        obtained_marks=8, total_marks=10, percentage=80, correct_count=8,
        incorrect_count=2, unanswered_count=0, passing_marks=6,
        qualification_rule=">", is_qualified=True, qualification_message="Qualified",
        review_status="PENDING_REVIEW",
    ))
    db.commit()
    own = answer_assistant(db, "What is my assessment result?", "candidate", user=candidate_user)
    foreign = answer_assistant(db, "What is my assessment result?", "candidate", user=other_user)
    assert "8/10" in own["reply"] and "PENDING_REVIEW" in own["reply"]
    assert "8/10" not in foreign["reply"]


def test_candidate_personalized_responses_localize_without_changing_database_values(assistant_db):
    db, candidate_user, _other, _recruiter, _admin, candidate, job = assistant_db
    application = Application(job_id=job.id, candidate_id=candidate.id, current_status=ApplicationStatusEnum.SHORTLISTED)
    db.add(application); db.flush()
    assessment = JobAssessment(job_id=job.id, is_enabled=True, title="Synthetic Technical Assessment")
    db.add(assessment); db.flush()
    assignment = AssessmentAssignment(
        application_id=application.id, job_id=job.id, candidate_id=candidate.id,
        job_assessment_id=assessment.id, status="SUBMITTED", config_snapshot={},
        assigned_questions=[], private_answer_key=[],
    )
    db.add(assignment); db.flush()
    db.add(CandidateAssessmentResult(
        attempt_id=1, assignment_id=assignment.id, candidate_id=candidate.id, job_id=job.id,
        obtained_marks=8, total_marks=10, percentage=80, correct_count=8,
        incorrect_count=2, unanswered_count=0, passing_marks=6,
        qualification_rule=">", is_qualified=True, qualification_message="Qualified",
        review_status="PENDING_REVIEW",
    ))
    db.add(Interview(
        application_id=application.id, recruiter_id=9131, candidate_id=candidate.id,
        job_id=job.id, interview_date=datetime(2030, 1, 2, 15, 4),
        status=InterviewStatusEnum.SCHEDULED,
    ))
    db.commit()

    samples = {
        "en": ("Your recent applications:", "Your assessment results:", "Your profile completion", "Your interviews:"),
        "hi": ("आपके हाल के आवेदन:", "आपके assessment परिणाम:", "आपकी profile", "आपके interviews:"),
        "hinglish": ("Aapki recent applications:", "Aapke assessment results:", "Aapki profile", "Aapke interviews:"),
        "pa": ("ਤੁਹਾਡੀਆਂ ਹਾਲੀਆ ਅਰਜ਼ੀਆਂ:", "ਤੁਹਾਡੇ assessment ਨਤੀਜੇ:", "ਤੁਹਾਡੀ profile", "ਤੁਹਾਡੇ interviews:"),
        "pa_latn": ("Tuhadian recent applications:", "Tuhade assessment results:", "Tuhadi profile", "Tuhade interviews:"),
    }
    queries = (
        "What is my application status?", "What is my assessment result?",
        "What is my profile completion?", "What is my interview schedule?",
    )
    for language, expected in samples.items():
        replies = [
            answer_assistant(db, query, "candidate", user=candidate_user, selected_language=language)
            for query in queries
        ]
        for reply, expected_text in zip(replies, expected):
            assert reply["language"] == language
            assert expected_text in reply["reply"]
        assert "Backend Engineer" in replies[0]["reply"]
        assert "Example Labs" in replies[0]["reply"]
        assert "SHORTLISTED" in replies[0]["reply"]
        assert "Synthetic Technical Assessment" in replies[1]["reply"]
        assert "8/10" in replies[1]["reply"] and "PENDING_REVIEW" in replies[1]["reply"]
        assert "72%" in replies[2]["reply"]
        assert "Backend Engineer" in replies[3]["reply"]
        assert "SCHEDULED" in replies[3]["reply"] and "2030-01-02 15:04" in replies[3]["reply"]

    detected = answer_assistant(
        db, "मेरे आवेदन की स्थिति क्या है?", "candidate", user=candidate_user,
        selected_language="auto",
    )
    assert detected["language"] == "hi"
    assert "आपके हाल के आवेदन:" in detected["reply"]
    assert "SHORTLISTED" in detected["reply"]


def test_admin_unanswered_language_and_frequency_filters_return_real_rows(assistant_db):
    db, _candidate, _other, _recruiter, admin, *_ = assistant_db
    db.add_all([
        AssistantUnansweredQuestion(query_hash="a" * 64, normalized_query="hindi repeated", language="hi", frequency=3, match_score=0.2),
        AssistantUnansweredQuestion(query_hash="b" * 64, normalized_query="punjabi popular", language="pa", frequency=5, match_score=0.3),
        AssistantUnansweredQuestion(query_hash="c" * 64, normalized_query="english single", language="en", frequency=1, match_score=0.1),
    ])
    db.commit()

    hindi_rows = admin_unanswered(language="hi", min_frequency=2, admin=admin, db=db)
    popular_rows = admin_unanswered(language=None, min_frequency=4, admin=admin, db=db)

    assert [(row["question"], row["frequency"]) for row in hindi_rows] == [("hindi repeated", 3)]
    assert [(row["question"], row["language"]) for row in popular_rows] == [("punjabi popular", "pa")]


def test_feedback_moderation_history_records_deltas_and_redacts_sensitive_notes(assistant_db):
    db, _candidate, _other, _recruiter, admin, *_ = assistant_db
    guest_token = create_guest_session()["session_token"]
    chat = assistant_chat(ChatRequest(message="Confidential synthetic transcript must stay private"), None, db, guest_token)
    submitted = submit_feedback(
        FeedbackRequest(message_id=chat["message_id"], rating="not_helpful", category="incomplete"),
        None, db, guest_token,
    )
    feedback_id = db.query(AssistantFeedback).filter_by(id=submitted["feedback_id"]).one().id

    update_feedback(
        feedback_id,
        AdminFeedbackUpdate(
            status="IN_PROGRESS", priority="HIGH", assigned_admin_id=admin.id,
            admin_notes="Investigating. password: SecretNote9 Bearer note.token.value",
        ),
        admin, db,
    )
    update_feedback(
        feedback_id,
        AdminFeedbackUpdate(
            status="RESOLVED", priority="CRITICAL",
            admin_notes="Resolved after review. api_key=sk-proj-ABCDEFGHIJKLMNOPQRSTUV",
        ),
        admin, db,
    )

    history = admin_feedback_history(feedback_id, admin, db)
    assert len(history) == 2
    first, second = history
    assert first["admin_id"] == admin.id and first["created_at"]
    assert first["changes"]["status"] == {"from": "OPEN", "to": "IN_PROGRESS"}
    assert first["changes"]["priority"] == {"from": "MEDIUM", "to": "HIGH"}
    assert first["changes"]["assigned_admin_id"] == {"from": None, "to": admin.id}
    assert "SecretNote9" not in str(first["changes"])
    assert "note.token.value" not in str(first["changes"])
    assert first["changes"]["admin_notes"]["to"].startswith("Investigating")
    assert second["changes"]["status"] == {"from": "IN_PROGRESS", "to": "RESOLVED"}
    assert second["changes"]["priority"] == {"from": "HIGH", "to": "CRITICAL"}
    assert "ABCDEFGHIJKLMNOPQRSTUV" not in str(second["changes"])
    assert second["changes"]["admin_notes"]["from"].startswith("Investigating")
    assert second["changes"]["admin_notes"]["to"].startswith("Resolved after review")
    assert "Confidential synthetic transcript" not in str(history)
    assert "message_id" not in first and "conversation_id" not in first
    audit_rows = db.query(AuditLog).filter_by(action="ASSISTANT_FEEDBACK_UPDATED", entity_id=feedback_id).all()
    assert len(audit_rows) == 2
    assert all(item.user_id == admin.id for item in audit_rows)


def test_feedback_history_and_moderation_routes_are_admin_only(assistant_db):
    from fastapi.routing import APIRoute

    _db, candidate, _other, _recruiter, admin, *_ = assistant_db
    admin_guard = get_current_admin.__defaults__[0].dependency
    with pytest.raises(ForbiddenException):
        admin_guard(candidate)
    assert admin_guard(admin) is admin

    guarded = [
        route for route in router.routes
        if isinstance(route, APIRoute)
        and route.path in {
            "/assistant/admin/feedback/{feedback_id}/history",
            "/assistant/admin/feedback/{feedback_id}",
        }
    ]
    assert {route.path for route in guarded} == {
        "/assistant/admin/feedback/{feedback_id}/history",
        "/assistant/admin/feedback/{feedback_id}",
    }
    assert all(
        any(dependency.call is get_current_admin for dependency in route.dependant.dependencies)
        for route in guarded
    )
    assert not any(
        isinstance(route, APIRoute)
        and route.path.startswith("/assistant/admin/feedback/{feedback_id}/history")
        and route.methods.intersection({"POST", "PUT", "PATCH", "DELETE"})
        for route in router.routes
    )


def test_every_admin_assistant_route_declares_admin_dependency():
    from fastapi.routing import APIRoute

    admin_routes = [route for route in router.routes if isinstance(route, APIRoute) and "/admin/" in route.path]
    assert admin_routes
    assert all(any(dependency.call is get_current_admin for dependency in route.dependant.dependencies) for route in admin_routes)


def test_assistant_rate_limit_rejects_excess_requests(monkeypatch):
    actor = "test:assistant-rate-limit"
    monkeypatch.setattr(assistant_router, "_MAX_PER_MINUTE", 1)
    assistant_router._rate_events.pop(actor, None)
    assistant_router._enforce_rate_limit(actor)
    with pytest.raises(Exception) as limited:
        assistant_router._enforce_rate_limit(actor)
    assert getattr(limited.value, "status_code", None) == 400
    assistant_router._rate_events.pop(actor, None)


@pytest.mark.parametrize("message", ["Please raise a ticket", "Contact support"])
def test_visitor_support_request_guides_to_sign_in_without_ticket_cta(message):
    result = answer_assistant(None, message, "visitor")

    assert result["intent"] == "support"
    assert result["ticket_suggestion"] is False
    assert "sign in" in result["reply"].lower()
    assert result["actions"] == [{"label": "Open: Sign in", "path": "/login"}]


@pytest.mark.parametrize(
    "role,expected_path",
    [
        ("candidate", "/candidate/support"),
        ("recruiter", "/recruiter/support"),
    ],
)
def test_candidate_and_recruiter_support_requests_offer_ticket_flow(role, expected_path):
    result = answer_assistant(None, "Please raise a ticket", role)

    assert result["intent"] == "support"
    assert result["ticket_suggestion"] is True
    assert result["actions"] == [{"label": "Open: Support Center", "path": expected_path}]


def test_generic_contact_question_does_not_offer_support_ticket():
    result = answer_assistant(None, "What is the public contact information?", "visitor")

    assert result["intent"] == "contact"
    assert result["ticket_suggestion"] is False
    assert result["actions"] == []


def test_support_ticket_create_route_requires_authenticated_user():
    with pytest.raises(UnauthorizedException) as unauthorized:
        get_current_user(token=None, db=None)
    assert unauthorized.value.status_code == 401
    assert any(
        dependency.call is get_current_user
        for route in support_ticket_router.routes
        if route.path == "/support-tickets" and "POST" in route.methods
        for dependency in route.dependant.dependencies
    )


def test_unanswered_queries_are_redacted_and_aggregated(assistant_db):
    db = assistant_db[0]
    match = {"intent": None, "confidence": 0.22}
    record_unanswered(db, "Need help for person@example.test, password: abc123", "en", match)
    record_unanswered(db, "Need help for person@example.test, password: abc123", "en", match)
    db.commit()
    rows = db.query(AssistantUnansweredQuestion).all()
    assert len(rows) == 1
    assert rows[0].frequency == 2
    assert "person@example.test" not in rows[0].normalized_query
    assert "abc123" not in rows[0].normalized_query


def test_admin_approved_knowledge_is_reviewed_before_assistant_use(assistant_db):
    db, _candidate, _other, _recruiter, _admin, *_ = assistant_db
    db.add(AssistantKnowledgeSuggestion(intent_id="company_info", language="en", question="how do verified company records work", response="Company facts come from published SkillSphere records.", status="PENDING"))
    db.commit()
    before = answer_assistant(db, "how do verified company records work", "candidate")
    assert "verified information" in before["reply"].lower()
    row = db.query(AssistantKnowledgeSuggestion).one()
    row.status = "APPROVED"
    db.commit()
    after = answer_assistant(db, "how do verified company records work", "candidate")
    assert after["reply"] == "Company facts come from published SkillSphere records."


def test_rule_engine_never_calls_provider(monkeypatch):
    from app.services.ai_service import AIService

    monkeypatch.setattr(AIService, "_request_text", staticmethod(lambda *a, **k: pytest.fail("Assistant must never call an external model")))
    result = answer_assistant(None, "How do I create a resume PDF?", "candidate")
    assert result["reply"]
    assert result["actions"][0]["path"] == "/candidate/resume-builder"


@pytest.mark.parametrize("message,language", [
    ("मेरा रिज्यूमे कैसे अपलोड करूँ?", "hi"),
    ("yr mera resume upload ni hora", "hinglish"),
    ("ਮੈਂ ਆਪਣਾ ਰੈਜ਼ਿਊਮੇ ਕਿਵੇਂ ਅੱਪਲੋਡ ਕਰਾਂ?", "pa"),
    ("mai apna resume kive upload kara", "pa_latn"),
])
def test_script_language_detection(message, language):
    assert detect_language(message) == language
    assert match_intent(message)["intent"] == "resume_upload"
