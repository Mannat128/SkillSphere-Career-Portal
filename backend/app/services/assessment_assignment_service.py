import random
import datetime
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models.recruiter_assessment import (
    QuestionBankQuestion,
    JobAssessment,
    AssessmentAssignment,
    CandidateAssessmentAttempt,
    CandidateAssessmentResult,
)
from app.models.job import Job
from app.models.application import Application
from app.models.notification import Notification
from app.core.exceptions import BadRequestException, NotFoundException

class AssessmentAssignmentService:
    @classmethod
    def get_eligible_questions(
        cls,
        db: Session,
        recruiter_id: Optional[int],
        categories: Optional[List[str]] = None,
        difficulty: Optional[str] = None,
        job_id: Optional[int] = None
    ) -> List[QuestionBankQuestion]:
        """
        Fetch questions that this recruiter is authorized to use:
        - Their own private questions (`recruiter_id == recruiter_id`)
        - Admin-approved shared questions (`is_shared == True`)
        - Questions created specifically for this job (`job_id == job_id`)
        """
        conditions = [
            QuestionBankQuestion.is_shared == True,
            and_(
                QuestionBankQuestion.recruiter_id == recruiter_id,
                QuestionBankQuestion.job_id.is_(None)
            )
        ]
        if job_id:
            conditions.append(QuestionBankQuestion.job_id == job_id)

        query = db.query(QuestionBankQuestion).filter(or_(*conditions))

        if categories and len(categories) > 0:
            query = query.filter(QuestionBankQuestion.category.in_(categories))
        if difficulty:
            query = query.filter(QuestionBankQuestion.difficulty == difficulty)

        return query.all()

    @classmethod
    def select_questions_for_candidate(
        cls,
        db: Session,
        job_assessment: JobAssessment,
        recruiter_id: Optional[int]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Selects and shuffles questions for candidate test assignment.
        Returns:
            - assigned_questions: list of question dicts without correct answers
            - private_answer_key: {str(q_id): correct_option_letter}
        """
        selected_questions: List[QuestionBankQuestion] = []
        job_id = job_assessment.job_id

        if job_assessment.selection_mode == "SPECIFIC" and job_assessment.selected_question_ids:
            # Explicit recruiter picked questions
            selected_questions = db.query(QuestionBankQuestion).filter(
                QuestionBankQuestion.id.in_(job_assessment.selected_question_ids)
            ).all()
        elif job_assessment.difficulty_distribution:
            # Difficulty distribution (e.g. {"Easy": 3, "Medium": 5, "Hard": 2})
            for diff, count in job_assessment.difficulty_distribution.items():
                if count <= 0:
                    continue
                pool = cls.get_eligible_questions(
                    db,
                    recruiter_id=recruiter_id,
                    categories=job_assessment.categories,
                    difficulty=diff,
                    job_id=job_id
                )
                if len(pool) < count:
                    raise BadRequestException(
                        f"Insufficient '{diff}' questions available. Required: {count}, available: {len(pool)}."
                    )
                sampled = random.sample(pool, count)
                selected_questions.extend(sampled)
        else:
            # Generic category random selection
            pool = cls.get_eligible_questions(
                db,
                recruiter_id=recruiter_id,
                categories=job_assessment.categories,
                job_id=job_id
            )
            req_count = job_assessment.total_questions
            if len(pool) < req_count:
                raise BadRequestException(
                    f"Insufficient questions in Question Bank. Required: {req_count}, available: {len(pool)}."
                )
            selected_questions = random.sample(pool, req_count)

        # Shuffle overall question order
        random.shuffle(selected_questions)

        assigned_questions = []
        private_answer_key: Dict[str, str] = {}

        for q in selected_questions:
            # Shuffle answer options while tracking the correct answer
            original_options = [
                ("A", q.option_a),
                ("B", q.option_b),
                ("C", q.option_c),
                ("D", q.option_d)
            ]
            correct_text = dict(original_options)[q.correct_answer]

            # Shuffle the option texts
            option_texts = [q.option_a, q.option_b, q.option_c, q.option_d]
            random.shuffle(option_texts)

            # Assign new letters A, B, C, D
            new_options = {
                "A": option_texts[0],
                "B": option_texts[1],
                "C": option_texts[2],
                "D": option_texts[3]
            }

            # Find which letter holds the correct text
            new_correct_letter = "A"
            for letter, text in new_options.items():
                if text == correct_text:
                    new_correct_letter = letter
                    break

            private_answer_key[str(q.id)] = new_correct_letter

            assigned_questions.append({
                "id": q.id,
                "question_text": q.question_text,
                "category": q.category,
                "difficulty": q.difficulty,
                "option_a": new_options["A"],
                "option_b": new_options["B"],
                "option_c": new_options["C"],
                "option_d": new_options["D"],
                "marks": q.marks,
            })

        return assigned_questions, private_answer_key

    @classmethod
    def assign_assessment_to_shortlisted_candidate(
        cls,
        db: Session,
        application: Application
    ) -> Optional[AssessmentAssignment]:
        """
        Triggered when application is SHORTLISTED.
        Creates assignment if job has enabled assessment, avoiding duplicates.
        """
        job = application.job
        if not job or not job.assessment_config or not job.assessment_config.is_enabled:
            return None

        # Check existing assignment
        existing = db.query(AssessmentAssignment).filter(
            AssessmentAssignment.application_id == application.id
        ).first()
        if existing:
            return existing

        config = job.assessment_config

        # Select questions
        assigned_questions, private_key = cls.select_questions_for_candidate(
            db,
            job_assessment=config,
            recruiter_id=job.recruiter_id
        )

        config_snapshot = {
            "title": config.title,
            "instructions": config.instructions,
            "total_questions": len(assigned_questions),
            "duration_minutes": config.duration_minutes,
            "total_marks": sum(q["marks"] for q in assigned_questions),
            "passing_marks": config.passing_marks,
            "qualification_rule": config.qualification_rule,
            "negative_marking": config.negative_marking,
            "negative_marks": config.negative_marks,
        }

        assignment = AssessmentAssignment(
            application_id=application.id,
            job_id=job.id,
            candidate_id=application.candidate_id,
            job_assessment_id=config.id,
            status="PENDING",
            config_snapshot=config_snapshot,
            assigned_questions=assigned_questions,
            private_answer_key=private_key,
        )
        db.add(assignment)

        # Notify candidate
        cand_user = application.candidate.user if application.candidate else None
        if cand_user:
            notif = Notification(
                user_id=cand_user.id,
                title="Assessment Assigned!",
                message=f"Congratulations! You have been shortlisted for '{job.title}'. Your First Round Assessment '{config.title}' is now available on your dashboard.",
                type="APPLICATION",
                link="/candidate/assessments"
            )
            db.add(notif)

        db.commit()
        db.refresh(assignment)
        return assignment

    @classmethod
    def evaluate_attempt(
        cls,
        db: Session,
        attempt: CandidateAssessmentAttempt
    ) -> CandidateAssessmentResult:
        """
        Strict backend evaluation:
        1. Compare candidate's saved answers against private_answer_key.
        2. Calculate marks with negative marking if enabled.
        3. Apply recruiter qualification rule (> or >=).
        4. Save final result and update assignment status.
        """
        assignment = attempt.assignment
        config = assignment.config_snapshot
        private_keys: Dict[str, str] = assignment.private_answer_key
        saved_answers: Dict[str, str] = attempt.saved_answers or {}

        # Map question id to marks
        q_marks_map = {str(q["id"]): q.get("marks", 1.0) for q in assignment.assigned_questions}

        correct_count = 0
        incorrect_count = 0
        unanswered_count = 0
        obtained_marks = 0.0
        total_marks = sum(q_marks_map.values())
        breakdown = []

        for q in assignment.assigned_questions:
            q_id_str = str(q["id"])
            correct_opt = private_keys.get(q_id_str)
            user_opt = saved_answers.get(q_id_str)
            q_marks = q.get("marks", 1.0)

            if not user_opt:
                unanswered_count += 1
                is_correct = False
                awarded = 0.0
            elif user_opt.strip().upper() == correct_opt.strip().upper():
                correct_count += 1
                is_correct = True
                awarded = q_marks
                obtained_marks += q_marks
            else:
                incorrect_count += 1
                is_correct = False
                deduction = config.get("negative_marks", 0.0) if config.get("negative_marking") else 0.0
                awarded = -deduction
                obtained_marks -= deduction

            breakdown.append({
                "question_id": q["id"],
                "question_text": q["question_text"],
                "selected_option": user_opt,
                "is_correct": is_correct,
                "marks_awarded": awarded,
            })

        # Do not allow obtained marks to drop below 0
        obtained_marks = max(0.0, round(obtained_marks, 2))
        percentage = round((obtained_marks / float(total_marks)) * 100.0, 1) if total_marks > 0 else 0.0
        passing_marks = float(config.get("passing_marks", 0.0))
        rule = config.get("qualification_rule", ">")

        # EXACT Qualification rule comparison
        if rule == ">=":
            is_qualified = (obtained_marks >= passing_marks)
        else: # '>'
            is_qualified = (obtained_marks > passing_marks)

        qualification_message = (
            "Congratulations! You have been selected for the next round."
            if is_qualified
            else "Thank you for completing the assessment. Unfortunately, you have not qualified for the next round."
        )

        now = datetime.datetime.utcnow()
        attempt.is_submitted = True
        attempt.submitted_at = now
        time_taken = int((now - attempt.started_at).total_seconds()) if attempt.started_at else 0
        attempt.time_taken_seconds = time_taken

        # Update assignment status
        assignment.status = "QUALIFIED" if is_qualified else "NOT_QUALIFIED"
        assignment.updated_at = now

        result = db.query(CandidateAssessmentResult).filter(
            CandidateAssessmentResult.assignment_id == assignment.id
        ).first()

        if not result:
            result = CandidateAssessmentResult(
                attempt_id=attempt.id,
                assignment_id=assignment.id,
                candidate_id=assignment.candidate_id,
                job_id=assignment.job_id,
                obtained_marks=obtained_marks,
                total_marks=total_marks,
                percentage=percentage,
                correct_count=correct_count,
                incorrect_count=incorrect_count,
                unanswered_count=unanswered_count,
                passing_marks=passing_marks,
                qualification_rule=rule,
                is_qualified=is_qualified,
                qualification_message=qualification_message,
                question_breakdown=breakdown,
                evaluated_at=now
            )
            db.add(result)
        else:
            result.obtained_marks = obtained_marks
            result.total_marks = total_marks
            result.percentage = percentage
            result.correct_count = correct_count
            result.incorrect_count = incorrect_count
            result.unanswered_count = unanswered_count
            result.is_qualified = is_qualified
            result.qualification_message = qualification_message
            result.question_breakdown = breakdown
            result.evaluated_at = now

        # Notify Candidate of completion
        cand_user = assignment.candidate.user if assignment.candidate else None
        if cand_user:
            notif = Notification(
                user_id=cand_user.id,
                title="Assessment Result Available",
                message=f"Your result for '{config.get('title')}' is now available. {qualification_message}",
                type="APPLICATION",
                link=f"/candidate/assessments/{assignment.id}/result"
            )
            db.add(notif)

        # Notify Recruiter of test submission
        job = assignment.job
        if job and job.recruiter and job.recruiter.user:
            rec_status_text = "QUALIFIED" if is_qualified else "DID NOT QUALIFY"
            notif = Notification(
                user_id=job.recruiter.user.id,
                title="Assessment Completed",
                message=f"{cand_user.full_name if cand_user else 'A candidate'} completed the assessment for '{job.title}' and {rec_status_text} (Score: {obtained_marks}/{total_marks}).",
                type="APPLICATION",
                link=f"/recruiter/assessments/results"
            )
            db.add(notif)

        db.commit()
        db.refresh(result)
        return result
