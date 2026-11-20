"""
Email Delivery Adapter Service.

Provides unified interface for email dispatching with two distinct operating modes:
1. Simulation Mode (Default & Safe): No network connections are attempted.
   Messages are validated and logged as 'simulated'.
2. SMTP Mode (Optional): Requires explicit DRY_RUN=false in settings.
   Supports two distinct SMTP configurations:
   - Authenticated SMTP (Default for Gmail, SendGrid, Amazon SES):
     Requires SMTP_AUTH_REQUIRED=true, with non-empty username and password.
   - Unauthenticated Relay (Local development relays, MailHog, internal Postfix):
     Requires SMTP_AUTH_REQUIRED=false; skips credentials authentication.
"""

import smtplib
import logging
from email.message import EmailMessage
from typing import Dict, Any
from src.email_automation.config import settings


logger = logging.getLogger("email_automation.delivery")


class DeliveryConfigError(Exception):
    """Raised when live SMTP delivery configuration is incomplete or invalid."""
    pass


class DeliveryResult:
    """Encapsulates the outcome of an email dispatch attempt."""
    def __init__(self, success: bool, status: str, mode: str, message: str, error_detail: str = None):
        self.success = success
        self.status = status          # 'simulated', 'sent', or 'failed'
        self.mode = mode              # 'simulation' or 'smtp'
        self.message = message
        self.error_detail = error_detail

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "mode": self.mode,
            "message": self.message,
            "error_detail": self.error_detail
        }


class DeliveryAdapter:
    """Manages dispatching emails via simulation or authenticated/relay SMTP."""

    @classmethod
    def validate_smtp_configuration(cls) -> None:
        """
        Validates that required SMTP settings are populated when live delivery is enabled.
        Distinguishes between Authenticated SMTP (e.g. Gmail) and Unauthenticated Relay.
        """
        if not settings.SMTP_HOST:
            raise DeliveryConfigError("SMTP_HOST is not configured.")
        if not settings.SMTP_PORT:
            raise DeliveryConfigError("SMTP_PORT is not configured.")
        if not settings.SMTP_FROM_EMAIL:
            raise DeliveryConfigError("SMTP_FROM_EMAIL is not configured.")

        # Authenticated Mode (e.g. Gmail, Outlook, SendGrid)
        if settings.SMTP_AUTH_REQUIRED:
            if not settings.SMTP_USERNAME:
                raise DeliveryConfigError(
                    "SMTP authentication is enabled (SMTP_AUTH_REQUIRED=true), but SMTP_USERNAME is missing. "
                    "For authenticated services like Gmail, both username and password are required. "
                    "If using an unauthenticated local relay (e.g. MailHog), set SMTP_AUTH_REQUIRED=false."
                )
            if not settings.SMTP_PASSWORD:
                raise DeliveryConfigError(
                    "SMTP authentication is enabled (SMTP_AUTH_REQUIRED=true), but SMTP_PASSWORD is missing."
                )

    @classmethod
    def send_email(
        cls,
        to_email: str,
        to_name: str,
        subject: str,
        body: str
    ) -> DeliveryResult:
        """
        Sends an email using either Simulation mode or live SMTP based on DRY_RUN setting.
        """
        # =====================================================================
        # 1. SIMULATION MODE (Default Safety Guarantee)
        # =====================================================================
        if settings.DRY_RUN:
            logger.info(
                f"[SIMULATION] Sending email to '{to_name}' <{to_email}> | Subject: '{subject}'"
            )
            return DeliveryResult(
                success=True,
                status="simulated",
                mode="simulation",
                message=f"Email successfully simulated for {to_email}. No SMTP connection was made."
            )

        # =====================================================================
        # 2. LIVE SMTP MODE (Only when DRY_RUN=false)
        # =====================================================================
        mode_desc = "Authenticated SMTP" if settings.SMTP_AUTH_REQUIRED else "Unauthenticated Relay"
        logger.info(f"[SMTP LIVE: {mode_desc}] Dispatching email to <{to_email}> via {settings.SMTP_HOST}:{settings.SMTP_PORT}")
        
        try:
            cls.validate_smtp_configuration()
        except DeliveryConfigError as e:
            logger.error(f"[SMTP CONFIG ERROR] {str(e)}")
            return DeliveryResult(
                success=False,
                status="failed",
                mode="smtp",
                message="SMTP Configuration Error",
                error_detail=str(e)
            )

        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
            msg.set_content(body)

            # Transport connection
            if settings.SMTP_USE_SSL:
                server = smtplib.SMTP_SSL(
                    host=settings.SMTP_HOST,
                    port=settings.SMTP_PORT,
                    timeout=settings.SMTP_TIMEOUT_SECONDS
                )
            else:
                server = smtplib.SMTP(
                    host=settings.SMTP_HOST,
                    port=settings.SMTP_PORT,
                    timeout=settings.SMTP_TIMEOUT_SECONDS
                )
                if settings.SMTP_USE_TLS:
                    server.starttls()

            # Authenticate only if required
            if settings.SMTP_AUTH_REQUIRED:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)

            server.send_message(msg)
            server.quit()

            logger.info(f"[SMTP SUCCESS] Accepted by mail server for {to_email}")
            return DeliveryResult(
                success=True,
                status="sent",
                mode="smtp",
                message=f"Email accepted by SMTP server for {to_email}."
            )

        except smtplib.SMTPAuthenticationError:
            logger.error(f"[SMTP AUTH ERROR] Authentication failed for user {settings.SMTP_USERNAME}")
            return DeliveryResult(
                success=False,
                status="failed",
                mode="smtp",
                message="SMTP Authentication Failed",
                error_detail="Invalid username or password for SMTP server."
            )
        except smtplib.SMTPConnectError:
            logger.error(f"[SMTP CONNECT ERROR] Could not connect to {settings.SMTP_HOST}:{settings.SMTP_PORT}")
            return DeliveryResult(
                success=False,
                status="failed",
                mode="smtp",
                message="SMTP Connection Failed",
                error_detail=f"Unable to reach SMTP host at {settings.SMTP_HOST}:{settings.SMTP_PORT}"
            )
        except Exception as e:
            logger.error(f"[SMTP DISPATCH ERROR] Failed to send email to {to_email}: {str(e)}")
            return DeliveryResult(
                success=False,
                status="failed",
                mode="smtp",
                message="Email dispatch failed",
                error_detail=str(e)
            )
