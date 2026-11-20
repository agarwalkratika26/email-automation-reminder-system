"""
Application Configuration Module.

Reads settings from environment variables and provides centralized access
with sensible defaults. Ensures DRY_RUN mode is strictly enabled by default.
"""

from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


# Base directory pointing to the repository root
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    Application settings schema.
    Values can be overridden using a .env file or environment variables.
    """
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core Application Settings
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    FRONTEND_PORT: int = 3000

    # CORS Configuration: Strictly restricted to local dashboard origins
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]

    # Persistence
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'email_automation.db'}"

    # Delivery & Simulation Safety
    # When True (default), emails are simulated and NO outbound SMTP network connection is created.
    DRY_RUN: bool = Field(default=True, description="Strict safety default: simulated email delivery")

    # SMTP Configuration (Only evaluated when DRY_RUN is explicitly False)
    # Mode 1: Authenticated SMTP (Default for Gmail, SendGrid, etc.) -> Requires username & password.
    # Mode 2: Unauthenticated Relay (Internal/Local relays, e.g. MailHog, Postfix) -> Set SMTP_AUTH_REQUIRED=false.
    SMTP_AUTH_REQUIRED: bool = Field(default=True, description="Whether SMTP server mandates username/password authentication")
    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@example.com"
    SMTP_FROM_NAME: str = "Campaign Automation System"
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_TIMEOUT_SECONDS: int = 15

    # Worker / Scheduler Configuration
    WORKER_POLL_INTERVAL_SECONDS: int = 5
    BATCH_SEND_SIZE: int = 10
    STALE_JOB_TIMEOUT_SECONDS: int = Field(default=300, description="Grace period before abandoned processing jobs are recovered (5 min)")
    WORKER_LOCK_FILE: str = "email_automation_worker.lock"

    # Project Paths
    DATA_DIR: Path = BASE_DIR / "data"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    OUTPUTS_DIR: Path = BASE_DIR / "outputs"
    LOGS_DIR: Path = BASE_DIR / "logs"


# Singleton instance of settings
settings = Settings()

# Ensure required runtime output directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
