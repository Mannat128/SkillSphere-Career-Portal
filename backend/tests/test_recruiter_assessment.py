import time
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

def create_recruiter_and_login():
    """Helper to create a recruiter and return auth headers."""
    uid = uuid.uuid4().hex[:8]
    email = f"recruiter_test_{uid}@example.com"
    reg = client.post(
        "/api/v1/auth/register-recruiter",
        json={
            "full_name": "Test Recruiter",
            "email": email,
            "password": "Password123!",
            "company_name": f"Acme Corp {uid}",
            "designation": "Hiring Lead"
        }
    )
    assert reg.status_code == 201

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, email

def create_candidate_and_login():
    """Helper to create a candidate and return auth headers."""
    uid = uuid.uuid4().hex[:8]
    email = f"candidate_assessment_{uid}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Candidate Tester",
            "email": email,
            "password": "Password123!"
        }
    )
    assert reg.status_code == 201

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, email

def test_question_bank_manual_add():
    """Option 1: Recruiter manually creates an MCQ."""
    headers, _ = create_recruiter_and_login()

    res = client.post(
        "/api/v1/question-bank",
        headers=headers,
        json={
            "question_text": "What is the primary function of SQLAlchemy Session?",
            "category": "Python",
            "difficulty": "Medium",
            "option_a": "To render HTML templates",
            "option_b": "To manage persistence operations for ORM-mapped objects",
            "option_c": "To encode JSON payloads",
            "option_d": "To encrypt passwords",
            "correct_answer": "B",
            "marks": 2.0,
            "explanation": "Session manages the conversation with the database and tracks changes."
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert data["correct_answer"] == "B"
    assert data["marks"] == 2.0
    assert data["category"] == "Python"

def test_question_bank_bulk_upload():
    """Option 2: Bulk upload CSV with validation."""
    headers, _ = create_recruiter_and_login()

    csv_content = (
        "question_text,category,difficulty,option_a,option_b,option_c,option_d,correct_answer,marks,explanation\n"
        "What does CSS stand for?,HTML/CSS,Easy,Cascading Style Sheets,Creative Style Sheets,Computer Style System,Colorful Style Sheets,A,1.0,Standard expansion\n"
        "What is the output of 2 + 2 in Python?,Python,Easy,3,4,5,22,B,1.0,Basic arithmetic\n"
    )

    files = {"file": ("questions.csv", csv_content, "text/csv")}
    upload_res = client.post("/api/v1/question-bank/bulk-upload", headers=headers, files=files)
    assert upload_res.status_code == 200
    resp_data = upload_res.json()
    assert resp_data["success"] is True
    assert resp_data["imported_count"] == 2

def test_question_bank_select_and_filter():
    """Option 3: Select from Question Bank with category and source filters."""
    headers, _ = create_recruiter_and_login()

    res = client.get("/api/v1/question-bank?category=Python", headers=headers)
    assert res.status_code == 200
    questions = res.json()
    assert len(questions) >= 1
    assert any(q["category"] == "Python" for q in questions)

def test_question_bank_bulk_upload_preview():
    """Option 2 Preview: Test bulk upload preview with row validation and duplicate detection."""
    headers, _ = create_recruiter_and_login()

    csv_content = (
        'question_text,category,difficulty,option_a,option_b,option_c,option_d,correct_answer,marks,explanation\n'
        '"What is the output of len([1, 2, 3]) in Python?",Python,Easy,1,2,3,4,C,1.0,Length function returns item count\n'
        'Invalid row lacking options,Python,Easy,A,B,,,A,1.0,\n'
    )

    files = {"file": ("preview_test.csv", csv_content, "text/csv")}
    preview_res = client.post("/api/v1/question-bank/bulk-upload/preview", headers=headers, files=files)
    assert preview_res.status_code == 200
    pdata = preview_res.json()
    assert pdata["total_rows"] == 2
    assert pdata["valid_count"] == 1
    assert pdata["error_count"] == 1
    assert pdata["valid"] is False
    assert len(pdata["errors"]) == 1
    assert pdata["errors"][0]["row"] == 3

def test_question_bank_job_only_versus_personal_bank():
    """Verify saving question only for current job vs saving to personal question bank."""
    rec_headers, _ = create_recruiter_and_login()

    # 1. Recruiter creates a job
    job_res = client.post(
        "/api/v1/recruiter/jobs",
        headers=rec_headers,
        json={
            "title": "Backend Specialist",
            "description": "Building and maintaining robust backend services with FastAPI and MySQL.",
            "location": "Remote",
            "employment_type": "Full-time",
            "experience_level": "Senior",
            "required_skills": ["FastAPI", "SQL"]
        }
    )
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]

    # 2. Add question ONLY for this job (save_to_bank = False)
    q_job_res = client.post(
        "/api/v1/question-bank",
        headers=rec_headers,
        json={
            "question_text": f"Exclusive job question for job {job_id}?",
            "category": "FastAPI",
            "difficulty": "Hard",
            "option_a": "Opt A",
            "option_b": "Opt B",
            "option_c": "Opt C",
            "option_d": "Opt D",
            "correct_answer": "A",
            "marks": 3.0,
            "save_to_bank": False,
            "job_id": job_id
        }
    )
    assert q_job_res.status_code == 201
    q_job_data = q_job_res.json()
    assert q_job_data["job_id"] == job_id

    # 3. Check general question bank (should NOT include this job-only question by default)
    bank_res = client.get("/api/v1/question-bank?include_job_specific=false", headers=rec_headers)
    assert bank_res.status_code == 200
    bank_ids = [q["id"] for q in bank_res.json()]
    assert q_job_data["id"] not in bank_ids

    # 4. Check questions for this job specifically
    job_q_res = client.get(f"/api/v1/question-bank?job_id={job_id}&source=job", headers=rec_headers)
    assert job_q_res.status_code == 200
    job_q_ids = [q["id"] for q in job_q_res.json()]
    assert q_job_data["id"] in job_q_ids

def test_first_round_assessment_end_to_end_flow():
    """
    End-to-end recruitment assessment test:
    1. Recruiter creates a job.
    2. Recruiter configures First Round MCQ Assessment with passing criteria (Rule '>').
    3. Candidate applies for the job.
    4. Recruiter changes application status to SHORTLISTED.
    5. Automatic assessment assignment created (idempotent on duplicate shortlist).
    6. Candidate starts assessment (timer synchronized, questions randomized, correct answers hidden).
    7. Candidate saves answers.
    8. Candidate submits assessment.
    9. Strict backend evaluation and immediate qualification verdict.
    10. Retakes blocked.
    11. Recruiter views result on recruiter dashboard.
    """
    rec_headers, _ = create_recruiter_and_login()
    cand_headers, _ = create_candidate_and_login()

    # 1. Recruiter posts job
    job_res = client.post(
        "/api/v1/recruiter/jobs",
        headers=rec_headers,
        json={
            "title": "Full Stack Software Engineer",
            "description": "Building modern scalable web apps with React and FastAPI.",
            "location": "Remote",
            "employment_type": "Full-time",
            "experience_level": "Mid-Level",
            "required_skills": ["Python", "React", "SQL"]
        }
    )
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]

    # 2. Recruiter configures First Round Assessment
    config_res = client.post(
        f"/api/v1/jobs/{job_id}/assessment",
        headers=rec_headers,
        json={
            "is_enabled": True,
            "title": "Round 1 Technical Screening",
            "instructions": "Answer all questions within the allocated time. No retakes permitted.",
            "total_questions": 3,
            "duration_minutes": 15,
            "total_marks": 5.0,
            "passing_marks": 3.0,
            "qualification_rule": ">=",
            "negative_marking": False,
            "negative_marks": 0.0,
            "categories": ["Python", "React", "SQL"],
            "selection_mode": "RANDOM"
        }
    )
    assert config_res.status_code == 200
    config_data = config_res.json()
    assert config_data["is_enabled"] is True
    assert config_data["passing_marks"] == 3.0
    assert config_data["qualification_rule"] == ">="

    # 3. Candidate applies for job
    apply_res = client.post(f"/api/v1/applications/jobs/{job_id}/apply", headers=cand_headers, json={})
    assert apply_res.status_code == 201
    app_id = apply_res.json()["id"]

    # 4. Recruiter shortlists candidate
    shortlist_res = client.put(
        f"/api/v1/recruiter/applicants/{app_id}/status",
        headers=rec_headers,
        json={"status": "SHORTLISTED", "notes": "Profile matches initial criteria"}
    )
    assert shortlist_res.status_code == 200

    # Test idempotency: shortlist again
    shortlist_res2 = client.put(
        f"/api/v1/recruiter/applicants/{app_id}/status",
        headers=rec_headers,
        json={"status": "SHORTLISTED", "notes": "Re-verifying shortlisting"}
    )
    assert shortlist_res2.status_code == 200

    # 5. Candidate checks assessment dashboard
    cand_assessments = client.get("/api/v1/candidate/first-round-assessments", headers=cand_headers)
    assert cand_assessments.status_code == 200
    assignments = cand_assessments.json()
    assert len(assignments) == 1
    assignment_id = assignments[0]["id"]
    assert assignments[0]["job_title"] == "Full Stack Software Engineer"
    assert assignments[0]["status"] == "PENDING"

    # 6. Candidate starts test
    start_res = client.post(
        f"/api/v1/candidate/first-round-assessments/{assignment_id}/start",
        headers=cand_headers
    )
    assert start_res.status_code == 200
    test_data = start_res.json()
    assert len(test_data["questions"]) == 3
    assert test_data["remaining_seconds"] > 0
    # Crucial security assertion: Correct answers MUST NOT be exposed!
    for q in test_data["questions"]:
        assert "correct_answer" not in q
        assert "correct_option" not in q

    q1_id = test_data["questions"][0]["id"]

    # 7. Candidate saves answer
    save_res = client.post(
        f"/api/v1/candidate/first-round-assessments/{assignment_id}/save-answer",
        headers=cand_headers,
        json={"question_id": q1_id, "selected_option": "B", "is_marked_for_review": True}
    )
    assert save_res.status_code == 200

    # 8. Candidate submits assessment
    submit_res = client.post(
        f"/api/v1/candidate/first-round-assessments/{assignment_id}/submit",
        headers=cand_headers,
        json={"final_answers": {str(q1_id): "B"}}
    )
    assert submit_res.status_code == 200
    result_data = submit_res.json()
    assert "is_qualified" in result_data
    assert "qualification_message" in result_data
    if result_data["is_qualified"]:
        assert "selected for the next round" in result_data["qualification_message"]
    else:
        assert "not qualified for the next round" in result_data["qualification_message"]

    # 9. Retake attempt blocked
    retake_res = client.post(
        f"/api/v1/candidate/first-round-assessments/{assignment_id}/start",
        headers=cand_headers
    )
    assert retake_res.status_code == 400

    # 10. Recruiter checks results dashboard
    rec_results_res = client.get(
        f"/api/v1/recruiter/assessments/results?job_id={job_id}",
        headers=rec_headers
    )
    assert rec_results_res.status_code == 200
    rec_results = rec_results_res.json()
    assert len(rec_results) >= 1
    assert rec_results[0]["job_id"] == job_id
    assert "obtained_marks" in rec_results[0]
