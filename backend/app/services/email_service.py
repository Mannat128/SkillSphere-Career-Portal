
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("SkillSphere.Email")


class EmailService:

    @classmethod
    def send_email(
        cls,
        to_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None,
        sensitive: bool = False,
    ) -> bool:
        """Send an email.

        Development mode logs the email and returns True.
        Production mode requires complete SMTP configuration.
        Unknown EMAIL_MODE values raise RuntimeError.
        """

        # Validate EMAIL_MODE safely
        raw_mode = getattr(settings, "EMAIL_MODE", None)

        if not isinstance(raw_mode, str) or not raw_mode.strip():
            raise RuntimeError(
                "EMAIL_MODE must be set to 'development' or 'production'."
            )

        mode = raw_mode.strip().lower()

        if mode not in ("development", "production"):
            raise RuntimeError(
                f"Unsupported EMAIL_MODE '{raw_mode}'. "
                "Use 'development' or 'production'."
            )

        # Validate all required production email settings
        if mode == "production":
            required_settings = {
                "SMTP_HOST": getattr(settings, "SMTP_HOST", None),
                "SMTP_PORT": getattr(settings, "SMTP_PORT", None),
                "SMTP_USER": getattr(settings, "SMTP_USER", None),
                "SMTP_PASSWORD": getattr(settings, "SMTP_PASSWORD", None),
                "EMAILS_FROM_EMAIL": getattr(
                    settings, "EMAILS_FROM_EMAIL", None
                ),
                "FRONTEND_BASE_URL": getattr(
                    settings, "FRONTEND_BASE_URL", None
                ),
            }

            missing = [
                name
                for name, value in required_settings.items()
                if value is None or (
                    isinstance(value, str) and not value.strip()
                )
            ]

            if missing:
                raise RuntimeError(
                    "EMAIL_MODE is 'production' but required settings "
                    f"are missing: {', '.join(missing)}"
                )

        # Development email simulator
        if mode == "development":
            logger.info("=" * 60)
            logger.info(f"[DEV EMAIL SIMULATOR] To: {to_email}")
            logger.info(f"Subject: {subject}")
            if not sensitive:
                logger.info(f"Body: {plain_content or html_content}")
            else:
                logger.info("Body omitted because it contains a one-time secret link.")
            logger.info("=" * 60)
            return True

        # Production SMTP delivery
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = (
                f"{settings.EMAILS_FROM_NAME} "
                f"<{settings.EMAILS_FROM_EMAIL}>"
            )
            msg["To"] = to_email

            if plain_content:
                msg.attach(MIMEText(plain_content, "plain"))

            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT
            ) as server:
                server.starttls()
                server.login(
                    settings.SMTP_USER,
                    settings.SMTP_PASSWORD
                )
                server.send_message(msg)

            logger.info(f"Email successfully delivered to {to_email}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to deliver email to {to_email}: {e}"
            )
            raise

    # ---------------------------------------------------------
    @classmethod
    def send_verification_email(
        cls,
        to_email: str,
        token: str
    ) -> bool:

        raw_base = getattr(settings, "FRONTEND_BASE_URL", None)

        if not isinstance(raw_base, str) or not raw_base.strip():
            raise RuntimeError(
                "FRONTEND_BASE_URL must be a non-empty string "
                "for email link generation."
            )

        base_url = raw_base.strip().rstrip("/")
        verify_url = f"{base_url}/verify-email?token={token}"

        subject = "SkillSphere – Verify Your Email Address"

        html = f"""
<div style="font-family: Arial, sans-serif; padding: 20px; color: #1e293b;">
<h2 style="color: #4f46e5;">Welcome to SkillSphere!</h2>
<p>Thank you for joining our Career &amp; Job Portal. Please verify your email address to activate all candidate and application features.</p>
<div style="margin: 25px 0;">
    <a href="{verify_url}" style="background-color: #8DB9F0; color: #0f172a; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold;">Verify Email Address</a>
</div>
<p>Verification Token: <code>{token}</code></p>
<p>If you did not create an account, you can safely ignore this email.</p>
</div>
"""

        plain = (
            f"Welcome to SkillSphere! Please verify your email "
            f"using this link: {verify_url}\nToken: {token}"
        )

        return cls.send_email(to_email, subject, html, plain)

    # ---------------------------------------------------------
    @classmethod
    def send_password_reset_email(
        cls,
        to_email: str,
        token: str
    ) -> bool:

        raw_base = getattr(settings, "FRONTEND_BASE_URL", None)

        if not isinstance(raw_base, str) or not raw_base.strip():
            raise RuntimeError(
                "FRONTEND_BASE_URL must be a non-empty string "
                "for email link generation."
            )

        base_url = raw_base.strip().rstrip("/")
        reset_url = f"{base_url}/reset-password?token={token}"

        subject = "SkillSphere – Password Reset Request"

        html = f"""
<div style="font-family: Arial, sans-serif; padding: 20px; color: #1e293b;">
<h2 style="color: #4f46e5;">Password Reset Request</h2>
<p>We received a request to reset your password on SkillSphere.</p>
<div style="margin: 25px 0;">
    <a href="{reset_url}" style="background-color: #F5B69E; color: #0f172a; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold;">Reset Password</a>
</div>
<p>Reset Token: <code>{token}</code></p>
<p>This link is valid for 24 hours.</p>
</div>
"""

        plain = (
            f"Reset your password with this link: "
            f"{reset_url}\nToken: {token}"
        )

        return cls.send_email(to_email, subject, html, plain, sensitive=True)

    # ---------------------------------------------------------
    @classmethod
    def send_job_alert_email(
        cls,
        to_email: str,
        candidate_name: str,
        job_title: str,
        company_name: str,
        location: str,
        employment_type: str,
        job_id: int,
    ) -> bool:
        """Send a formatted job alert email notification to matching candidates."""
        raw_base = getattr(settings, "FRONTEND_BASE_URL", None)
        base_url = (raw_base or "http://localhost:5173").strip().rstrip("/")
        job_url = f"{base_url}/candidate/jobs"

        subject = f"SkillSphere Job Alert: New opportunity for '{job_title}'"

        html = f"""
<div style="font-family: Arial, sans-serif; padding: 24px; color: #1e293b; max-width: 600px; line-height: 1.5;">
    <h2 style="color: #4f46e5; margin-bottom: 8px;">New Job Opportunity Matched!</h2>
    <p>Hello {candidate_name},</p>
    <p>A new position matching your career preferences has just been posted on SkillSphere:</p>
    <div style="background-color: #f8fafc; border-left: 4px solid #4f46e5; padding: 16px; margin: 20px 0; border-radius: 4px;">
        <h3 style="margin: 0 0 8px 0; color: #0f172a;">{job_title}</h3>
        <p style="margin: 4px 0; color: #475569;"><strong>Company:</strong> {company_name}</p>
        <p style="margin: 4px 0; color: #475569;"><strong>Location:</strong> {location}</p>
        <p style="margin: 4px 0; color: #475569;"><strong>Type:</strong> {employment_type}</p>
    </div>
    <div style="margin: 25px 0;">
        <a href="{job_url}" style="background-color: #4f46e5; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">View Opportunity</a>
    </div>
    <p style="font-size: 13px; color: #64748b;">You received this email because you subscribed to Job Alerts on SkillSphere. You can manage your alert preferences from your candidate profile.</p>
</div>
"""

        plain = (
            f"Hello {candidate_name},\n\n"
            f"A new job matching your preferences has been posted on SkillSphere:\n"
            f"Job: {job_title}\n"
            f"Company: {company_name}\n"
            f"Location: {location}\n"
            f"Type: {employment_type}\n\n"
            f"View details and apply: {job_url}\n"
        )

        return cls.send_email(to_email, subject, html, plain)
