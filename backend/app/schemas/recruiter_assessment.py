from typing import List, Optional, Dict, Any
import datetime
from pydantic import BaseModel, Field, ConfigDict

# --- Question Bank ---

class QuestionCreate(BaseModel):
    question_text: str = Field(..., min_length=5)
    category: str = Field(..., min_length=2)
    difficulty: str = Field("Medium", pattern="^(Easy|Medium|Hard)$")
    option_a: str = Field(..., min_length=1)
    option_b: str = Field(..., min_length=1)
    option_c: str = Field(..., min_length=1)
    option_d: str = Field(..., min_length=1)
    correct_answer: str = Field(..., pattern="^(A|B|C|D)$")
    marks: float = Field(1.0, gt=0)
    explanation: Optional[str] = None
    is_shared: bool = False
    save_to_bank: bool = True
    job_id: Optional[int] = None

class QuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    correct_answer: Optional[str] = None
    marks: Optional[float] = None
    explanation: Optional[str] = None
    job_id: Optional[int] = None

class QuestionResponse(BaseModel):
    id: int
    recruiter_id: Optional[int] = None
    job_id: Optional[int] = None
    is_shared: bool
    question_text: str
    category: str
    difficulty: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_answer: str # Only accessible by Recruiter & Admin
    marks: float
    explanation: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

# Candidate view (correct answer NEVER exposed)
class CandidateQuestionItem(BaseModel):
    id: int
    question_text: str
    category: str
    difficulty: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    marks: float

# --- Job Assessment Configuration ---

class JobAssessmentConfigCreate(BaseModel):
    is_enabled: bool = True
    title: str = Field("First Round Technical MCQ Assessment", min_length=3)
    instructions: Optional[str] = None
    total_questions: int = Field(10, ge=1, le=100)
    duration_minutes: int = Field(30, ge=1, le=300)
    total_marks: float = Field(10.0, gt=0)
    passing_marks: float = Field(6.0, ge=0)
    qualification_rule: str = Field(">", pattern="^(>|>=)$")
    negative_marking: bool = False
    negative_marks: float = Field(0.0, ge=0)
    categories: List[str] = []
    difficulty_distribution: Optional[Dict[str, int]] = None
    selection_mode: str = Field("RANDOM", pattern="^(RANDOM|SPECIFIC)$")
    selected_question_ids: Optional[List[int]] = None

class JobAssessmentConfigResponse(BaseModel):
    id: Optional[int] = None
    job_id: int
    is_enabled: bool
    title: str
    instructions: Optional[str] = None
    total_questions: int
    duration_minutes: int
    total_marks: float
    passing_marks: float
    qualification_rule: str
    negative_marking: bool
    negative_marks: float
    categories: List[str] = []
    difficulty_distribution: Optional[Dict[str, int]] = None
    selection_mode: str
    selected_question_ids: Optional[List[int]] = None
    eligible_questions_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)

# --- Candidate Assessment Flow ---

class CandidateAssignmentListItem(BaseModel):
    id: int # assignment_id
    job_id: int
    job_title: str
    company_name: str
    assessment_title: str
    total_questions: int
    duration_minutes: int
    total_marks: float
    passing_marks: float
    qualification_rule: str
    negative_marking: bool
    negative_marks: float
    status: str # PENDING, IN_PROGRESS, SUBMITTED, QUALIFIED, NOT_QUALIFIED, EXPIRED
    assigned_at: datetime.datetime
    started_at: Optional[datetime.datetime] = None
    expires_at: Optional[datetime.datetime] = None
    is_submitted: bool = False
    is_qualified: Optional[bool] = None

class CandidateTestStartResponse(BaseModel):
    attempt_id: int
    assignment_id: int
    title: str
    duration_minutes: int
    started_at: datetime.datetime
    expires_at: datetime.datetime
    remaining_seconds: int
    negative_marking: bool
    negative_marks: float
    questions: List[CandidateQuestionItem]
    saved_answers: Dict[str, str]
    marked_for_review: List[int]

class SaveAnswerRequest(BaseModel):
    question_id: int
    selected_option: Optional[str] = None # 'A', 'B', 'C', 'D' or None
    is_marked_for_review: Optional[bool] = None

class SubmitAssessmentRequest(BaseModel):
    final_answers: Optional[Dict[str, str]] = None

class CandidateAssessmentResultResponse(BaseModel):
    assignment_id: int
    job_title: str
    assessment_title: str
    obtained_marks: float
    total_marks: float
    percentage: float
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    passing_marks: float
    qualification_rule: str
    is_qualified: bool
    qualification_message: str
    submitted_at: datetime.datetime
    time_taken_seconds: int

# --- Recruiter Results Dashboard ---

class RecruiterAssessmentResultItem(BaseModel):
    id: int
    candidate_id: int
    candidate_name: str
    candidate_email: str
    job_id: int
    job_title: str
    assessment_title: str
    obtained_marks: float
    total_marks: float
    percentage: float
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    passing_marks: float
    qualification_rule: str
    is_qualified: bool
    time_taken_seconds: int
    evaluated_at: datetime.datetime
    question_breakdown: Optional[List[Dict[str, Any]]] = None

    model_config = ConfigDict(from_attributes=True)
