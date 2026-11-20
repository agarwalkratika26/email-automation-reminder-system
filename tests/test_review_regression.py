"""
Regression tests addressing technical review findings:
1. Reminder notification history and user completion/dismissal actions.
2. Recurring campaign occurrence tracking preserving historical records across runs.
3. Safe worker behavior: timeout-based stale recovery and atomic conditional claiming.
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.email_automation.storage.models
from src.email_automation.storage.database import Base
from src.email_automation.storage.models import (
    Contact, Campaign, RecipientSendRecord, Reminder, ReminderNotificationRecord
)
from src.email_automation.scheduler.worker import SchedulerWorker
from src.email_automation.config import settings


def get_memory_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_reminder_due_keeps_actionable_and_records_notification():
    """Verify that due reminders transition to 'due' (not completed) and persist notification logs."""
    session_factory = get_memory_session_factory()
    db = session_factory()

    past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    reminder = Reminder(
        title="Quarterly Budget Review",
        description="Verify department expenses",
        due_time=past_time,
        owner="Alice",
        team="Finance",
        priority="high",
        recurrence="one-off",
        status="pending"
    )
    db.add(reminder)
    db.commit()

    worker = SchedulerWorker(db_factory=session_factory)
    result = worker.run_cycle()

    assert result["reminders_notified"] == 1

    db.refresh(reminder)
    # Reminder remains actionable in 'due' status
    assert reminder.status == "due"
    assert reminder.last_notified_at is not None

    # Notification record is persisted
    notifications = db.query(ReminderNotificationRecord).filter(
        ReminderNotificationRecord.reminder_id == reminder.id
    ).all()
    assert len(notifications) == 1
    assert notifications[0].status == "pending_action"
    assert "Quarterly Budget Review" in notifications[0].detail


def test_recurring_campaign_preserves_separate_occurrence_history():
    """Verify that recurring campaigns create distinct send records for each occurrence."""
    settings.DRY_RUN = True
    session_factory = get_memory_session_factory()
    db = session_factory()

    contact = Contact(name="Bob", email="bob@sample.fake", company="TechCorp", role="Dev")
    db.add(contact)
    db.commit()

    past_time = datetime.now(timezone.utc) - timedelta(hours=1)
    campaign = Campaign(
        title="Daily Standup Notification",
        template_name="meeting_reminder.txt",
        recurrence="daily",
        current_run_number=1,
        scheduled_at=past_time,
        status="pending"
    )
    db.add(campaign)
    db.flush()

    # Occurrence 1 send record
    rec1 = RecipientSendRecord(
        campaign_id=campaign.id,
        contact_id=contact.id,
        occurrence_number=1,
        recipient_email=contact.email,
        recipient_name=contact.name,
        rendered_subject="Standup Reminder 1",
        rendered_body="Body 1",
        status="queued"
    )
    db.add(rec1)
    db.commit()

    worker = SchedulerWorker(db_factory=session_factory)

    # First cycle dispatches occurrence 1
    res1 = worker.run_cycle()
    assert res1["emails_processed"] == 1

    db.refresh(rec1)
    assert rec1.status == "simulated"
    assert rec1.occurrence_number == 1

    # Second cycle detects occurrence 1 is complete and schedules occurrence 2
    worker.run_cycle()
    db.refresh(campaign)
    assert campaign.current_run_number == 2
    assert campaign.next_run_at is not None

    # Check total records in database
    all_records = db.query(RecipientSendRecord).filter(
        RecipientSendRecord.campaign_id == campaign.id
    ).order_by(RecipientSendRecord.occurrence_number.asc()).all()

    # Must have 2 distinct records: one for occurrence 1, one queued for occurrence 2
    assert len(all_records) == 2
    assert all_records[0].occurrence_number == 1
    assert all_records[0].status == "simulated"  # Prior history NOT overwritten!

    assert all_records[1].occurrence_number == 2
    assert all_records[1].status == "queued"


def test_worker_stale_job_timeout_safety():
    """Verify that active jobs within timeout are NOT reset, and only expired jobs recover."""
    session_factory = get_memory_session_factory()
    db = session_factory()

    now = datetime.now(timezone.utc)
    contact = Contact(name="Carol", email="carol@sample.fake")
    campaign = Campaign(title="Test Camp", template_name="test.txt", scheduled_at=now, status="running")
    db.add_all([contact, campaign])
    db.flush()

    # Active job touched 10 seconds ago (should NOT be reset)
    active_rec = RecipientSendRecord(
        campaign_id=campaign.id,
        contact_id=contact.id,
        occurrence_number=1,
        recipient_email=contact.email,
        recipient_name=contact.name,
        rendered_subject="Active",
        rendered_body="Active",
        status="processing",
        last_attempt_at=now - timedelta(seconds=10)
    )

    # Abandoned job touched 2 hours ago (SHOULD be reset)
    abandoned_rec = RecipientSendRecord(
        campaign_id=campaign.id,
        contact_id=contact.id,
        occurrence_number=1,
        recipient_email=contact.email,
        recipient_name=contact.name,
        rendered_subject="Abandoned",
        rendered_body="Abandoned",
        status="processing",
        last_attempt_at=now - timedelta(hours=2)
    )

    db.add_all([active_rec, abandoned_rec])
    db.commit()

    worker = SchedulerWorker(db_factory=session_factory)
    recovered = worker.recover_stale_processing(db)

    # Only 1 job exceeded timeout
    assert recovered == 1

    db.refresh(active_rec)
    db.refresh(abandoned_rec)

    assert active_rec.status == "processing"  # Untouched!
    assert abandoned_rec.status == "queued"   # Recovered safely!
