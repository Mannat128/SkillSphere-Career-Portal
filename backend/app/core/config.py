import os
from typing import List, Literal, Optional
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

ENV_PATH = os.path.join(BASE_DIR, ".env")


class Settings(BaseSettings):

    APP_NAME: str = "SkillSphere – Career & Job Portal"
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Database configuration
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 3306
    DATABASE_NAME: str = "skillsphere_portal"
    DATABASE_USER: str
    DATABASE_PASSWORD: str

    # Security configuration
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Admin configuration
    ADMIN_NAME: str
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str

    # AI configuration
    AI_PROVIDER: Literal["google_gemini"] = "google_gemini"
    AI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # Default to a model verified in the current Gemini model list. Operators
    # can still pin a model through GEMINI_MODEL.
    GEMINI_MODEL: str = "gemini-3.8-flash"

    # Upload configuration
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "uploads")
    MAX_FILE_SIZE_MB: int = 10

    # OCR configuration
    TESSERACT_CMD: str = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )

    # Email configuration
    EMAIL_MODE: str = "development"  # "development" logs, "production" sends via SMTP
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    EMAILS_FROM_EMAIL: str = "no-reply@skillsphere.local"
    EMAILS_FROM_NAME: str = "SkillSphere Notifications"

    # Front‑end base URL used to build verification and password‑reset links
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    # Assessment recording storage (Cloudinary by default; local remains available)
    STORAGE_BACKEND: str = "cloudinary"
    CLOUDINARY_CLOUD_NAME: Optional[str] = None
    CLOUDINARY_API_KEY: Optional[str] = None
    CLOUDINARY_API_SECRET: Optional[str] = None

    # Legacy S3 settings remain available for existing s3:// recording references.
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET_NAME: Optional[str] = None
    AWS_S3_ENDPOINT_URL: Optional[str] = None

    # Recording lifecycle. Cleanup is opt-in so no existing recording is removed
    # until the operator reviews the data inventory and explicitly enables it.
    RECORDING_RETENTION_DAYS: int = 15
    ENABLE_RECORDING_CLEANUP: bool = False

    @property
    def DATABASE_URL(self) -> str:
        user = quote_plus(self.DATABASE_USER)
        password = quote_plus(self.DATABASE_PASSWORD)

        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}"
            f"/{self.DATABASE_NAME}?charset=utf8mb4"
        )

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
