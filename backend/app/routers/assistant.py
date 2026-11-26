"""API for the deterministic SkillSphere Company & Platform Assistant."""

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import threading
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Header, Query
from jose import jwt, JWTError
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_admin, get_current_user, get_db, get_optional_current_user
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.audit import AuditLog
from app.models.sphera import (
    AssistantFeedback,
    AssistantKnowledgeSuggestion,
    AssistantUnansweredQuestion,
    SpheraConversation,
    SpheraMessage,
)
from app.models.user import User, UserRole
from app.services.assistant_engine import LANGUAGES, answer_assistant, redact_sensitive_data, role_name
from app.services.assistant_company_catalog import catalog_options


router = APIRouter(prefix="/assistant", tags=["SkillSphere Assistant"])
FEEDBACK_CATEGORIES = {"incorrect", "incomplete", "not_understood", "technical", "language", "other"}
ISSUE_STATUSES = {"OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"}
PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
_rate_lock = threading.Lock()
_rate_events: dict[str, list[datetime]] = {}
_MAX_PER_MINUTE = 30


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[int] = Field(default=None, gt=0)
    language: str = Field(default="auto", max_length=16)
    context_path: Optional[str] = Field(default=None, max_length=160)


class FeedbackRequest(BaseModel):
    message_id: int = Field(gt=0)
    rating: Literal["helpful", "not_helpful"]
    category: Optional[str] = Field(default=None, max_length=40)
    comment: Optional[str] = Field(default=None, max_length=1000)


class AdminFeedbackUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    admin_notes: Optional[str] = Field(default=None, max_length=2000)
    assigned_admin_id: Optional[int] = Field(default=None, gt=0)


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class KnowledgeReview(BaseModel):
    status: Literal["APPROVED", "REJECTED"]


class KnowledgeSuggestionCreate(BaseModel):
    unanswered_id: Optional[int] = Field(default=None, gt=0)
    intent_id: str = Field(min_length=2, max_length=80)
    language: str = Field(default="en", max_length=16)
    question: str = Field(min_length=3, max_length=500)
    response: str = Field(min_length=3, max_length=2000)
    route: Optional[str] = Field(default=None, max_length=160)


def _guest_claims(token: Optional[str]):
    if not token:
        raise ForbiddenException("A valid assistant guest session is required.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "assistant_guest" or not payload.get("sid"):
            raise ValueError("invalid guest token")
    except (JWTError, ValueError, TypeError):
        raise ForbiddenException("The assistant guest session is invalid or expired.")
    return payload


def _guest_hash(token: Optional[str]) -> str:
    _guest_claims(token)
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _owner_filter(query, user: Optional[User], guest_hash: Optional[str]):
    if user:
        return query.filter(SpheraConversation.user_id == user.id)
    return query.filter(
        SpheraConversation.user_id.is_(None),
        SpheraConversation.guest_session_hash == guest_hash,
    )


def _owned_conversation(db: Session, conversation_id: int, user: Optional[User], guest_hash: Optional[str]):
    query = db.query(SpheraConversation).filter(SpheraConversation.id == conversation_id)
    conversation = _owner_filter(query, user, guest_hash).first()
    if not conversation:
        raise NotFoundException("Conversation")
    return conversation


def _enforce_rate_limit(actor: str):
    now = datetime.now(timezone.utc)
    with _rate_lock:
        events = [item for item in _rate_events.get(actor, []) if now - item < timedelta(minutes=1)]
        if len(events) >= _MAX_PER_MINUTE:
            raise BadRequestException("Assistant request limit reached. Please wait a minute and try again.")
        events.append(now)
        _rate_events[actor] = events


def _conversation_dict(row: SpheraConversation):
    return {
        "id": row.id,
        "title": row.title,
        "updated_at": row.updated_at.isoformat(),
        "created_at": row.created_at.isoformat(),
        "language": row.selected_language,
    }


@router.post("/guest-session")
def create_guest_session():
    sid = secrets.token_urlsafe(32)
    token = jwt.encode({
        "sid": sid,
        "type": "assistant_guest",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"session_token": token, "expires_in": 43200}


@router.delete("/guest-session")
def clear_guest_session(
    x_assistant_session: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    guest_hash = _guest_hash(x_assistant_session)
    rows = db.query(SpheraConversation).filter(
        SpheraConversation.user_id.is_(None),
        SpheraConversation.guest_session_hash == guest_hash,
    ).all()
    for row in rows:
        db.delete(row)
    db.commit()
    return {"cleared": True, "deleted_conversation_count": len(rows)}


@router.get("/options")
def assistant_options(current_user: Optional[User] = Depends(get_optional_current_user), db: Session = Depends(get_db)):
    role = role_name(current_user)
    actions = {
        "candidate": ["Find Jobs", "My Applications", "Resume Builder", "Assessment Rules", "My Profile", "Contact Support"],
        "recruiter": ["My Jobs", "Manage Applicants", "Question Bank", "Assessment Results", "Interview Scheduler", "Company Profile"],
        "visitor": ["About SkillSphere", "Explore Features", "Browse Jobs", "Create Account", "Contact Us"],
        "admin": ["Admin Dashboard", "Chatbot Feedback", "Support Center"],
    }
    return {"role": role, "languages": [
        {"id": "auto", "label": "Auto detect"}, {"id": "en", "label": "English"},
        {"id": "hi", "label": "हिन्दी"}, {"id": "hinglish", "label": "Hinglish"},
        {"id": "pa", "label": "ਪੰਜਾਬੀ"}, {"id": "pa_latn", "label": "Roman Punjabi"},
    ], "quick_actions": actions[role], "catalog": catalog_options(db)}


@router.post("/chat")
def assistant_chat(
    request: ChatRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
    x_assistant_session: Optional[str] = Header(default=None),
):
    text = request.message.strip()
    if len(text) < 2:
        raise BadRequestException("Please enter a message with at least two characters.")
    if request.language not in LANGUAGES:
        raise BadRequestException("Choose a supported assistant language.")
    guest_hash = None if current_user else _guest_hash(x_assistant_session)
    actor = f"user:{current_user.id}" if current_user else f"guest:{guest_hash}"
    _enforce_rate_limit(actor)

    conversation = None
    history = []
    if request.conversation_id:
        conversation = _owned_conversation(db, request.conversation_id, current_user, guest_hash)
        previous = db.query(SpheraMessage).filter_by(conversation_id=conversation.id).order_by(
            SpheraMessage.created_at.desc(), SpheraMessage.id.desc()
        ).limit(12).all()
        history = [{"role": row.role, "text": row.text} for row in reversed(previous)]

    answer = answer_assistant(
        db=db,
        message=text,
        role=role_name(current_user),
        context_path=request.context_path or "",
        history=history,
        selected_language=request.language,
        user=current_user,
    )
    stored_user_text = redact_sensitive_data(text)
    now = datetime.utcnow()
    if conversation is None:
        conversation = SpheraConversation(
            user_id=current_user.id if current_user else None,
            guest_session_hash=guest_hash,
            title=" ".join(stored_user_text.split())[:117],
            mode="assistant",
            selected_language=request.language,
            created_at=now,
            updated_at=now,
        )
        db.add(conversation)
        db.flush()
    else:
        conversation.selected_language = request.language
    conversation.last_intent = answer["intent"]
    conversation.last_confidence = answer["confidence"]
    user_message = SpheraMessage(
        conversation_id=conversation.id, role="user", text=stored_user_text,
        intent=answer["intent"], confidence=answer["confidence"],
        language=answer["language"], created_at=now,
    )
    assistant_message = SpheraMessage(
        conversation_id=conversation.id, role="assistant", text=answer["reply"],
        intent=answer["intent"], confidence=answer["confidence"],
        language=answer["language"], created_at=now,
    )
    db.add_all([user_message, assistant_message])
    db.commit()
    db.refresh(assistant_message)
    return {
        "assistant": "SkillSphere Assistant",
        "reply": answer["reply"],
        "intent": answer["intent"],
        "confidence": answer["confidence"],
        "language": answer["language"],
        "actions": answer["actions"],
        "suggestions": answer["suggestions"],
        "ticket_suggestion": answer["ticket_suggestion"],
        "conversation_id": conversation.id,
        "message_id": assistant_message.id,
        "created_at": assistant_message.created_at.isoformat(),
    }


@router.get("/conversations")
def list_conversations(
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
    x_assistant_session: Optional[str] = Header(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    guest_hash = None if current_user else _guest_hash(x_assistant_session)
    query = db.query(SpheraConversation)
    rows = _owner_filter(query, current_user, guest_hash).order_by(
        SpheraConversation.updated_at.desc()
    ).limit(limit).all()
    return [_conversation_dict(row) for row in rows]


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
    x_assistant_session: Optional[str] = Header(default=None),
):
    guest_hash = None if current_user else _guest_hash(x_assistant_session)
    row = _owned_conversation(db, conversation_id, current_user, guest_hash)
    messages = db.query(SpheraMessage).filter_by(conversation_id=row.id).order_by(SpheraMessage.created_at, SpheraMessage.id).all()
    return {**_conversation_dict(row), "messages": [{
        "id": item.id, "role": item.role, "text": item.text,
        "created_at": item.created_at.isoformat(), "intent": item.intent,
        "confidence": item.confidence, "language": item.language,
    } for item in messages]}


@router.patch("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: int,
    request: RenameRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
    x_assistant_session: Optional[str] = Header(default=None),
):
    title = request.title.strip()
    guest_hash = None if current_user else _guest_hash(x_assistant_session)
    row = _owned_conversation(db, conversation_id, current_user, guest_hash)
    row.title = title
    row.updated_at = datetime.utcnow()
    db.commit()
    return _conversation_dict(row)


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
    x_assistant_session: Optional[str] = Header(default=None),
):
    guest_hash = None if current_user else _guest_hash(x_assistant_session)
    row = _owned_conversation(db, conversation_id, current_user, guest_hash)
    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.post("/feedback")
def submit_feedback(
    request: FeedbackRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
    x_assistant_session: Optional[str] = Header(default=None),
):
    guest_hash = None if current_user else _guest_hash(x_assistant_session)
    message = db.query(SpheraMessage).filter_by(id=request.message_id, role="assistant").first()
    if not message:
        raise NotFoundException("Assistant message")
    conversation = _owned_conversation(db, message.conversation_id, current_user, guest_hash)
    if request.rating == "not_helpful" and request.category not in FEEDBACK_CATEGORIES:
        raise BadRequestException("Choose a feedback category for an unhelpful response.")
    existing_query = db.query(AssistantFeedback).filter(AssistantFeedback.message_id == message.id)
    existing_query = existing_query.filter(AssistantFeedback.user_id == current_user.id) if current_user else existing_query.filter(
        AssistantFeedback.user_id.is_(None), AssistantFeedback.guest_session_hash == guest_hash
    )
    if existing_query.first():
        raise BadRequestException("Feedback has already been submitted for this answer.")
    row = AssistantFeedback(
        message_id=message.id, conversation_id=conversation.id,
        user_id=current_user.id if current_user else None,
        guest_session_hash=guest_hash, user_role=role_name(current_user),
        rating=request.rating, category=request.category,
        comment=redact_sensitive_data(request.comment.strip()) if request.comment else None,
        language=message.language or "en", matched_intent=message.intent,
        match_score=message.confidence or 0.0,
        status="OPEN" if request.rating == "not_helpful" else "CLOSED",
        priority="MEDIUM" if request.rating == "not_helpful" else "LOW",
        created_at=datetime.utcnow(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate_query = db.query(AssistantFeedback).filter(
            AssistantFeedback.message_id == message.id
        )
        if current_user:
            duplicate_query = duplicate_query.filter(AssistantFeedback.user_id == current_user.id)
        else:
            duplicate_query = duplicate_query.filter(
                AssistantFeedback.user_id.is_(None),
                AssistantFeedback.guest_session_hash == guest_hash,
            )
        if duplicate_query.first():
            raise BadRequestException("Feedback has already been submitted for this answer.")
        raise
    return {"submitted": True, "feedback_id": row.id}


@router.get("/admin/analytics")
def admin_analytics(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    total = db.query(func.count(AssistantFeedback.id)).scalar() or 0
    helpful = db.query(func.count(AssistantFeedback.id)).filter(AssistantFeedback.rating == "helpful").scalar() or 0
    counts = {
        status: db.query(func.count(AssistantFeedback.id)).filter(AssistantFeedback.status == status).scalar() or 0
        for status in ISSUE_STATUSES
    }
    unanswered = db.query(func.count(AssistantUnansweredQuestion.id)).scalar() or 0
    return {
        "total_feedback": total,
        "helpful_count": helpful,
        "negative_count": total - helpful,
        "helpful_percentage": round(helpful * 100 / total, 1) if total else 0,
        "statuses": counts,
        "unanswered_questions": unanswered,
        "by_role": [{"role": role, "count": count} for role, count in db.query(AssistantFeedback.user_role, func.count(AssistantFeedback.id)).group_by(AssistantFeedback.user_role).all()],
        "by_language": [{"language": language, "count": count} for language, count in db.query(AssistantFeedback.language, func.count(AssistantFeedback.id)).group_by(AssistantFeedback.language).all()],
        "by_category": [{"category": category, "count": count} for category, count in db.query(AssistantFeedback.category, func.count(AssistantFeedback.id)).filter(AssistantFeedback.category.is_not(None)).group_by(AssistantFeedback.category).all()],
        "by_intent": [{"intent": intent, "count": count} for intent, count in db.query(AssistantFeedback.matched_intent, func.count(AssistantFeedback.id)).filter(AssistantFeedback.matched_intent.is_not(None)).group_by(AssistantFeedback.matched_intent).order_by(func.count(AssistantFeedback.id).desc()).all()],
    }


@router.get("/admin/feedback")
def admin_feedback(
    role: Optional[str] = None,
    language: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = Query(default=None, max_length=120),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AssistantFeedback)
    if role: query = query.filter(AssistantFeedback.user_role == role.lower())
    if language: query = query.filter(AssistantFeedback.language == language)
    if category: query = query.filter(AssistantFeedback.category == category)
    if priority: query = query.filter(AssistantFeedback.priority == priority.upper())
    if status: query = query.filter(AssistantFeedback.status == status.upper())
    if search: query = query.filter(AssistantFeedback.comment.ilike(f"%{search.strip()}%"))
    rows = query.order_by(AssistantFeedback.created_at.desc()).limit(200).all()
    return [{
        "id": row.id, "message_id": row.message_id, "conversation_id": row.conversation_id,
        "user_role": row.user_role, "rating": row.rating, "category": row.category,
        "comment": row.comment, "language": row.language,
        "matched_intent": row.matched_intent, "match_score": row.match_score,
        "status": row.status, "priority": row.priority, "admin_notes": row.admin_notes,
        "assigned_admin_id": row.assigned_admin_id, "created_at": row.created_at.isoformat(),
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    } for row in rows]


def _safe_feedback_history_changes(details) -> dict:
    """Return only approved moderation fields, never transcripts or raw messages."""
    details = details if isinstance(details, dict) else {}
    changes = details.get("changes")
    if not isinstance(changes, dict):
        # Compatibility with audit entries written before field-level history.
        previous = details.get("previous") if isinstance(details.get("previous"), dict) else {}
        changes = {}
        for key in ("status", "priority"):
            before, after = previous.get(key), details.get(key)
            if before != after and (before is not None or after is not None):
                changes[key] = {"from": before, "to": after}

    safe = {}
    for key in ("status", "priority", "assigned_admin_id"):
        value = changes.get(key)
        if isinstance(value, dict) and set(value).issubset({"from", "to"}):
            safe[key] = {"from": value.get("from"), "to": value.get("to")}
    notes = changes.get("admin_notes")
    if isinstance(notes, dict) and set(notes).issubset({"from", "to"}):
        safe["admin_notes"] = {
            "from": redact_sensitive_data(str(notes.get("from") or ""))[:2000],
            "to": redact_sensitive_data(str(notes.get("to") or ""))[:2000],
        }
    return safe


@router.get("/admin/feedback/{feedback_id}/history")
def admin_feedback_history(
    feedback_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    feedback = db.query(AssistantFeedback.id).filter_by(id=feedback_id).first()
    if not feedback:
        raise NotFoundException("Assistant feedback")
    logs = (
        db.query(AuditLog)
        .filter_by(action="ASSISTANT_FEEDBACK_UPDATED", entity_type="assistant_feedback", entity_id=feedback_id)
        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        .limit(200)
        .all()
    )
    return [{
        "id": log.id,
        "admin_id": log.user_id,
        "action": log.action,
        "changes": _safe_feedback_history_changes(log.details),
        "created_at": log.created_at.isoformat(),
    } for log in logs]


@router.patch("/admin/feedback/{feedback_id}")
def update_feedback(
    feedback_id: int,
    request: AdminFeedbackUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = db.query(AssistantFeedback).filter_by(id=feedback_id).first()
    if not row: raise NotFoundException("Assistant feedback")
    if request.status and request.status.upper() not in ISSUE_STATUSES: raise BadRequestException("Invalid issue status.")
    if request.priority and request.priority.upper() not in PRIORITIES: raise BadRequestException("Invalid feedback priority.")
    changes = {}
    now = datetime.utcnow()
    if request.status:
        new_status = request.status.upper()
        if new_status != row.status:
            changes["status"] = {"from": row.status, "to": new_status}
            row.status = new_status
            row.resolved_at = now if new_status in {"RESOLVED", "CLOSED"} else None
    if request.priority:
        new_priority = request.priority.upper()
        if new_priority != row.priority:
            changes["priority"] = {"from": row.priority, "to": new_priority}
            row.priority = new_priority
    if request.admin_notes is not None:
        new_notes = redact_sensitive_data(request.admin_notes.strip())
        if new_notes != (row.admin_notes or ""):
            changes["admin_notes"] = {
                "from": redact_sensitive_data(row.admin_notes or ""),
                "to": new_notes,
            }
            row.admin_notes = new_notes
    if request.assigned_admin_id is not None:
        assignee = db.query(User).filter_by(id=request.assigned_admin_id, role=UserRole.ADMIN, is_active=True).first()
        if not assignee: raise BadRequestException("The assigned administrator is not active.")
        if assignee.id != row.assigned_admin_id:
            changes["assigned_admin_id"] = {"from": row.assigned_admin_id, "to": assignee.id}
            row.assigned_admin_id = assignee.id
    if changes:
        db.add(AuditLog(
            user_id=admin.id,
            action="ASSISTANT_FEEDBACK_UPDATED",
            entity_type="assistant_feedback",
            entity_id=row.id,
            details={"changes": changes},
            created_at=now,
        ))
        db.commit()
    return {"updated": True, "id": row.id, "status": row.status, "priority": row.priority}


@router.get("/admin/unanswered")
def admin_unanswered(
    language: Optional[str] = None,
    min_frequency: int = Query(default=1, ge=1),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AssistantUnansweredQuestion).filter(AssistantUnansweredQuestion.frequency >= min_frequency)
    if language: query = query.filter(AssistantUnansweredQuestion.language == language)
    return [{
        "id": row.id, "question": row.normalized_query, "language": row.language,
        "best_intent": row.best_intent, "match_score": row.match_score,
        "frequency": row.frequency, "review_status": row.review_status,
        "last_seen_at": row.last_seen_at.isoformat(),
    } for row in query.order_by(AssistantUnansweredQuestion.frequency.desc()).limit(200).all()]


@router.get("/admin/knowledge-suggestions")
def admin_knowledge_suggestions(
    status: Optional[str] = "PENDING",
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AssistantKnowledgeSuggestion)
    if status:
        query = query.filter(AssistantKnowledgeSuggestion.status == status.upper())
    return [{
        "id": row.id, "unanswered_id": row.unanswered_id, "intent_id": row.intent_id,
        "language": row.language, "question": row.question, "response": row.response,
        "route": row.route, "status": row.status, "created_at": row.created_at.isoformat(),
    } for row in query.order_by(AssistantKnowledgeSuggestion.created_at.desc()).limit(200).all()]


@router.post("/admin/knowledge-suggestions")
def create_knowledge_suggestion(
    request: KnowledgeSuggestionCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if request.language not in LANGUAGES - {"auto"}:
        raise BadRequestException("Choose a supported knowledge-entry language.")
    if request.route and not request.route.startswith("/"):
        raise BadRequestException("Knowledge route must be an internal application path.")
    row = AssistantKnowledgeSuggestion(
        unanswered_id=request.unanswered_id, intent_id=request.intent_id.strip(),
        language=request.language, question=request.question.strip(),
        response=request.response.strip(), route=request.route,
        status="PENDING", created_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    db.add(AuditLog(user_id=admin.id, action="ASSISTANT_KNOWLEDGE_PROPOSED", entity_type="assistant_knowledge_suggestion", entity_id=row.id, details={"status": "PENDING"}))
    db.commit()
    return {"id": row.id, "status": row.status}


@router.post("/admin/knowledge-suggestions/{suggestion_id}/review")
def review_knowledge_suggestion(
    suggestion_id: int,
    request: KnowledgeReview,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = db.query(AssistantKnowledgeSuggestion).filter_by(id=suggestion_id).first()
    if not row: raise NotFoundException("Knowledge suggestion")
    row.status = request.status
    row.reviewed_by_id = admin.id
    row.reviewed_at = datetime.utcnow()
    db.add(AuditLog(user_id=admin.id, action="ASSISTANT_KNOWLEDGE_REVIEWED", entity_type="assistant_knowledge_suggestion", entity_id=row.id, details={"status": row.status}))
    db.commit()
    return {"reviewed": True, "status": row.status}
