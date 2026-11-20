"""
Integration tests for Scheduler Worker and End-to-End Campaign Execution.
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.email_automation.storage.database import Base
from src.email_automation.storage.models import (
    Contact, Campaign, RecipientSendRecord, Reminder
)
from src.email_automation.scheduler.worker import SchedulerWorker
from src.email_automation.config import settings


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    return TestingSession


def test_worker_processes_due_campaign():
    # Force simulation mode
    settings.DRY_RUN = True
    session_factory = setup_in_memory_db()
    db = session_factory()

    # Create contact
    contact = Contact(
        name="Elena Rostova",
        email="elena.rostova@quantumlogistics.fake",
        company="Quantum Logistics",
        role="Supply Chain Lead",
        department="Logistics"
    )
    db.add(contact)
    db.commit()

    # Create due campaign (scheduled 1 hour ago)
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    campaign = Campaign(
        title="Weekly Logistics Check-In",
        template_name="welcome_onboarding.txt",
        recurrence="one-off",
        scheduled_at=one_hour_ago,
        status="pending"
    )
    db.add(campaign)
    db.flush()

    # Queue send record
    send_rec = RecipientSendRecord(
        campaign_id=campaign.id,
        contact_id=contact.id,
        recipient_email=contact.email,
        recipient_name=contact.name,
        rendered_subject="Welcome Elena Rostova!",
        rendered_body="Hello Elena, welcome to Quantum Logistics.",
        status="queued",
        delivery_mode="simulation"
    )
    db.add(send_rec)
    db.commit()

    # Initialize worker with this in-memory db factory
    worker = SchedulerWorker(db_factory=session_factory)
    result = worker.run_cycle()

    assert result["emails_processed"] == 1

    # Verify record was marked simulated
    db.refresh(send_rec)
    assert send_rec.status == "simulated"
    assert send_rec.attempt_count == 1
    assert send_rec.completed_at is not None

    # Run another cycle to complete campaign
    worker.run_cycle()
    db.refresh(campaign)
    assert campaign.status == "completed"


def test_worker_stale_processing_recovery():
    session_factory = setup_in_memory_db()
    db = session_factory()

    contact = Contact(name="Bob", email="bob@test.com")
    campaign = Campaign(
        title="Test",
        template_name="test.txt",
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
        status="running"
    )
    db.add_all([contact, campaign])
    db.flush()

    # Simulate an abandoned job in 'processing' state (as if worker crashed)
    stale_rec = RecipientSendRecord(
        campaign_id=campaign.id,
        contact_id=contact.id,
        recipient_email=contact.email,
        recipient_name=contact.name,
        rendered_subject="Subject",
        rendered_body="Body",
        status="processing"
    )
    db.add(stale_rec)
    db.commit()

    worker = SchedulerWorker(db_factory=session_factory)
    worker.run_cycle()

    db.refresh(stale_rec)
    assert stale_rec.status == "queued"
