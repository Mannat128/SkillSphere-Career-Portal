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
        plain_content: Optional[str] = None
    ) -> bool:
        """
        Send system email or log cleanly in development mode.
        """
        # If in development mode or SMTP is not fully configured, log the email content
        if settings.EMAIL_MODE.lower() == "development" or not settings.SMTP_HOST:
            logger.info("=" * 60)
            logger.info(f"📧 [DEV EMAIL SIMULATOR] To: {to_email}")
            logger.info(f"📧 Subject: {subject}")
            logger.info(f"📧 Body: {plain_content or html_content}")
            logger.info("=" * 60)
            return True

        # Production SMTP delivery
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
            msg["To"] = to_email

            if plain_content:
                msg.attach(MIMEText(plain_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)

            logger.info(f"Email successfully delivered to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to deliver email to {to_email}: {e}")
            return False

    @classmethod
    def send_verification_email(cls, to_email: str, token: str) -> bool:
        verify_url = f"http://localhost:5173/verify-email?token={token}"
        subject = "SkillSphere – Verify Your Email Address"
        html = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #1e293b;">
            <h2 style="color: #4f46e5;">Welcome to SkillSphere!</h2>
            <p>Thank you for joining our Career & Job Portal. Please verify your email address to activate all candidate and application features.</p>
            <div style="margin: 25px 0;">
                <a href="{verify_url}" style="background-color: #8DB9F0; color: #0f172a; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                    Verify Email Address
                </a>
            </div>
            <p>Verification Token: <code>{token}</code></p>
            <p>If you did not create an account, you can safely ignore this email.</p>
        </div>
        """
        plain = f"Welcome to SkillSphere! Please verify your email using this link: {verify_url}\nToken: {token}"
        return cls.send_email(to_email, subject, html, plain)

    @classmethod
    def send_password_reset_email(cls, to_email: str, token: str) -> bool:
        reset_url = f"http://localhost:5173/reset-password?token={token}"
        subject = "SkillSphere – Password Reset Request"
        html = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #1e293b;">
            <h2 style="color: #4f46e5;">Password Reset Request</h2>
            <p>We received a request to reset your password on SkillSphere.</p>
            <div style="margin: 25px 0;">
                <a href="{reset_url}" style="background-color: #F5B69E; color: #0f172a; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                    Reset Password
                </a>
            </div>
            <p>Reset Token: <code>{token}</code></p>
            <p>This link is valid for 24 hours.</p>
        </div>
        """
        plain = f"Reset your password with this link: {reset_url}\nToken: {token}"
        return cls.send_email(to_email, subject, html, plain)
