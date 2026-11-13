from typing import List, Optional
import datetime
from pydantic import BaseModel, Field
from app.models.interview import InterviewStatusEnum

class InterviewCreate(BaseModel):
    application_id: int
    interview_date: datetime.datetime
    interview_type: str = "Video Call"
    meeting_link: Optional[str] = None
    instructions: Optional[str] = None
    notes: Optional[str] = None

class InterviewUpdate(BaseModel):
    interview_date: Optional[datetime.datetime] = None
    interview_type: Optional[str] = None
    meeting_link: Optional[str] = None
    instructions: Optional[str] = None
    status: Optional[InterviewStatusEnum] = None
    notes: Optional[str] = None

class InterviewResponse(BaseModel):
    id: int
    application_id: int
    recruiter_id: int
    candidate_id: int
    job_id: int
    job_title: str
    company_name: str
    candidate_name: str
    candidate_email: str
    interview_date: datetime.datetime
    interview_type: str
    meeting_link: Optional[str] = None
    instructions: Optional[str] = None
    status: InterviewStatusEnum
    notes: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# Mock Interview Schemas
class MockInterviewStartRequest(BaseModel):
    role_or_tech: str = Field(..., min_length=2)
    difficulty: str = "Intermediate"
    num_questions: int = 5

class MockInterviewQuestionResponse(BaseModel):
    id: int
    question_text: str
    category: str
    difficulty: str

class MockInterviewAnswerSubmit(BaseModel):
    answer_text: str = Field(..., min_length=5)

class MockInterviewFeedbackResponse(BaseModel):
    question_id: int
    score: float
    feedback: str
    strengths: str
    improvements: str

class MockInterviewSessionResponse(BaseModel):
    id: int
    role_or_tech: str
    total_questions: int
    completed: Optional[datetime.datetime] = None
    feedback_summary: Optional[str] = None
    questions: List[MockInterviewQuestionResponse] = []
    created_at: datetime.datetime

    class Config:
        from_attributes = True
