"""
Audit Reporting & CSV Export Service.

Generates downloadable, transparent CSV reports for:
1. Email Campaign Send Attempts & Statuses (with occurrence tracking)
2. Reminder Execution & Activity History (with notification audit trail)

Uses Pandas for structured CSV generation.
Ensures sensitive tokens or passwords are never present in reports.
"""

from typing import Optional
import pandas as pd
from sqlalchemy.orm import Session
from src.email_automation.storage.models import (
    RecipientSendRecord, Campaign, Reminder, ReminderNotificationRecord
)
from src.email_automation.config import settings


class ReportingService:
    """Generates structured CSV and dictionary reports for audit and compliance."""

    @staticmethod
    def export_campaign_send_records_csv(db: Session, campaign_id: Optional[int] = None) -> str:
        """
        Exports recipient send records to a CSV string.
        Includes campaign metadata, occurrence number, recipient info, timestamps, delivery mode, status, and errors.
        """
        query = db.query(RecipientSendRecord, Campaign).join(
            Campaign, RecipientSendRecord.campaign_id == Campaign.id
        )
        if campaign_id:
            query = query.filter(RecipientSendRecord.campaign_id == campaign_id)

        records = query.order_by(
            RecipientSendRecord.campaign_id.desc(),
            RecipientSendRecord.occurrence_number.desc(),
            RecipientSendRecord.id.desc()
        ).all()

        rows = []
        for send_rec, camp in records:
            rows.append({
                "record_id": send_rec.id,
                "campaign_id": camp.id,
                "campaign_title": camp.title,
                "occurrence_number": send_rec.occurrence_number,
                "template_name": camp.template_name,
                "recipient_name": send_rec.recipient_name,
                "recipient_email": send_rec.recipient_email,
                "subject": send_rec.rendered_subject,
                "status": send_rec.status,
                "delivery_mode": send_rec.delivery_mode,
                "attempt_count": send_rec.attempt_count,
                "last_attempt_at": send_rec.last_attempt_at.isoformat() if send_rec.last_attempt_at else "",
                "completed_at": send_rec.completed_at.isoformat() if send_rec.completed_at else "",
                "error_detail": send_rec.error_detail or ""
            })

        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame(columns=[
                "record_id", "campaign_id", "campaign_title", "occurrence_number", "template_name",
                "recipient_name", "recipient_email", "subject", "status",
                "delivery_mode", "attempt_count", "last_attempt_at", "completed_at", "error_detail"
            ])

        return df.to_csv(index=False)

    @staticmethod
    def export_reminders_csv(db: Session, team: Optional[str] = None) -> str:
        """
        Exports reminder activity and notification records to a CSV string.
        """
        query = db.query(Reminder)
        if team:
            query = query.filter(Reminder.team == team)

        reminders = query.order_by(Reminder.due_time.asc()).all()

        rows = []
        for r in reminders:
            notification_count = len(r.notifications) if r.notifications else 0
            rows.append({
                "reminder_id": r.id,
                "title": r.title,
                "description": r.description or "",
                "owner": r.owner,
                "team": r.team or "General",
                "priority": r.priority,
                "due_time": r.due_time.isoformat() if r.due_time else "",
                "recurrence": r.recurrence,
                "status": r.status,
                "last_notified_at": r.last_notified_at.isoformat() if r.last_notified_at else "",
                "notification_alerts_count": notification_count,
                "dismissed_at": r.dismissed_at.isoformat() if r.dismissed_at else "",
                "completed_at": r.completed_at.isoformat() if r.completed_at else "",
                "created_at": r.created_at.isoformat() if r.created_at else ""
            })

        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame(columns=[
                "reminder_id", "title", "description", "owner", "team",
                "priority", "due_time", "recurrence", "status",
                "last_notified_at", "notification_alerts_count", "dismissed_at", "completed_at", "created_at"
            ])

        return df.to_csv(index=False)

    @classmethod
    def save_sample_reports(cls, db: Session, target_dir = None) -> None:
        """Saves sample CSV audit reports to disk for demonstration and portfolio review."""
        out_dir = target_dir or (settings.OUTPUTS_DIR / "sample_reports")
        out_dir.mkdir(parents=True, exist_ok=True)
        
        campaigns_csv = cls.export_campaign_send_records_csv(db)
        (out_dir / "campaign_send_audit_report.csv").write_text(campaigns_csv, encoding="utf-8")
        
        reminders_csv = cls.export_reminders_csv(db)
        (out_dir / "reminders_activity_report.csv").write_text(reminders_csv, encoding="utf-8")
