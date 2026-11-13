import io
import csv
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from app.database.session import get_db
from app.core.dependencies import get_current_user, get_current_recruiter
from app.core.exceptions import NotFoundException, BadRequestException, ForbiddenException
from app.models.user import User, UserRole
from app.models.recruiter import Recruiter
from app.models.recruiter_assessment import QuestionBankQuestion
from app.schemas.recruiter_assessment import (
    QuestionCreate,
    QuestionUpdate,
    QuestionResponse,
)

router = APIRouter(prefix="/question-bank", tags=["Recruiter Question Bank"])

@router.get("", response_model=List[QuestionResponse])
def get_question_bank(
    category: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    source: str = Query("all", description="Source filter: 'all', 'mine', 'shared', or 'job'"),
    job_id: Optional[int] = Query(None, description="Optional job ID to filter questions"),
    include_job_specific: bool = Query(False, description="Include questions created only for jobs"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Option 3: Select from Question Bank.
    Retrieve questions accessible to this recruiter:
    - Their own personal Question Bank questions
    - Admin-approved shared questions
    - Specific questions created for a job assessment (when job_id is provided)
    """
    recruiter = None
    if current_user.role == UserRole.RECRUITER:
        recruiter = db.query(Recruiter).filter(Recruiter.user_id == current_user.id).first()

    query = db.query(QuestionBankQuestion)

    if current_user.role == UserRole.ADMIN:
        # Admin can view all questions
        if source == "shared":
            query = query.filter(QuestionBankQuestion.is_shared == True)
        elif source == "mine":
            query = query.filter(QuestionBankQuestion.created_by_id == current_user.id)
        elif source == "job" and job_id:
            query = query.filter(QuestionBankQuestion.job_id == job_id)
    else:
        # Recruiter
        recruiter_id = recruiter.id if recruiter else None
        if source == "mine":
            query = query.filter(
                QuestionBankQuestion.recruiter_id == recruiter_id,
                QuestionBankQuestion.job_id.is_(None)
            )
        elif source == "shared":
            query = query.filter(QuestionBankQuestion.is_shared == True)
        elif source == "job" and job_id:
            query = query.filter(QuestionBankQuestion.job_id == job_id)
        else: # "all"
            if job_id:
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
            elif not include_job_specific:
                # Default: Show only questions in general Question Bank
                query = query.filter(
                    QuestionBankQuestion.job_id.is_(None),
                    or_(
                        QuestionBankQuestion.is_shared == True,
                        QuestionBankQuestion.recruiter_id == recruiter_id
                    )
                )
            else:
                query = query.filter(
                    or_(
                        QuestionBankQuestion.is_shared == True,
                        QuestionBankQuestion.recruiter_id == recruiter_id
                    )
                )

    if category and category.strip():
        query = query.filter(QuestionBankQuestion.category.ilike(f"%{category.strip()}%"))

    if difficulty and difficulty.strip():
        query = query.filter(QuestionBankQuestion.difficulty == difficulty.strip().title())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(QuestionBankQuestion.question_text.ilike(term))

    return query.order_by(desc(QuestionBankQuestion.created_at)).all()

@router.get("/categories")
def get_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of distinct question categories in Question Bank."""
    categories = db.query(QuestionBankQuestion.category).distinct().all()
    names = sorted(list(set(c[0] for c in categories if c[0])))
    return names

@router.post("", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
def add_question_manually(
    req: QuestionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Option 1: Add Manually.
    Recruiter creates a new MCQ with 4 options, correct answer, category, difficulty, marks, and explanation.
    Can be saved to personal Question Bank or used only for the current job assessment.
    """
    recruiter = None
    if current_user.role == UserRole.RECRUITER:
        recruiter = db.query(Recruiter).filter(Recruiter.user_id == current_user.id).first()

    is_shared = (current_user.role == UserRole.ADMIN and req.is_shared)
    target_job_id = req.job_id if (not req.save_to_bank and req.job_id) else None

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

@router.get("/template/csv")
def download_csv_template():
    """
    Downloadable CSV template for Bulk Question Upload.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "question_text", "category", "difficulty",
        "option_a", "option_b", "option_c", "option_d",
        "correct_answer", "marks", "explanation"
    ])
    # Sample row
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
        headers={"Content-Disposition": "attachment; filename=SkillSphere_Question_Upload_Template.csv"}
    )

def _parse_and_validate_question_file(content: bytes, filename: str, existing_texts: set):
    """Internal helper to parse and validate CSV/XLSX questions."""
    filename_lower = filename.lower()
    rows = []
    if filename_lower.endswith(".csv"):
        text_content = content.decode("utf-8-sig", errors="replace")
        csv_reader = csv.DictReader(io.StringIO(text_content))
        for row in csv_reader:
            rows.append(row)
    else: # Excel
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        sheet = wb.active
        headers = [cell.value for cell in sheet[1]]
        for row_cells in sheet.iter_rows(min_row=2, values_only=True):
            if any(row_cells):
                row_dict = dict(zip(headers, row_cells))
                rows.append(row_dict)

    if not rows:
        raise BadRequestException("No question rows found in file.")

    errors = []
    parsed_items = []
    seen_in_file = set()

    for idx, r in enumerate(rows, start=2): # row 1 is header
        normalized = {str(k).strip().lower(): v for k, v in r.items() if k is not None}

        q_text = str(normalized.get("question_text") or "").strip()
        cat = str(normalized.get("category") or "").strip()
        diff = str(normalized.get("difficulty") or "Medium").strip().title()
        opt_a = str(normalized.get("option_a") or "").strip()
        opt_b = str(normalized.get("option_b") or "").strip()
        opt_c = str(normalized.get("option_c") or "").strip()
        opt_d = str(normalized.get("option_d") or "").strip()
        correct = str(normalized.get("correct_answer") or "").strip().upper()
        marks_raw = normalized.get("marks", 1.0)
        expl = str(normalized.get("explanation") or "").strip()

        row_errors = []
        if not q_text or len(q_text) < 5:
            row_errors.append("Question text is required (min 5 characters)")
        if not cat:
            row_errors.append("Category is required")
        if diff not in ["Easy", "Medium", "Hard"]:
            row_errors.append(f"Difficulty must be Easy, Medium, or Hard (got '{diff}')")
        if not opt_a or not opt_b or not opt_c or not opt_d:
            row_errors.append("All 4 options (A, B, C, D) are required")
        if correct not in ["A", "B", "C", "D"]:
            row_errors.append(f"Correct answer must be A, B, C, or D (got '{correct}')")

        try:
            marks = float(marks_raw) if marks_raw else 1.0
            if marks <= 0:
                row_errors.append("Marks must be greater than 0")
        except ValueError:
            row_errors.append("Marks must be a valid number")
            marks = 1.0

        # Duplicate check
        normalized_text = q_text.lower().strip()
        is_duplicate = False
        if normalized_text in seen_in_file:
            row_errors.append("Duplicate question within this file")
            is_duplicate = True
        elif normalized_text in existing_texts:
            is_duplicate = True

        seen_in_file.add(normalized_text)

        if row_errors:
            errors.append({"row": idx, "errors": row_errors, "question_snippet": q_text[:60]})
        else:
            parsed_items.append({
                "question_text": q_text,
                "category": cat,
                "difficulty": diff,
                "option_a": opt_a,
                "option_b": opt_b,
                "option_c": opt_c,
                "option_d": opt_d,
                "correct_answer": correct,
                "marks": marks,
                "explanation": expl if expl else None,
                "is_duplicate": is_duplicate,
            })

    return rows, errors, parsed_items

@router.post("/bulk-upload/preview")
async def preview_bulk_upload(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Preview bulk question upload without saving.
    Validates row by row, detects duplicates, and returns structured preview.
    """
    if not file.filename:
        raise BadRequestException("No file provided.")

    filename_lower = file.filename.lower()
    if not (filename_lower.endswith(".csv") or filename_lower.endswith(".xlsx")):
        raise BadRequestException("Please upload a .csv or .xlsx file.")

    content = await file.read()
    if len(content) == 0:
        raise BadRequestException("The uploaded file is empty.")

    recruiter = None
    if current_user.role == UserRole.RECRUITER:
        recruiter = db.query(Recruiter).filter(Recruiter.user_id == current_user.id).first()

    # Query existing question texts for duplicate detection
    existing_q_query = db.query(QuestionBankQuestion.question_text)
    if recruiter:
        existing_q_query = existing_q_query.filter(
            or_(
                QuestionBankQuestion.is_shared == True,
                QuestionBankQuestion.recruiter_id == recruiter.id
            )
        )
    existing_texts = {q[0].lower().strip() for q in existing_q_query.all() if q[0]}

    rows, errors, parsed_items = _parse_and_validate_question_file(content, file.filename, existing_texts)

    return {
        "valid": len(errors) == 0,
        "total_rows": len(rows),
        "valid_count": len(parsed_items),
        "error_count": len(errors),
        "errors": errors,
        "preview_questions": parsed_items[:30] # return first 30 for UI preview
    }

@router.post("/bulk-upload")
async def bulk_upload_questions(
    file: UploadFile = File(...),
    save_to_bank: bool = Form(True),
    job_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Option 2: Bulk Upload questions via CSV or Excel file.
    Validates required columns, rows, difficulty, correct_answer (A,B,C,D).
    Allows saving to recruiter's personal Question Bank or using only for current job.
    """
    if not file.filename:
        raise BadRequestException("No file provided.")

    filename_lower = file.filename.lower()
    if not (filename_lower.endswith(".csv") or filename_lower.endswith(".xlsx")):
        raise BadRequestException("Please upload a .csv or .xlsx file.")

    content = await file.read()
    if len(content) == 0:
        raise BadRequestException("The uploaded file is empty.")

    recruiter = None
    if current_user.role == UserRole.RECRUITER:
        recruiter = db.query(Recruiter).filter(Recruiter.user_id == current_user.id).first()

    existing_q_query = db.query(QuestionBankQuestion.question_text)
    if recruiter:
        existing_q_query = existing_q_query.filter(
            or_(
                QuestionBankQuestion.is_shared == True,
                QuestionBankQuestion.recruiter_id == recruiter.id
            )
        )
    existing_texts = {q[0].lower().strip() for q in existing_q_query.all() if q[0]}

    rows, errors, parsed_items = _parse_and_validate_question_file(content, file.filename, existing_texts)

    if errors:
        return {
            "success": False,
            "message": f"Validation failed with {len(errors)} row errors. Please correct the errors and re-upload.",
            "total_rows": len(rows),
            "valid_count": len(parsed_items),
            "errors": errors
        }

    target_job_id = job_id if (not save_to_bank and job_id) else None

    # Construct models
    entities = [
        QuestionBankQuestion(
            recruiter_id=recruiter.id if recruiter else None,
            job_id=target_job_id,
            created_by_id=current_user.id,
            is_shared=False,
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

    dest = "your Question Bank" if not target_job_id else f"Job #{target_job_id} Assessment"
    return {
        "success": True,
        "message": f"Successfully imported {len(entities)} questions into {dest}.",
        "imported_count": len(entities)
    }

@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve single question."""
    q = db.query(QuestionBankQuestion).filter(QuestionBankQuestion.id == question_id).first()
    if not q:
        raise NotFoundException("Question")
    return q

@router.put("/{question_id}", response_model=QuestionResponse)
def update_question(
    question_id: int,
    req: QuestionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Edit question in Question Bank."""
    q = db.query(QuestionBankQuestion).filter(QuestionBankQuestion.id == question_id).first()
    if not q:
        raise NotFoundException("Question")

    # Permission check: Recruiter can edit own question, admin can edit shared
    if current_user.role == UserRole.RECRUITER:
        recruiter = db.query(Recruiter).filter(Recruiter.user_id == current_user.id).first()
        if not recruiter or q.recruiter_id != recruiter.id:
            raise ForbiddenException("You cannot edit shared questions or questions from other recruiters.")

    if req.question_text:
        q.question_text = req.question_text.strip()
    if req.category:
        q.category = req.category.strip()
    if req.difficulty:
        q.difficulty = req.difficulty.title()
    if req.option_a:
        q.option_a = req.option_a.strip()
    if req.option_b:
        q.option_b = req.option_b.strip()
    if req.option_c:
        q.option_c = req.option_c.strip()
    if req.option_d:
        q.option_d = req.option_d.strip()
    if req.correct_answer:
        q.correct_answer = req.correct_answer.strip().upper()
    if req.marks is not None:
        q.marks = req.marks
    if req.explanation is not None:
        q.explanation = req.explanation.strip()

    db.commit()
    db.refresh(q)
    return q

@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete question from Question Bank."""
    q = db.query(QuestionBankQuestion).filter(QuestionBankQuestion.id == question_id).first()
    if not q:
        raise NotFoundException("Question")

    if current_user.role == UserRole.RECRUITER:
        recruiter = db.query(Recruiter).filter(Recruiter.user_id == current_user.id).first()
        if not recruiter or q.recruiter_id != recruiter.id:
            raise ForbiddenException("You can only delete your own private questions.")

    db.delete(q)
    db.commit()
    return {"message": "Question deleted successfully from Question Bank."}
