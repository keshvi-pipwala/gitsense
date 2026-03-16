from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "GitSense"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"

    # Database
    DATABASE_URL: str = "postgresql://gitsense:gitsense@localhost:5432/gitsense"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # GitHub
    GITHUB_TOKEN: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""

    # Anthropic (Claude)
    GOOGLE_API_KEY: str = ""

    # Slack
    SLACK_WEBHOOK_URL: Optional[str] = None
    SLACK_ENABLED: bool = False

    # Email (SMTP)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    EMAIL_ENABLED: bool = False

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "/data/chroma"

    # Notification thresholds
    NOTIFY_RISK_LEVELS: str = "HIGH,CRITICAL"
    STALE_PR_DAYS: int = 7
    HEALTH_CHECK_INTERVAL_HOURS: int = 6

    # Frontend URL (for links in notifications)
    FRONTEND_URL: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
