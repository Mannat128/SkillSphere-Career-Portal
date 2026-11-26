"""Isolated authorization and ownership checks for the Recruiter-only bank."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException, UnauthorizedException
from app.database.base import Base
from app.models.recruiter import Company, Recruiter
from app.models.recruiter_assessment import QuestionBankQuestion
from app.models.user import User, UserRole
from app.routers import question_bank
from app.routers.question_bank import (
    AIGenerateRequest,
    AIGeneratedQuestionSaveRequest,
    add_question_manually,
    delete_question,
    generate_ai_questions,
    get_categories,
    get_question,
    get_question_bank,
    router,
    save_reviewed_ai_questions,
    update_question,
)
from app.schemas.recruiter_assessment import QuestionCreate, QuestionUpdate
from app.services.ai_service import AIService


def _question(text, *, recruiter_id=None, creator_id=None, shared=False):
    return QuestionBankQuestion(
        recruiter_id=recruiter_id,
        created_by_id=creator_id,
        is_shared=shared,
        question_text=text,
        category="Python",
        difficulty="Medium",
        option_a="Option A",
        option_b="Option B",
        option_c="Option C",
        option_d="Option D",
        correct_answer="B",
        marks=1,
    )


@pytest.fixture
def isolated_question_bank():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    assert engine.dialect.name == "sqlite"
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    recruiter_user = User(
        id=3101, email="recruiter-qb@example.test", full_name="Synthetic Recruiter",
        hashed_password="unused", role=UserRole.RECRUITER, is_active=True,
    )
    other_recruiter_user = User(
        id=3102, email="other-recruiter-qb@example.test", full_name="Other Recruiter",
        hashed_password="unused", role=UserRole.RECRUITER, is_active=True,
    )
    admin = User(
        id=3103, email="admin-qb@example.test", full_name="Synthetic Admin",
        hashed_password="unused", role=UserRole.ADMIN, is_active=True,
    )
    candidate = User(
        id=3104, email="candidate-qb@example.test", full_name="Synthetic Candidate",
        hashed_password="unused", role=UserRole.CANDIDATE, is_active=True,
    )
    db.add_all([recruiter_user, other_recruiter_user, admin, candidate])
    db.flush()
    company = Company(name="Synthetic Question Bank Company")
    other_company = Company(name="Other Synthetic Question Bank Company")
    db.add_all([company, other_company])
    db.flush()
    recruiter = Recruiter(user_id=recruiter_user.id, company_id=company.id)
    other_recruiter = Recruiter(user_id=other_recruiter_user.id, company_id=other_company.id)
    db.add_all([recruiter, other_recruiter])
    db.flush()
    shared_question = _question(
        "Which Python value is a boolean?", creator_id=admin.id, shared=True,
    )
    own_question = _question(
        "How does this recruiter own a private question?",
        recruiter_id=recruiter.id, creator_id=recruiter_user.id,
    )
    foreign_question = _question(
        "How does another recruiter own a private question?",
        recruiter_id=other_recruiter.id, creator_id=other_recruiter_user.id,
    )
    db.add_all([shared_question, own_question, foreign_question])
    db.commit()
    for row in (shared_question, own_question, foreign_question):
        db.refresh(row)
    actors = {
        "recruiter": recruiter_user,
        "recruiter_profile": recruiter,
        "other_recruiter": other_recruiter_user,
        "admin": admin,
        "candidate": candidate,
        "shared_question": shared_question,
        "own_question": own_question,
        "foreign_question": foreign_question,
    }
    try:
        yield db, actors
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_every_question_bank_api_route_has_recruiter_guard():
    recruiter_guard = router.dependencies[0].dependency
    assert len(router.routes) >= 10
    for route in router.routes:
        assert any(item.call is recruiter_guard for item in route.dependant.dependencies), route.path


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.CANDIDATE])
def test_admin_and_candidate_are_forbidden_at_question_bank_route_guard(role):
    recruiter_guard = router.dependencies[0].dependency
    user = User(email=f"{role.value.lower()}-qb@example.test", full_name="Synthetic", role=role)
    with pytest.raises(ForbiddenException) as exc:
        recruiter_guard(current_user=user)
    assert exc.value.status_code == 403


def test_unauthenticated_question_bank_request_is_rejected(isolated_question_bank):
    db, _actors = isolated_question_bank
    with pytest.raises(UnauthorizedException) as exc:
        get_current_user(token=None, db=db)
    assert exc.value.status_code == 401


def test_recruiter_reads_shared_and_own_questions_only(isolated_question_bank):
    db, actors = isolated_question_bank
    rows = get_question_bank(
        category=None, difficulty=None, search=None, source="all", job_id=None,
        include_job_specific=True, current_user=actors["recruiter"], db=db,
    )
    ids = {row.id for row in rows}
    assert actors["shared_question"].id in ids
    assert actors["own_question"].id in ids
    assert actors["foreign_question"].id not in ids
    assert get_categories(actors["recruiter"], db) == ["Python"]


def test_recruiter_can_generate_and_save_questions_without_external_request(isolated_question_bank, monkeypatch):
    db, actors = isolated_question_bank
    generated = {
        "question_text": "What does a Python generator produce lazily?",
        "category": "Python",
        "difficulty": "Medium",
        "option_a": "A value",
        "option_b": "An iterator",
        "option_c": "A class",
        "option_d": "A module",
        "correct_answer": "B",
        "marks": 1,
        "explanation": "Generators yield values over time.",
    }
    monkeypatch.setattr(AIService, "generate_mcq_questions", lambda **_kwargs: [generated])
    preview = generate_ai_questions(
        AIGenerateRequest(topic="Python", count=1), actors["recruiter"], db,
    )
    assert preview["generated_count"] == 1
    assert preview["saved"] is False

    request = AIGeneratedQuestionSaveRequest(
        questions=[QuestionCreate(**generated)], save_to_bank=True,
    )
    saved = save_reviewed_ai_questions(request, actors["recruiter"], db)
    assert len(saved) == 1
    assert saved[0].recruiter_id == actors["recruiter_profile"].id
    assert saved[0].is_shared is False


def test_recruiter_can_manually_save_private_question(isolated_question_bank):
    db, actors = isolated_question_bank
    request = QuestionCreate(
        question_text="Which test verifies a private Recruiter question?",
        category="Testing", difficulty="Easy", option_a="A", option_b="B",
        option_c="C", option_d="D", correct_answer="A", save_to_bank=True,
    )
    saved = add_question_manually(request, actors["recruiter"], db)
    assert saved.recruiter_id == actors["recruiter_profile"].id
    assert saved.is_shared is False


def test_admin_and_candidate_cannot_call_question_bank_handlers_directly(isolated_question_bank):
    db, actors = isolated_question_bank
    for actor in (actors["admin"], actors["candidate"]):
        with pytest.raises(ForbiddenException):
            get_question_bank(None, None, None, "all", None, False, actor, db)
        with pytest.raises(ForbiddenException):
            get_categories(actor, db)
        with pytest.raises(ForbiddenException):
            generate_ai_questions(AIGenerateRequest(topic="Python"), actor, db)
        with pytest.raises(ForbiddenException):
            add_question_manually(
                QuestionCreate(**{
                    "question_text": "Which route must deny this request?",
                    "category": "Testing", "option_a": "A", "option_b": "B",
                    "option_c": "C", "option_d": "D", "correct_answer": "A",
                }), actor, db,
            )
        with pytest.raises(ForbiddenException):
            save_reviewed_ai_questions(
                AIGeneratedQuestionSaveRequest(
                    questions=[QuestionCreate(
                        question_text="Which API operation is restricted?",
                        category="Testing", option_a="A", option_b="B",
                        option_c="C", option_d="D", correct_answer="A",
                    )],
                ),
                actor,
                db,
            )
        with pytest.raises(ForbiddenException):
            get_question(actors["shared_question"].id, actor, db)
        with pytest.raises(ForbiddenException):
            update_question(actors["own_question"].id, QuestionUpdate(category="Changed"), actor, db)
        with pytest.raises(ForbiddenException):
            delete_question(actors["own_question"].id, actor, db)


def test_recruiter_cannot_read_edit_or_delete_another_recruiters_question(isolated_question_bank):
    db, actors = isolated_question_bank
    foreign_id = actors["foreign_question"].id
    with pytest.raises(NotFoundException):
        get_question(foreign_id, actors["recruiter"], db)
    with pytest.raises(NotFoundException):
        update_question(foreign_id, QuestionUpdate(category="Changed"), actors["recruiter"], db)
    with pytest.raises(NotFoundException):
        delete_question(foreign_id, actors["recruiter"], db)
