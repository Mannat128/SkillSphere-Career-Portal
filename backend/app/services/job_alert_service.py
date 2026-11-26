import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.job import Job, JobStatusEnum
from app.models.candidate import Candidate, JobAlertPreference
from app.models.notification import Notification, NotificationPreference
from app.services.email_service import EmailService

logger = logging.getLogger("SkillSphere.JobAlert")


class JobAlertService:
    """Service to match newly published jobs with candidate alert preferences and dispatch notifications."""

    @classmethod
    def match_job_against_preference(cls, job: Job, pref: JobAlertPreference) -> bool:
        """
        Check if a job matches a candidate's JobAlertPreference.
        All specified filter criteria must match (conjunction).
        """
        if not pref.is_active:
            return False

        # 1. Match Keywords in Job Title, Description, or Required Skills
        if pref.keywords and pref.keywords.strip():
            keywords = [k.strip().lower() for k in pref.keywords.replace(",", " ").split() if k.strip()]
            if keywords:
                title_lower = (job.title or "").lower()
                desc_lower = (job.description or "").lower()
                skill_names = [js.skill.name.lower() for js in (job.required_skills or []) if js.skill]

                # Check if any keyword matches title, description, or skills
                keyword_matched = False
                for kw in keywords:
                    if kw in title_lower or kw in desc_lower or any(kw in sk for sk in skill_names):
                        keyword_matched = True
                        break
                if not keyword_matched:
                    return False

        # 2. Match Location
        if pref.preferred_location and pref.preferred_location.strip():
            pref_loc = pref.preferred_location.strip().lower()
            job_loc = (job.location or "").lower()
            # If candidate wants Remote, job must be remote; if candidate wants a specific location, match substring or remote
            if pref_loc == "remote":
                if "remote" not in job_loc:
                    return False
            else:
                if pref_loc not in job_loc and "remote" not in job_loc:
                    return False

        # 3. Match Job / Employment Type (e.g., Full-time, Part-time, Contract, Remote)
        if pref.preferred_job_type and pref.preferred_job_type.strip():
            pref_type = pref.preferred_job_type.strip().lower()
            job_type = (job.employment_type or "").lower()
            if pref_type not in job_type:
                return False

        # 4. Match Experience Level (e.g., Entry, Mid-Level, Senior, Lead)
        if pref.experience_level and pref.experience_level.strip():
            pref_exp = pref.experience_level.strip().lower()
            job_exp = (job.experience_level or "").lower()
            if pref_exp not in job_exp:
                return False

        return True

    @classmethod
    def find_matching_candidates(cls, db: Session, job: Job) -> List[Candidate]:
        """Find all candidates with active job alert preferences matching the given job."""
        active_prefs = (
            db.query(JobAlertPreference)
            .filter(JobAlertPreference.is_active == True)
            .all()
        )

        matched_candidates = []
        for pref in active_prefs:
            candidate = pref.candidate
            if not candidate or not candidate.user or not candidate.user.is_active:
                continue

            if cls.match_job_against_preference(job, pref):
                matched_candidates.append(candidate)

        return matched_candidates

    @classmethod
    def dispatch_job_alerts(cls, db: Session, job: Job) -> Dict[str, Any]:
        """
        Dispatches in-app notifications and emails for a newly published job.
        Ensures idempotent behavior by preventing duplicate notifications for the same job.
        Errors during dispatch are caught and logged without failing caller execution.
        """
        if not job or job.status != JobStatusEnum.PUBLISHED:
            return {"dispatched": 0, "emails_sent": 0, "in_app_sent": 0}

        results = {
            "dispatched": 0,
            "emails_sent": 0,
            "in_app_sent": 0,
            "errors": []
        }

        try:
            candidates = cls.find_matching_candidates(db, job)
            job_link = f"/candidate/jobs"

            for candidate in candidates:
                user = candidate.user
                if not user:
                    continue

                # Deduplication check: Check if user already received an alert for this job
                alert_title = f"New Job Alert: {job.title}"
                already_notified = db.query(Notification).filter(
                    Notification.user_id == user.id,
                    Notification.type == "JOB_ALERT",
                    Notification.message.like(f"%{job.title}%")
                ).first()

                if already_notified:
                    logger.info(f"Skipping duplicate alert for user {user.id} on job {job.id}")
                    continue

                # Check user notification preferences if set
                notif_pref = user.notification_preferences

                in_app_enabled = notif_pref.in_app_notifications if notif_pref else True
                email_enabled = notif_pref.email_job_alerts if notif_pref else True

                # 1. Dispatch In-App Notification
                if in_app_enabled:
                    company_name = job.company.name if (job.company and job.company.name) else "SkillSphere Partner"
                    notification = Notification(
                        user_id=user.id,
                        title=alert_title,
                        message=(
                            f"A new job '{job.title}' at {company_name} ({job.location}) "
                            f"matches your career alert preferences."
                        ),
                        type="JOB_ALERT",
                        link=job_link,
                    )
                    db.add(notification)
                    results["in_app_sent"] += 1

                # 2. Dispatch Email Alert
                if email_enabled and user.email:
                    company_name = job.company.name if (job.company and job.company.name) else "SkillSphere Partner"
                    try:
                        EmailService.send_job_alert_email(
                            to_email=user.email,
                            candidate_name=user.full_name or "Candidate",
                            job_title=job.title,
                            company_name=company_name,
                            location=job.location,
                            employment_type=job.employment_type or "Full-time",
                            job_id=job.id,
                        )
                        results["emails_sent"] += 1
                    except Exception as email_err:
                        logger.warning(f"Failed to send job alert email to {user.email}: {email_err}")
                        results["errors"].append(str(email_err))

                results["dispatched"] += 1

            db.commit()

        except Exception as e:
            logger.exception(f"Error during job alert dispatching for job {job.id}: {e}")
            results["errors"].append(str(e))
            db.rollback()

        return results
