from typing import List, Optional
import datetime
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.dependencies import (
    get_current_user,
    get_current_candidate,
    get_current_recruiter,
    require_role,
)
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)
from app.models.user import User, UserRole
from app.models.candidate import Candidate
from app.models.recruiter import Recruiter
from app.models.job import Job
from app.models.application import Application, ApplicationStatusEnum
from app.models.interview import (
    Interview,
    InterviewStatusEnum,
    InterviewSession,
    InterviewQuestion,
    InterviewAnswer,
)
from app.models.notification import Notification
from app.schemas.interview import (
    InterviewCreate,
    InterviewUpdate,
    InterviewResponse,
    MockInterviewStartRequest,
    MockInterviewSessionResponse,
    MockInterviewAnswerSubmit,
    MockInterviewFeedbackResponse,
)
from app.services.ai_service import AIService

router = APIRouter(prefix="/interviews", tags=["Interviews & Mock Practice"])

# Curated Practice Questions by Technology
CURATED_PRACTICE_QUESTIONS = {
    "python": [
        "Explain the difference between mutable and immutable data types in Python. How does this affect memory and function arguments?",
        "How do Python decorators work under the hood? Write a practical use case.",
        "What are Python generators and iterators? How does `yield` improve memory efficiency with large datasets?",
        "Explain the Global Interpreter Lock (GIL) and how it affects multi-threaded Python programs.",
        "How does Python's Garbage Collection work with reference counting and cyclic references?"
    ],
    "react": [
        "Explain the Virtual DOM and React's reconciliation process (Fiber architecture).",
        "What are the differences between `useEffect`, `useLayoutEffect`, and `useMemo`?",
        "How would you optimize an expensive React component that re-renders frequently?",
        "What is the difference between controlled and uncontrolled components in React forms?",
        "How does React 18 automatic batching and Concurrent Mode improve UI responsiveness?"
    ],
    "sql": [
        "What is database indexing and how do B-Tree and Hash indexes differ?",
        "Explain ACID transactions and provide a scenario where isolation level matters.",
        "What is the difference between INNER, LEFT, RIGHT, and FULL OUTER joins?",
        "How would you diagnose and optimize a slow-running SQL query?",
        "Explain database normalization from 1NF to 3NF."
    ],
    "fastapi": [
        "How does FastAPI utilize Python type hints and Pydantic for validation and serialization?",
        "Explain FastAPI's Dependency Injection system and how `Depends()` works.",
        "What is the difference between synchronous (`def`) and asynchronous (`async def`) path operations in FastAPI?",
        "How does FastAPI handle background tasks and error exceptions?",
        "How do you implement JWT authentication middleware in FastAPI?"
    ],
    "javascript": [
        "Explain JavaScript Event Loop, call stack, microtask queue, and macrotask queue.",
        "What is lexical scope and how do closures work in modern JavaScript?",
        "Explain prototypal inheritance and how it compares to ES6 classes.",
        "What are Promises and how does `async/await` syntax sugar work?",
        "What are the differences between `var`, `let`, and `const` regarding hoisting and scope?"
    ]
}

# --- Recruiter Scheduled Interviews ---

@router.get("", response_model=List[InterviewResponse])
def list_interviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List interviews for candidate or recruiter.
    """
    if current_user.role == UserRole.CANDIDATE:
        candidate = db.query(Candidate).filter(Candidate.user_id == current_user.id).first()
        if not candidate:
            return []
        interviews = db.query(Interview).filter(Interview.candidate_id == candidate.id).order_by(Interview.interview_date.asc()).all()
    elif current_user.role == UserRole.RECRUITER:
        recruiter = db.query(Recruiter).filter(Recruiter.user_id == current_user.id).first()
        if not recruiter:
            return []
        interviews = db.query(Interview).filter(Interview.recruiter_id == recruiter.id).order_by(Interview.interview_date.asc()).all()
    else: # Admin
        interviews = db.query(Interview).order_by(Interview.interview_date.asc()).all()

    results = []
    for it in interviews:
        cand_user = it.candidate.user if it.candidate else None
        results.append({
            "id": it.id,
            "application_id": it.application_id,
            "recruiter_id": it.recruiter_id,
            "candidate_id": it.candidate_id,
            "job_id": it.job_id,
            "job_title": it.job.title if it.job else "Position",
            "company_name": it.job.company.name if (it.job and it.job.company) else "Company",
            "candidate_name": cand_user.full_name if cand_user else "Candidate",
            "candidate_email": cand_user.email if cand_user else "",
            "interview_date": it.interview_date,
            "interview_type": it.interview_type,
            "meeting_link": it.meeting_link,
            "instructions": it.instructions,
            "status": it.status,
            "notes": it.notes,
            "created_at": it.created_at
        })
    return results

@router.post("", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
def schedule_interview(
    req: InterviewCreate,
    recruiter: Recruiter = Depends(get_current_recruiter),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Recruiter schedules an interview with a candidate for their job application.
    Updates application status to INTERVIEW and sends notification.
    """
    app_record = db.query(Application).filter(Application.id == req.application_id).first()
    if not app_record:
        raise NotFoundException("Application")

    # Verify that this application belongs to recruiter's job
    if app_record.job.recruiter_id != recruiter.id and current_user.role != UserRole.ADMIN:
        raise ForbiddenException("You cannot schedule interviews for other recruiters' jobs.")

    interview = Interview(
        application_id=app_record.id,
        recruiter_id=recruiter.id,
        candidate_id=app_record.candidate_id,
        job_id=app_record.job_id,
        interview_date=req.interview_date,
        interview_type=req.interview_type,
        meeting_link=req.meeting_link,
        instructions=req.instructions,
        notes=req.notes,
        status=InterviewStatusEnum.SCHEDULED
    )
    db.add(interview)

    # Update application status to INTERVIEW
    app_record.current_status = ApplicationStatusEnum.INTERVIEW

    # Candidate notification
    cand_user = app_record.candidate.user
    if cand_user:
        notif = Notification(
            user_id=cand_user.id,
            title="Interview Scheduled!",
            message=f"An interview for '{app_record.job.title}' has been scheduled on {req.interview_date.strftime('%B %d, %Y at %I:%M %p')}.",
            type="INTERVIEW",
            link="/candidate/interviews"
        )
        db.add(notif)

    db.commit()
    db.refresh(interview)

    return {
        "id": interview.id,
        "application_id": interview.application_id,
        "recruiter_id": interview.recruiter_id,
        "candidate_id": interview.candidate_id,
        "job_id": interview.job_id,
        "job_title": app_record.job.title,
        "company_name": app_record.job.company.name if app_record.job.company else "",
        "candidate_name": cand_user.full_name if cand_user else "",
        "candidate_email": cand_user.email if cand_user else "",
        "interview_date": interview.interview_date,
        "interview_type": interview.interview_type,
        "meeting_link": interview.meeting_link,
        "instructions": interview.instructions,
        "status": interview.status,
        "notes": interview.notes,
        "created_at": interview.created_at
    }

@router.put("/{interview_id}", response_model=InterviewResponse)
def update_interview(
    interview_id: int,
    req: InterviewUpdate,
    recruiter: Recruiter = Depends(get_current_recruiter),
    db: Session = Depends(get_db)
):
    """Reschedule or update interview status."""
    it = db.query(Interview).filter(Interview.id == interview_id).first()
    if not it:
        raise NotFoundException("Interview")

    if it.recruiter_id != recruiter.id:
        raise ForbiddenException()

    if req.interview_date:
        it.interview_date = req.interview_date
        it.status = InterviewStatusEnum.RESCHEDULED
    if req.interview_type:
        it.interview_type = req.interview_type
    if req.meeting_link:
        it.meeting_link = req.meeting_link
    if req.instructions:
        it.instructions = req.instructions
    if req.status:
        it.status = req.status
    if req.notes:
        it.notes = req.notes

    # Notification to candidate
    if it.candidate and it.candidate.user:
        notif = Notification(
            user_id=it.candidate.user.id,
            title=f"Interview {it.status.value.title()}",
            message=f"Your interview for '{it.job.title}' was updated.",
            type="INTERVIEW",
            link="/candidate/interviews"
        )
        db.add(notif)

    db.commit()
    db.refresh(it)

    cand_user = it.candidate.user if it.candidate else None
    return {
        "id": it.id,
        "application_id": it.application_id,
        "recruiter_id": it.recruiter_id,
        "candidate_id": it.candidate_id,
        "job_id": it.job_id,
        "job_title": it.job.title if it.job else "",
        "company_name": it.job.company.name if (it.job and it.job.company) else "",
        "candidate_name": cand_user.full_name if cand_user else "",
        "candidate_email": cand_user.email if cand_user else "",
        "interview_date": it.interview_date,
        "interview_type": it.interview_type,
        "meeting_link": it.meeting_link,
        "instructions": it.instructions,
        "status": it.status,
        "notes": it.notes,
        "created_at": it.created_at
    }

# --- Candidate AI Mock Interview & Practice ---

@router.post("/mock/start", response_model=MockInterviewSessionResponse)
def start_mock_interview(
    req: MockInterviewStartRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """
    Start an interactive Mock Interview session for a chosen technology or role.
    Generates tailored questions from curated question sets.
    """
    tech_key = req.role_or_tech.lower().strip()
    questions_pool = CURATED_PRACTICE_QUESTIONS.get(tech_key)
    if not questions_pool:
        # Default question pool if technology is not in dictionary
        questions_pool = [
            f"Explain how you design scalable architectures when building applications with {req.role_or_tech}.",
            f"What are the most common performance bottlenecks in {req.role_or_tech} and how do you resolve them?",
            f"Describe a complex technical challenge you solved using {req.role_or_tech}.",
            f"How do you test and ensure code quality in {req.role_or_tech} projects?",
            f"What best practices do you follow for security and error handling in {req.role_or_tech}?"
        ]

    session = InterviewSession(
        candidate_id=candidate.id,
        role_or_tech=req.role_or_tech,
        total_questions=min(len(questions_pool), req.num_questions)
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Add questions
    for q_text in questions_pool[:req.num_questions]:
        q = InterviewQuestion(
            session_id=session.id,
            question_text=q_text,
            category="Technical",
            difficulty=req.difficulty
        )
        db.add(q)
    db.commit()
    db.refresh(session)

    return session

@router.get("/mock/sessions", response_model=List[MockInterviewSessionResponse])
def get_mock_sessions(
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """List candidate's past interview practice sessions."""
    sessions = db.query(InterviewSession).filter(
        InterviewSession.candidate_id == candidate.id
    ).order_by(InterviewSession.created_at.desc()).all()
    return sessions

@router.post("/mock/questions/{question_id}/answer")
def submit_mock_answer(
    question_id: int,
    req: MockInterviewAnswerSubmit,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """
    Submit candidate's answer for an interview question.
    Calls AIService for evaluation. If no AI API key is configured,
    returns a clear feature-unavailable notice without pretending AI succeeded.
    """
    question = db.query(InterviewQuestion).filter(InterviewQuestion.id == question_id).first()
    if not question:
        raise NotFoundException("Interview Question")

    # Call AI evaluation
    ai_status = "UNAVAILABLE"
    score = None
    feedback = None
    strengths = None
    improvements = None

    if AIService.is_configured():
        eval_result = AIService.evaluate_interview_answer(
            question=question.question_text,
            answer=req.answer_text,
            role_or_tech=question.session.role_or_tech
        )
        score = eval_result.get("score")
        feedback = eval_result.get("feedback")
        strengths = eval_result.get("strengths")
        improvements = eval_result.get("improvements")
        ai_status = "EVALUATED"
    else:
        feedback = "Live AI Evaluation is currently unavailable because no AI API key is configured in the environment. Your answer has been saved to your practice session record."

    answer_record = InterviewAnswer(
        question_id=question.id,
        candidate_id=candidate.id,
        candidate_answer=req.answer_text,
        ai_feedback=feedback,
        score=score,
        strengths=strengths,
        improvements=improvements
    )
    db.add(answer_record)
    db.commit()

    return {
        "question_id": question.id,
        "ai_status": ai_status,
        "score": score,
        "feedback": feedback,
        "strengths": strengths,
        "improvements": improvements,
        "ai_configured": AIService.is_configured()
    }
