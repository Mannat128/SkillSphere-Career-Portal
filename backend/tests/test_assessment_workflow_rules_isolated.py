"""Isolated assessment scoring and recruiter-review rule tests."""

from types import SimpleNamespace

import pytest

from app.core.exceptions import BadRequestException
from app.routers import assessment_reviews
from app.routers import candidate_assessments
from app.routers.assessment_reviews import AssessmentReviewRequest
from app.routers.candidate_assessments import SaveAnswerRequest, start_or_resume_assessment, save_candidate_answer, submit_assessment
from app.models.proctoring import ProctoringSession
from app.models.recruiter_assessment import AssessmentAssignment, CandidateAssessmentAttempt, CandidateAssessmentResult
from app.services.assessment_assignment_service import AssessmentAssignmentService


class FakeQuery:
    def filter(self, *_conditions):
        return self

    def first(self):
        return None


class FakeSession:
    def __init__(self, assignment=None, recording=None):
        self.added = []
        self.assignment = assignment
        self.recording = recording

    def query(self, model):
        return FakeQueryResult(self.recording if model is ProctoringSession else None)

    def add(self, value):
        self.added.append(value)
        if isinstance(value, CandidateAssessmentAttempt):
            value.id = 901
            value.assignment = self.assignment
            self.assignment.attempt = value
        elif isinstance(value, CandidateAssessmentResult):
            value.id = 908
            value.assignment = self.assignment

    def commit(self):
        pass

    def refresh(self, _value):
        pass


class FakeQueryResult(FakeQuery):
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


@pytest.mark.parametrize(
    ("selected", "passing_marks", "expected_qualified"),
    [("A", 1.0, False), ("A", 0.5, True), ("B", 0.5, False)],
)
def test_assessment_scoring_is_strict_greater_than_and_pending_manual_review(
    selected, passing_marks, expected_qualified
):
    assignment = SimpleNamespace(
        id=301,
        candidate_id=401,
        job_id=501,
        config_snapshot={"passing_marks": passing_marks, "qualification_rule": ">"},
        private_answer_key={"9": "A"},
        assigned_questions=[{"id": 9, "question_text": "Synthetic?", "marks": 1.0}],
        candidate=None,
        job=None,
        status="IN_PROGRESS",
    )
    attempt = SimpleNamespace(
        id=601,
        assignment=assignment,
        is_submitted=False,
        saved_answers={"9": selected},
        started_at=None,
    )
    db = FakeSession()

    result = AssessmentAssignmentService.evaluate_attempt(db, attempt)

    assert result.is_qualified is expected_qualified
    assert result.qualification_rule == ">"
    assert result.review_status == "PENDING_REVIEW"
    assert assignment.status == "PENDING_REVIEW"
    assert attempt.is_submitted is True
    assert result.obtained_marks == (1.0 if selected == "A" else 0.0)


@pytest.mark.parametrize("decision", ["QUALIFIED", "NOT_QUALIFIED"])
def test_recruiter_review_sets_final_assignment_decision(monkeypatch, decision):
    assignment = SimpleNamespace(status="PENDING_REVIEW", updated_at=None)
    result = SimpleNamespace(
        id=701,
        review_status="PENDING_REVIEW",
        reviewed_by_id=None,
        reviewed_at=None,
        review_notes=None,
        assignment=assignment,
        candidate=None,
        job=None,
    )
    recruiter = SimpleNamespace(user_id=801)
    db = FakeSession()
    monkeypatch.setattr(
        assessment_reviews,
        "get_recruiter_owned_result",
        lambda *_args: result,
    )

    response = assessment_reviews.submit_assessment_review(
        result.id,
        AssessmentReviewRequest(decision=decision, review_notes="Synthetic review"),
        recruiter,
        db,
    )

    assert response["review_status"] == decision
    assert result.reviewed_by_id == recruiter.user_id
    assert result.review_notes == "Synthetic review"
    assert assignment.status == decision


def test_recruiter_review_is_one_time(monkeypatch):
    result = SimpleNamespace(review_status="QUALIFIED")
    monkeypatch.setattr(
        assessment_reviews,
        "get_recruiter_owned_result",
        lambda *_args: result,
    )

    with pytest.raises(BadRequestException, match="already been reviewed"):
        assessment_reviews.submit_assessment_review(
            702,
            AssessmentReviewRequest(decision="NOT_QUALIFIED"),
            SimpleNamespace(user_id=801),
            FakeSession(),
        )


def test_isolated_start_answer_submit_and_recruiter_review_flow(monkeypatch):
    question = {
        "id": 19,
        "question_text": "Synthetic assessment: choose the correct answer.",
        "category": "Synthetic",
        "difficulty": "Easy",
        "option_a": "Correct",
        "option_b": "Wrong",
        "option_c": "Wrong",
        "option_d": "Wrong",
        "marks": 2.0,
    }
    assignment = AssessmentAssignment(
        id=902,
        application_id=903,
        job_id=904,
        candidate_id=905,
        job_assessment_id=906,
        status="ASSIGNED",
        config_snapshot={"duration_minutes": 10, "passing_marks": 1.0, "qualification_rule": ">"},
        assigned_questions=[question],
        private_answer_key={"19": "A"},
    )
    recording = ProctoringSession(
        assignment_id=assignment.id,
        candidate_id=assignment.candidate_id,
        consent_given=True,
        camera_permission_granted=True,
        microphone_permission_granted=True,
        session_status="COMPLETED",
        recording_path="synthetic://isolated-assessment-recording",
        recording_completed_at=__import__("datetime").datetime.utcnow(),
    )
    candidate = SimpleNamespace(id=assignment.candidate_id)
    db = FakeSession(assignment, recording)
    monkeypatch.setattr(candidate_assessments, "get_owned_assignment", lambda *_args: assignment)
    monkeypatch.setattr(candidate_assessments, "require_proctoring_consent", lambda *_args: recording)

    started = start_or_resume_assessment(assignment.id, candidate, db)
    assert len(started["questions"]) == 1
    assert "correct_answer" not in started["questions"][0].model_dump()
    assert started["remaining_seconds"] > 0

    saved = save_candidate_answer(
        assignment.id,
        SaveAnswerRequest(question_id=19, selected_option="a", is_marked_for_review=True),
        candidate,
        db,
    )
    assert saved["message"] == "Answer saved successfully"
    assert assignment.attempt.saved_answers == {"19": "A"}
    assert assignment.attempt.marked_for_review == [19]

    submitted = submit_assessment(
        assignment.id,
        None,
        candidate,
        db,
    )
    assert submitted["message"] == "Your assessment has been submitted successfully."
    result = next(value for value in db.added if isinstance(value, CandidateAssessmentResult))
    assert result.obtained_marks == 2.0
    assert result.is_qualified is True  # 2 > passing_marks 1
    assert result.review_status == "PENDING_REVIEW"
    assert assignment.status == "PENDING_REVIEW"

    recruiter = SimpleNamespace(user_id=907)
    monkeypatch.setattr(assessment_reviews, "get_recruiter_owned_result", lambda *_args: result)
    reviewed = assessment_reviews.submit_assessment_review(
        result.id or 908,
        AssessmentReviewRequest(decision="QUALIFIED", review_notes="Synthetic review"),
        recruiter,
        db,
    )
    assert reviewed["review_status"] == "QUALIFIED"
    assert result.reviewed_by_id == recruiter.user_id
    assert assignment.status == "QUALIFIED"
