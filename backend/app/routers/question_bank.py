
import io
import csv
import re
from difflib import SequenceMatcher
from typing import List, Optional, Literal

from fastapi import (
    APIRouter, Depends, Query, UploadFile, File,
    Form, Response, status
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from app.database.session import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException
)
from app.services.ai_service import AIService
from app.models.user import User, UserRole
from app.models.recruiter import Recruiter
from app.models.recruiter_assessment import QuestionBankQuestion
from app.schemas.recruiter_assessment import (
    QuestionCreate,
    QuestionUpdate,
    QuestionResponse,
)

router = APIRouter(
    prefix="/question-bank",
    tags=["Question Bank"],
    dependencies=[Depends(require_role(UserRole.RECRUITER))],
)


class AIGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=100)
    difficulty: Literal["Easy", "Medium", "Hard"] = "Medium"
    count: int = Field(5, ge=1, le=20)
    question_type: Literal[
        "Mixed",
        "Conceptual",
        "Code Snippet",
        "Fill in the Blank",
        "Scenario-based",
    ] = "Mixed"
    provider: Optional[
        Literal["google_gemini", "gemini"]
    ] = None


class AIGeneratedQuestionSaveRequest(BaseModel):
    questions: List[QuestionCreate] = Field(..., min_length=1, max_length=20)
    save_to_bank: bool = True
    job_id: Optional[int] = None


def get_recruiter_profile(current_user: User, db: Session):
    if current_user.role != UserRole.RECRUITER:
        raise ForbiddenException("Only recruiters can access the Question Bank.")

    recruiter = db.query(Recruiter).filter(
        Recruiter.user_id == current_user.id
    ).first()

    if not recruiter:
        raise ForbiddenException("Recruiter profile not found.")

    return recruiter


def normalize_question_text(value: str) -> str:
    """Normalize question text for exact and near-duplicate checks."""
    value = (value or "").casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def is_near_duplicate(candidate: str, existing_texts: set, threshold: float = 0.92) -> bool:
    normalized = normalize_question_text(candidate)
    if not normalized:
        return False

    for existing in existing_texts:
        other = normalize_question_text(existing)
        if normalized == other:
            return True
        # Avoid noisy similarity matches on very short questions.
        if min(len(normalized), len(other)) >= 30:
            if SequenceMatcher(None, normalized, other).ratio() >= threshold:
                return True
    return False


def get_existing_question_texts(db: Session, current_user: User):
    recruiter = get_recruiter_profile(current_user, db)
    query = db.query(QuestionBankQuestion.question_text)

    query = query.filter(
        or_(
            QuestionBankQuestion.is_shared == True,
            QuestionBankQuestion.recruiter_id == recruiter.id
        )
    )

    return {
        item[0].strip()
        for item in query.all()
        if item[0]
    }


# ---------------- AI QUESTION GENERATION ----------------

@router.post("/ai-generate")
def generate_ai_questions(
    req: AIGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_recruiter_profile(current_user, db)

    generated = AIService.generate_mcq_questions(
        topic=req.topic,
        difficulty=req.difficulty,
        count=req.count,
        question_type=req.question_type,
        provider=req.provider,
    )

    existing_texts = get_existing_question_texts(db, current_user)
    seen_generated = set()
    preview_questions = []

    for question in generated:
        normalized = normalize_question_text(question["question_text"])

        duplicate = (
            is_near_duplicate(question["question_text"], existing_texts)
            or is_near_duplicate(question["question_text"], seen_generated)
        )

        seen_generated.add(question["question_text"])

        preview_questions.append({
            **question,
            "is_duplicate": duplicate
        })

    return {
        "success": True,
        "saved": False,
        "message": "Review generated questions before saving.",
        "provider": req.provider or "configured_default",
        "topic": req.topic.strip(),
        "difficulty": req.difficulty,
        "requested_count": req.count,
        "generated_count": len(preview_questions),
        "duplicate_count": sum(
            1 for q in preview_questions if q["is_duplicate"]
        ),
        "questions": preview_questions
    }


@router.post("/ai-generate/save", response_model=List[QuestionResponse], status_code=status.HTTP_201_CREATED)
def save_reviewed_ai_questions(
    req: AIGeneratedQuestionSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persist recruiter-reviewed questions; generation itself never saves."""
    recruiter = get_recruiter_profile(current_user, db)
    is_shared = False
    target_job_id = None if req.save_to_bank else req.job_id
    if not req.save_to_bank:
        if not req.job_id:
            raise BadRequestException("Please select a job for these questions.")
        from app.models.job import Job
        owned_job = db.query(Job).filter(
            Job.id == req.job_id,
            Job.recruiter_id == recruiter.id
        ).first()
        if not owned_job:
            raise ForbiddenException("You can only add questions to your own jobs.")

    existing_texts = get_existing_question_texts(db, current_user)
    batch_texts = set()
    entities = []

    for item in req.questions:
        normalized = normalize_question_text(item.question_text)
        if is_near_duplicate(item.question_text, existing_texts | batch_texts):
            raise BadRequestException(
                "A duplicate or near-duplicate question was found. Remove it before saving."
            )
        batch_texts.add(item.question_text)

        entities.append(QuestionBankQuestion(
            recruiter_id=recruiter.id if recruiter else None,
            job_id=target_job_id,
            created_by_id=current_user.id,
            is_shared=is_shared,
            question_text=item.question_text.strip(),
            category=item.category.strip(),
            difficulty=item.difficulty.title(),
            option_a=item.option_a.strip(),
            option_b=item.option_b.strip(),
            option_c=item.option_c.strip(),
            option_d=item.option_d.strip(),
            correct_answer=item.correct_answer.strip().upper(),
            marks=item.marks,
            explanation=item.explanation.strip() if item.explanation else None,
        ))

    db.add_all(entities)
    db.commit()
    for entity in entities:
        db.refresh(entity)
    return entities


# ---------------- GET QUESTION BANK ----------------

@router.get("", response_model=List[QuestionResponse])
def get_question_bank(
    category: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    source: str = Query("all"),
    job_id: Optional[int] = Query(None),
    include_job_specific: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recruiter = get_recruiter_profile(current_user, db)
    query = db.query(QuestionBankQuestion)
    recruiter_id = recruiter.id

    if source == "mine":
        query = query.filter(
            QuestionBankQuestion.recruiter_id == recruiter_id,
            QuestionBankQuestion.job_id.is_(None)
        )

    elif source == "shared":
        query = query.filter(QuestionBankQuestion.is_shared == True)

    elif source == "job":
        if not job_id:
            return []

        query = query.filter(
            QuestionBankQuestion.job_id == job_id,
            QuestionBankQuestion.recruiter_id == recruiter_id
        )

    elif job_id:
        query = query.filter(
            or_(
                QuestionBankQuestion.job_id == job_id,
                and_(
                    QuestionBankQuestion.job_id.is_(None),
                    or_(
                        QuestionBankQuestion.is_shared == True,
                        QuestionBankQuestion.recruiter_id == recruiter_id
                    )
                )
            )
        )

    elif include_job_specific:
        query = query.filter(
            or_(
                QuestionBankQuestion.is_shared == True,
                QuestionBankQuestion.recruiter_id == recruiter_id
            )
        )

    else:
        query = query.filter(
            QuestionBankQuestion.job_id.is_(None),
            or_(
                QuestionBankQuestion.is_shared == True,
                QuestionBankQuestion.recruiter_id == recruiter_id
            )
        )

    if category and category.strip():
        query = query.filter(
            QuestionBankQuestion.category.ilike(
                f"%{category.strip()}%"
            )
        )

    if difficulty and difficulty.strip():
        query = query.filter(
            QuestionBankQuestion.difficulty == difficulty.strip().title()
        )

    if search and search.strip():
        query = query.filter(
            QuestionBankQuestion.question_text.ilike(
                f"%{search.strip()}%"
            )
        )

    return query.order_by(
        desc(QuestionBankQuestion.created_at)
    ).all()


# ---------------- CATEGORIES ----------------

@router.get("/categories")
def get_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recruiter = get_recruiter_profile(current_user, db)
    query = db.query(QuestionBankQuestion.category).filter(
        or_(
            QuestionBankQuestion.is_shared == True,
            QuestionBankQuestion.recruiter_id == recruiter.id
        )
    )

    categories = query.distinct().all()

    return sorted({
        item[0] for item in categories if item[0]
    })


# ---------------- CREATE QUESTION ----------------

@router.post(
    "",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED
)
def add_question_manually(
    req: QuestionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recruiter = get_recruiter_profile(current_user, db)

    is_shared = False
    target_job_id = req.job_id if not req.save_to_bank and req.job_id else None

    if not req.save_to_bank and not req.job_id:
        raise BadRequestException("Please select a job for this question.")

    if not req.save_to_bank:
        from app.models.job import Job
        owned_job = db.query(Job).filter(
            Job.id == req.job_id,
            Job.recruiter_id == recruiter.id
        ).first()
        if not owned_job:
            raise ForbiddenException("You can only add questions to your own jobs.")

    question = QuestionBankQuestion(
        recruiter_id=recruiter.id if recruiter else None,
        job_id=target_job_id,
        created_by_id=current_user.id,
        is_shared=is_shared,
        question_text=req.question_text.strip(),
        category=req.category.strip(),
        difficulty=req.difficulty.title(),
        option_a=req.option_a.strip(),
        option_b=req.option_b.strip(),
        option_c=req.option_c.strip(),
        option_d=req.option_d.strip(),
        correct_answer=req.correct_answer.strip().upper(),
        marks=req.marks,
        explanation=req.explanation.strip() if req.explanation else None
    )

    db.add(question)
    db.commit()
    db.refresh(question)

    return question


# ---------------- CSV TEMPLATE ----------------

@router.get("/template/csv")
def download_csv_template():
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "question_text",
        "category",
        "difficulty",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "correct_answer",
        "marks",
        "explanation"
    ])

    writer.writerow([
        "Which Python collection type is ordered and mutable?",
        "Python",
        "Easy",
        "Set",
        "List",
        "Tuple",
        "Frozenset",
        "B",
        "1.0",
        "Lists are mutable ordered sequences in Python."
    ])

    output.seek(0)

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=SkillSphere_Question_Upload_Template.csv"
        }
    )


# ---------------- FILE PARSING AND VALIDATION ----------------

def _parse_and_validate_question_file(
    content: bytes,
    filename: str,
    existing_texts: set
):
    rows = []

    if filename.lower().endswith(".csv"):
        text_content = content.decode(
            "utf-8-sig",
            errors="replace"
        )

        reader = csv.DictReader(io.StringIO(text_content))
        rows = list(reader)

    else:
        import openpyxl

        workbook = openpyxl.load_workbook(
            io.BytesIO(content),
            data_only=True
        )

        sheet = workbook.active
        headers = [cell.value for cell in sheet[1]]

        for values in sheet.iter_rows(
            min_row=2,
            values_only=True
        ):
            if any(values):
                rows.append(dict(zip(headers, values)))

    if not rows:
        raise BadRequestException("No question rows found in file.")

    errors = []
    parsed_items = []
    seen_in_file = set()

    for index, row in enumerate(rows, start=2):
        normalized = {
            str(key).strip().lower(): value
            for key, value in row.items()
            if key is not None
        }

        q_text = str(normalized.get("question_text") or "").strip()
        category = str(normalized.get("category") or "").strip()
        difficulty = str(
            normalized.get("difficulty") or "Medium"
        ).strip().title()

        options = {
            key: str(normalized.get(f"option_{key}") or "").strip()
            for key in ["a", "b", "c", "d"]
        }

        correct = str(
            normalized.get("correct_answer") or ""
        ).strip().upper()

        explanation = str(
            normalized.get("explanation") or ""
        ).strip()

        row_errors = []

        if len(q_text) < 5:
            row_errors.append("Question text must contain at least 5 characters.")

        if not category:
            row_errors.append("Category is required.")

        if difficulty not in ["Easy", "Medium", "Hard"]:
            row_errors.append("Difficulty must be Easy, Medium, or Hard.")

        if any(not value for value in options.values()):
            row_errors.append("All four options are required.")

        if correct not in ["A", "B", "C", "D"]:
            row_errors.append("Correct answer must be A, B, C, or D.")

        try:
            marks = float(normalized.get("marks") or 1)
            if marks <= 0:
                row_errors.append("Marks must be greater than zero.")
        except (ValueError, TypeError):
            marks = 1.0
            row_errors.append("Marks must be a valid number.")

        normalized_text = q_text.casefold()
        duplicate = (
            normalized_text in seen_in_file
            or is_near_duplicate(q_text, existing_texts)
        )

        if normalized_text in seen_in_file:
            row_errors.append("Duplicate question within this file.")

        seen_in_file.add(normalized_text)

        if row_errors:
            errors.append({
                "row": index,
                "errors": row_errors,
                "question_snippet": q_text[:60]
            })
        else:
            parsed_items.append({
                "question_text": q_text,
                "category": category,
                "difficulty": difficulty,
                "option_a": options["a"],
                "option_b": options["b"],
                "option_c": options["c"],
                "option_d": options["d"],
                "correct_answer": correct,
                "marks": marks,
                "explanation": explanation or None,
                "is_duplicate": duplicate
            })

    return rows, errors, parsed_items


# ---------------- BULK UPLOAD PREVIEW ----------------

@router.post("/bulk-upload/preview")
async def preview_bulk_upload(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    get_recruiter_profile(current_user, db)

    if not file.filename:
        raise BadRequestException("No file provided.")

    filename = file.filename.lower()

    if not (filename.endswith(".csv") or filename.endswith(".xlsx")):
        raise BadRequestException("Upload a CSV or XLSX file.")

    content = await file.read()

    if not content:
        raise BadRequestException("Uploaded file is empty.")

    existing_texts = get_existing_question_texts(db, current_user)

    rows, errors, parsed_items = _parse_and_validate_question_file(
        content,
        file.filename,
        existing_texts
    )

    return {
        "valid": len(errors) == 0,
        "total_rows": len(rows),
        "valid_count": len(parsed_items),
        "error_count": len(errors),
        "errors": errors,
        "preview_questions": parsed_items[:30]
    }


# ---------------- BULK UPLOAD SAVE ----------------

@router.post("/bulk-upload")
async def bulk_upload_questions(
    file: UploadFile = File(...),
    save_to_bank: bool = Form(True),
    job_id: Optional[int] = Form(None),
    is_shared: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recruiter = get_recruiter_profile(current_user, db)

    if not file.filename:
        raise BadRequestException("No file provided.")

    filename = file.filename.lower()

    if not (filename.endswith(".csv") or filename.endswith(".xlsx")):
        raise BadRequestException("Upload a CSV or XLSX file.")

    if not save_to_bank:
        if not job_id:
            raise BadRequestException("Please select a job.")

        from app.models.job import Job

        owned_job = db.query(Job).filter(
            Job.id == job_id,
            Job.recruiter_id == recruiter.id
        ).first()

        if not owned_job:
            raise ForbiddenException(
                "You can only add questions to your own jobs."
            )

    content = await file.read()

    if not content:
        raise BadRequestException("Uploaded file is empty.")

    existing_texts = get_existing_question_texts(db, current_user)

    rows, errors, parsed_items = _parse_and_validate_question_file(
        content,
        file.filename,
        existing_texts
    )

    if errors:
        return {
            "success": False,
            "message": (
                f"Validation failed with {len(errors)} row errors. "
                "Correct the errors and upload again."
            ),
            "total_rows": len(rows),
            "valid_count": len(parsed_items),
            "errors": errors
        }

    target_job_id = job_id if not save_to_bank else None
    shared_value = False

    entities = [
        QuestionBankQuestion(
            recruiter_id=recruiter.id if recruiter else None,
            job_id=target_job_id,
            created_by_id=current_user.id,
            is_shared=shared_value,
            question_text=item["question_text"],
            category=item["category"],
            difficulty=item["difficulty"],
            option_a=item["option_a"],
            option_b=item["option_b"],
            option_c=item["option_c"],
            option_d=item["option_d"],
            correct_answer=item["correct_answer"],
            marks=item["marks"],
            explanation=item["explanation"]
        )
        for item in parsed_items
    ]

    db.add_all(entities)
    db.commit()

    destination = (
        "Shared Question Bank"
        if shared_value
        else (
            "your Question Bank"
            if not target_job_id
            else f"Job #{target_job_id} Assessment"
        )
    )

    return {
        "success": True,
        "message": (
            f"Successfully imported {len(entities)} questions "
            f"into {destination}."
        ),
        "imported_count": len(entities)
    }


# ---------------- GET SINGLE QUESTION ----------------

@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recruiter = get_recruiter_profile(current_user, db)
    question = db.query(QuestionBankQuestion).filter(
        QuestionBankQuestion.id == question_id,
        or_(
            QuestionBankQuestion.is_shared == True,
            QuestionBankQuestion.recruiter_id == recruiter.id,
        ),
    ).first()

    if not question:
        raise NotFoundException("Question")

    return question


# ---------------- UPDATE QUESTION ----------------

@router.put("/{question_id}", response_model=QuestionResponse)
def update_question(
    question_id: int,
    req: QuestionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recruiter = get_recruiter_profile(current_user, db)
    question = db.query(QuestionBankQuestion).filter(
        QuestionBankQuestion.id == question_id,
        QuestionBankQuestion.recruiter_id == recruiter.id,
        QuestionBankQuestion.is_shared == False,
    ).first()

    if not question:
        raise NotFoundException("Question")

    fields = [
        "question_text",
        "category",
        "difficulty",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "correct_answer",
        "marks",
        "explanation"
    ]

    for field in fields:
        value = getattr(req, field, None)

        if value is not None:
            if isinstance(value, str):
                value = value.strip()

            setattr(question, field, value)

    if req.difficulty:
        question.difficulty = req.difficulty.title()

    if req.correct_answer:
        question.correct_answer = req.correct_answer.upper()

    db.commit()
    db.refresh(question)

    return question


# ---------------- DELETE QUESTION ----------------

@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recruiter = get_recruiter_profile(current_user, db)
    question = db.query(QuestionBankQuestion).filter(
        QuestionBankQuestion.id == question_id,
        QuestionBankQuestion.recruiter_id == recruiter.id,
        QuestionBankQuestion.is_shared == False,
    ).first()

    if not question:
        raise NotFoundException("Question")

    db.delete(question)
    db.commit()

    return {
        "message": "Question deleted successfully."
    }
