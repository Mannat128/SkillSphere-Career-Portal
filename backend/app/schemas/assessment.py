from typing import List, Optional
import datetime
from pydantic import BaseModel

class AssessmentListItem(BaseModel):
    id: int
    title: str
    technology: str
    description: Optional[str] = None
    difficulty: str
    duration_minutes: int
    passing_score: float
    total_questions: int

    class Config:
        from_attributes = True

class AssessmentQuestionItem(BaseModel):
    id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str

class AssessmentAttemptStart(BaseModel):
    attempt_id: int
    assessment_id: int
    title: str
    technology: str
    duration_minutes: int
    started_at: datetime.datetime
    questions: List[AssessmentQuestionItem]

class QuestionAnswerSubmission(BaseModel):
    question_id: int
    selected_option: str # 'A', 'B', 'C', 'D'

class AssessmentSubmissionRequest(BaseModel):
    answers: List[QuestionAnswerSubmission]

class AssessmentQuestionResultItem(BaseModel):
    question_id: int
    question_text: str
    selected_option: str
    correct_option: str
    is_correct: bool
    explanation: Optional[str] = None

class AssessmentAttemptResultResponse(BaseModel):
    attempt_id: int
    assessment_title: str
    technology: str
    score: float
    total_score: float
    passed: bool
    started_at: datetime.datetime
    completed_at: datetime.datetime
    question_results: List[AssessmentQuestionResultItem] = []

    class Config:
        from_attributes = True
