"""
Relational Data Models.

Defines persistence schemas for Contacts, Campaigns, Recipient Send Records,
Reminders, and Reminder Notification Records using SQLAlchemy.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from src.email_automation.storage.database import Base


def get_utc_now():
    """Returns the current UTC-aware datetime timestamp."""
    return datetime.now(timezone.utc)


class Contact(Base):
    """
    Individual contact record imported from CSV or managed through the UI.
    Email is indexed and enforced unique.
    """
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    company = Column(String(255), nullable=True, default="")
    role = Column(String(255), nullable=True, default="")
    department = Column(String(255), nullable=True, default="")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationships
    send_records = relationship("RecipientSendRecord", back_populates="contact", cascade="all, delete-orphan")


class Campaign(Base):
    """
    Email campaign defining template, scheduling, recurrence, and target recipients.
    Tracks current_run_number to support historical occurrences.
    """
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    template_name = Column(String(255), nullable=False)
    custom_subject = Column(String(255), nullable=True)  # Optional override of template subject
    custom_body = Column(Text, nullable=True)             # Optional override of template body
    
    # Recurrence: one-off, daily, weekly, monthly
    recurrence = Column(String(50), default="one-off", nullable=False)
    current_run_number = Column(Integer, default=1, nullable=False)
    
    # Scheduled timestamps (UTC-aware)
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Status: pending, running, completed, paused, cancelled
    status = Column(String(50), default="pending", nullable=False, index=True)
    
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationships
    send_records = relationship("RecipientSendRecord", back_populates="campaign", cascade="all, delete-orphan")


class RecipientSendRecord(Base):
    """
    Granular, per-recipient audit and status log for each campaign execution attempt.
    Tracks occurrence_number to preserve complete history across recurring runs.
    Status transitions: queued -> processing -> simulated | sent | failed
    """
    __tablename__ = "recipient_send_records"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False, index=True)
    occurrence_number = Column(Integer, default=1, nullable=False, index=True)
    
    # Snapshot at send time (in case contact or campaign changes later)
    recipient_email = Column(String(255), nullable=False, index=True)
    recipient_name = Column(String(255), nullable=False)
    rendered_subject = Column(String(255), nullable=False)
    rendered_body = Column(Text, nullable=False)
    
    # Status: queued, processing, simulated, sent, failed, cancelled
    status = Column(String(50), default="queued", nullable=False, index=True)
    delivery_mode = Column(String(50), default="simulation", nullable=False) # simulation or smtp
    
    # Audit timestamps
    attempt_count = Column(Integer, default=0, nullable=False)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Error message if delivery failed
    error_detail = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationships
    campaign = relationship("Campaign", back_populates="send_records")
    contact = relationship("Contact", back_populates="send_records")

    __table_args__ = (
        Index("idx_campaign_occurrence_status", "campaign_id", "occurrence_number", "status"),
    )


class Reminder(Base):
    """
    Personal and team reminders with recurrence, assignment, and active status tracking.
    Status: pending, due, completed, dismissed, cancelled
    """
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True, default="")
    
    # Scheduled due time (UTC-aware)
    due_time = Column(DateTime(timezone=True), nullable=False, index=True)
    
    owner = Column(String(255), nullable=False)        # Primary assignee / creator
    team = Column(String(255), nullable=True, default="General")
    priority = Column(String(50), default="medium", nullable=False) # low, medium, high, urgent
    
    # Recurrence: one-off, daily, weekly, monthly
    recurrence = Column(String(50), default="one-off", nullable=False)
    
    # Status: pending, due, completed, dismissed, cancelled
    status = Column(String(50), default="pending", nullable=False, index=True)
    
    last_notified_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationships
    notifications = relationship("ReminderNotificationRecord", back_populates="reminder", cascade="all, delete-orphan")


class ReminderNotificationRecord(Base):
    """
    Persistent audit log of reminder triggers, alerts, and user acknowledgements.
    """
    __tablename__ = "reminder_notification_records"

    id = Column(Integer, primary_key=True, index=True)
    reminder_id = Column(Integer, ForeignKey("reminders.id"), nullable=False, index=True)
    notified_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    notification_type = Column(String(50), default="due_alert", nullable=False) # due_alert, recurrence_alert
    status = Column(String(50), default="pending_action", nullable=False) # pending_action, completed, dismissed
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationships
    reminder = relationship("Reminder", back_populates="notifications")
