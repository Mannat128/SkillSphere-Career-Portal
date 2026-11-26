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
from app.models.proctoring import ProctoringSession
from app.core.exceptions import BadRequestException
from app.services.recording_retention import sync_recording_expiry


class AssessmentAssignmentService:

    @classmethod
    def get_eligible_questions(
        cls,
        db: Session,
        recruiter_id: Optional[int],
        categories: Optional[List[str]] = None,
        difficulty: Optional[str] = None,
        job_id: Optional[int] = None,
    ) -> List[QuestionBankQuestion]:
        """
        Fetch questions authorized for the recruiter:
        - Shared questions
        - Recruiter's own private general questions
        - Questions associated with this specific job
        """
        conditions = [
            QuestionBankQuestion.is_shared.is_(True),
            and_(
                QuestionBankQuestion.recruiter_id == recruiter_id,
                QuestionBankQuestion.job_id.is_(None),
            ),
        ]

        if job_id is not None:
            conditions.append(
                QuestionBankQuestion.job_id == job_id
            )

        query = db.query(QuestionBankQuestion).filter(
            or_(*conditions)
        )

        if categories:
            query = query.filter(
                QuestionBankQuestion.category.in_(categories)
            )

        if difficulty:
            query = query.filter(
                QuestionBankQuestion.difficulty == difficulty
            )

        return query.all()

    @classmethod
    def select_questions_for_candidate(
        cls,
        db: Session,
        job_assessment: JobAssessment,
        recruiter_id: Optional[int],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Select and shuffle the configured number of questions.
        Correct answers remain in the private answer key.
        """
        required_count = int(job_assessment.total_questions or 0)

        if required_count < 1:
            raise BadRequestException(
                "Assessment must contain at least one question."
            )

        job_id = job_assessment.job_id
        selected_questions: List[QuestionBankQuestion] = []

        if job_assessment.selection_mode == "SPECIFIC":
            requested_ids = job_assessment.selected_question_ids or []

            if len(set(requested_ids)) != len(requested_ids):
                raise BadRequestException(
                    "Selected question IDs must not contain duplicates."
                )

            if len(requested_ids) < required_count:
                raise BadRequestException(
                    f"Select at least {required_count} questions."
                )

            eligible_pool = cls.get_eligible_questions(
                db,
                recruiter_id=recruiter_id,
                categories=job_assessment.categories,
                job_id=job_id,
            )

            eligible_by_id = {
                question.id: question
                for question in eligible_pool
            }

            unauthorized_ids = [
                question_id
                for question_id in requested_ids
                if question_id not in eligible_by_id
            ]

            if unauthorized_ids:
                raise BadRequestException(
                    "One or more selected questions are unavailable "
                    "or you are not authorized to use them."
                )

            selected_pool = [
                eligible_by_id[question_id]
                for question_id in requested_ids
            ]

            selected_questions = random.sample(
                selected_pool,
                required_count,
            )

        elif job_assessment.difficulty_distribution:
            distribution = job_assessment.difficulty_distribution

            if sum(distribution.values()) != required_count:
                raise BadRequestException(
                    "Difficulty distribution must equal the configured "
                    "question count."
                )

            for difficulty, count in distribution.items():
                if count < 0:
                    raise BadRequestException(
                        "Difficulty counts cannot be negative."
                    )

                if count == 0:
                    continue

                pool = cls.get_eligible_questions(
                    db,
                    recruiter_id=recruiter_id,
                    categories=job_assessment.categories,
                    difficulty=difficulty,
                    job_id=job_id,
                )

                if len(pool) < count:
                    raise BadRequestException(
                        f"Insufficient '{difficulty}' questions available. "
                        f"Required: {count}, available: {len(pool)}."
                    )

                selected_questions.extend(
                    random.sample(pool, count)
                )

        else:
            pool = cls.get_eligible_questions(
                db,
                recruiter_id=recruiter_id,
                categories=job_assessment.categories,
                job_id=job_id,
            )

            if len(pool) < required_count:
                raise BadRequestException(
                    "Insufficient questions in Question Bank. "
                    f"Required: {required_count}, available: {len(pool)}."
                )

            selected_questions = random.sample(
                pool,
                required_count,
            )

        if len(selected_questions) != required_count:
            raise BadRequestException(
                "The selected question count does not match the "
                "assessment configuration."
            )

        random.shuffle(selected_questions)

        assigned_questions: List[Dict[str, Any]] = []
        private_answer_key: Dict[str, str] = {}

        for question in selected_questions:
            original_options = [
                ("A", question.option_a),
                ("B", question.option_b),
                ("C", question.option_c),
                ("D", question.option_d),
            ]

            correct_original_letter = (
                str(question.correct_answer).strip().upper()
            )

            if correct_original_letter not in {"A", "B", "C", "D"}:
                raise BadRequestException(
                    f"Question {question.id} has an invalid answer key."
                )

            shuffled_options = original_options.copy()
            random.shuffle(shuffled_options)

            new_options: Dict[str, str] = {}
            new_correct_letter = None

            for index, (original_letter, option_text) in enumerate(
                shuffled_options
            ):
                new_letter = "ABCD"[index]
                new_options[new_letter] = option_text

                if original_letter == correct_original_letter:
                    new_correct_letter = new_letter

            if new_correct_letter is None:
                raise BadRequestException(
                    f"Question {question.id} has an invalid answer key."
                )

            private_answer_key[str(question.id)] = new_correct_letter

            assigned_questions.append({
                "id": question.id,
                "question_text": question.question_text,
                "category": question.category,
                "difficulty": question.difficulty,
                "option_a": new_options["A"],
                "option_b": new_options["B"],
                "option_c": new_options["C"],
                "option_d": new_options["D"],
                "marks": question.marks,
            })

        return assigned_questions, private_answer_key

    @classmethod
    def assign_assessment_to_shortlisted_candidate(
        cls,
        db: Session,
        application: Application,
    ) -> Optional[AssessmentAssignment]:
        """
        Assign assessment when application is shortlisted.
        Avoid duplicate assignments.
        """
        job = application.job

        if (
            not job
            or not job.assessment_config
            or not job.assessment_config.is_enabled
        ):
            return None

        existing = (
            db.query(AssessmentAssignment)
            .filter(
                AssessmentAssignment.application_id == application.id
            )
            .first()
        )

        if existing:
            return existing

        config = job.assessment_config

        assigned_questions, private_key = (
            cls.select_questions_for_candidate(
                db,
                job_assessment=config,
                recruiter_id=job.recruiter_id,
            )
        )

        config_snapshot = {
            "title": config.title,
            "instructions": config.instructions,
            "total_questions": len(assigned_questions),
            "duration_minutes": config.duration_minutes,
            "total_marks": sum(
                question["marks"]
                for question in assigned_questions
            ),
            "passing_marks": config.passing_marks,
            "qualification_rule": ">",
            "negative_marking": config.negative_marking,
            "negative_marks": config.negative_marks,
            "available_from": config.available_from.isoformat() if config.available_from else None,
            "available_until": config.available_until.isoformat() if config.available_until else None,
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

        candidate_user = (
            application.candidate.user
            if application.candidate
            else None
        )

        if candidate_user:
            notification = Notification(
                user_id=candidate_user.id,
                title="Assessment Assigned!",
                message=(
                    f"Congratulations! You have been shortlisted for "
                    f"'{job.title}'. Your First Round Assessment "
                    f"'{config.title}' is now available on your dashboard."
                ),
                type="APPLICATION",
                link="/candidate/assessments",
            )
            db.add(notification)

        db.commit()
        db.refresh(assignment)

        return assignment

    @classmethod
    def evaluate_attempt(
        cls,
        db: Session,
        attempt: CandidateAssessmentAttempt,
    ) -> CandidateAssessmentResult:
        """
        Evaluate candidate answers, calculate marks, apply strict
        greater-than qualification, save result and update assignment.

        Manual review workflow:
        - Score is calculated internally.
        - Candidate cannot see score or automatic qualification.
        - Assignment remains PENDING_REVIEW.
        - Recruiter makes the final decision manually.
        """
        assignment = attempt.assignment

        if attempt.is_submitted:
            existing_result = (
                db.query(CandidateAssessmentResult)
                .filter(
                    CandidateAssessmentResult.assignment_id
                    == assignment.id
                )
                .first()
            )

            if existing_result:
                return existing_result

            raise BadRequestException(
                "This assessment attempt has already been submitted."
            )

        config = assignment.config_snapshot or {}
        private_keys = assignment.private_answer_key or {}
        saved_answers = attempt.saved_answers or {}

        question_marks = {
            str(question["id"]): float(question.get("marks", 1.0))
            for question in assignment.assigned_questions
        }

        correct_count = 0
        incorrect_count = 0
        unanswered_count = 0
        obtained_marks = 0.0
        total_marks = sum(question_marks.values())
        breakdown = []

        for question in assignment.assigned_questions:
            question_id = str(question["id"])
            correct_option = private_keys.get(question_id)
            user_option = saved_answers.get(question_id)

            question_marks_value = float(
                question.get("marks", 1.0)
            )

            if not user_option:
                unanswered_count += 1
                is_correct = False
                awarded = 0.0

            elif (
                correct_option
                and str(user_option).strip().upper()
                == str(correct_option).strip().upper()
            ):
                correct_count += 1
                is_correct = True
                awarded = question_marks_value
                obtained_marks += question_marks_value

            else:
                incorrect_count += 1
                is_correct = False

                deduction = (
                    float(config.get("negative_marks", 0.0) or 0.0)
                    if config.get("negative_marking")
                    else 0.0
                )

                awarded = -deduction
                obtained_marks -= deduction

            breakdown.append({
                "question_id": question["id"],
                "question_text": question["question_text"],
                "selected_option": user_option,
                "is_correct": is_correct,
                "marks_awarded": awarded,
            })

        obtained_marks = max(0.0, round(obtained_marks, 2))

        percentage = (
            round(
                (obtained_marks / float(total_marks)) * 100.0,
                1,
            )
            if total_marks > 0
            else 0.0
        )

        passing_marks = float(config.get("passing_marks", 0.0))
        qualification_rule = ">"

        # Strict rule: equal marks do NOT qualify.
        # This is calculated internally for the recruiter scorecard.
        is_qualified = obtained_marks > passing_marks

        qualification_message = (
            "Candidate qualified for the next round."
            if is_qualified
            else "Candidate did not qualify for the next round."
        )

        now = datetime.datetime.utcnow()

        attempt.is_submitted = True
        attempt.submitted_at = now

        # Recording upload is required before candidate submission in the
        # current workflow. Start its retention window from this immutable
        # assessment-completion timestamp, not from the earlier upload time.
        proctoring_session = (
            db.query(ProctoringSession)
            .filter(ProctoringSession.assignment_id == assignment.id)
            .first()
        )
        if proctoring_session:
            sync_recording_expiry(proctoring_session, attempt)

        attempt.time_taken_seconds = (
            int((now - attempt.started_at).total_seconds())
            if attempt.started_at
            else 0
        )

        # -------------------------------------------------
        # MANUAL REVIEW WORKFLOW
        # -------------------------------------------------

        # Candidate status is Pending Review regardless of
        # the internally calculated score.
        assignment.status = "PENDING_REVIEW"
        assignment.updated_at = now

        result = (
            db.query(CandidateAssessmentResult)
            .filter(
                CandidateAssessmentResult.assignment_id
                == assignment.id
            )
            .first()
        )

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
                qualification_rule=qualification_rule,
                is_qualified=is_qualified,
                qualification_message=qualification_message,
                question_breakdown=breakdown,
                review_status="PENDING_REVIEW",
                evaluated_at=now,
            )
            db.add(result)

        else:
            result.obtained_marks = obtained_marks
            result.total_marks = total_marks
            result.percentage = percentage
            result.correct_count = correct_count
            result.incorrect_count = incorrect_count
            result.unanswered_count = unanswered_count
            result.passing_marks = passing_marks
            result.qualification_rule = qualification_rule
            result.is_qualified = is_qualified
            result.qualification_message = qualification_message
            result.question_breakdown = breakdown

            result.review_status = "PENDING_REVIEW"
            result.reviewed_by_id = None
            result.reviewed_at = None
            result.review_notes = None

            result.evaluated_at = now

        # -------------------------------------------------
        # CANDIDATE NOTIFICATION
        # -------------------------------------------------

        # Candidate receives neutral submission notification.
        # No score or qualification verdict is disclosed.
        candidate_user = (
            assignment.candidate.user
            if assignment.candidate
            else None
        )

        if candidate_user:
            candidate_notification = Notification(
                user_id=candidate_user.id,
                title="Assessment Submitted",
                message=(
                    f"Your assessment for '{config.get('title')}' "
                    "has been submitted successfully and is pending "
                    "recruiter review. You will be notified once the "
                    "recruiter makes a decision."
                ),
                type="APPLICATION",
                link="/candidate/assessments",
            )
            db.add(candidate_notification)

        # -------------------------------------------------
        # RECRUITER NOTIFICATION
        # -------------------------------------------------

        # Internal score and automated threshold result are
        # visible only to the recruiter.
        job = assignment.job

        if job and job.recruiter and job.recruiter.user:
            automatic_status = (
                "meets the score threshold"
                if is_qualified
                else "does not meet the score threshold"
            )

            recruiter_notification = Notification(
                user_id=job.recruiter.user.id,
                title="Assessment Awaiting Review",
                message=(
                    f"{candidate_user.full_name if candidate_user else 'A candidate'} "
                    f"completed the assessment for '{job.title}'. "
                    f"Score: {obtained_marks}/{total_marks}. "
                    f"The candidate {automatic_status}. "
                    "Please review the scorecard and make the final decision."
                ),
                type="APPLICATION",
                link="/recruiter/assessments/results",
            )
            db.add(recruiter_notification)

        db.commit()
        db.refresh(result)

        return result
