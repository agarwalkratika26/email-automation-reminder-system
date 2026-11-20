"""
Unit tests for Recurrence Calculation and Delivery Adapter.
"""

from datetime import datetime, timezone
import pytest
from src.email_automation.scheduler.recurrence import compute_next_run
from src.email_automation.services.delivery import DeliveryAdapter, DeliveryConfigError
from src.email_automation.config import settings


def test_recurrence_one_off():
    base = datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc)
    assert compute_next_run(base, "one-off") is None


def test_recurrence_daily():
    base = datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc)
    next_time = compute_next_run(base, "daily")
    assert next_time == datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)


def test_recurrence_weekly():
    base = datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc)
    next_time = compute_next_run(base, "weekly")
    assert next_time == datetime(2026, 11, 28, 10, 0, 0, tzinfo=timezone.utc)


def test_recurrence_monthly():
    base = datetime(2026, 1, 31, 15, 0, 0, tzinfo=timezone.utc)
    next_time = compute_next_run(base, "monthly")
    # In leap/non-leap year, relativedelta snaps Jan 31 to Feb 28
    assert next_time == datetime(2026, 2, 28, 15, 0, 0, tzinfo=timezone.utc)


def test_delivery_adapter_simulation_mode():
    # Guarantee DRY_RUN is True
    settings.DRY_RUN = True
    result = DeliveryAdapter.send_email(
        to_email="test.user@example.com",
        to_name="Test User",
        subject="Test Campaign",
        body="Hello World"
    )

    assert result.success is True
    assert result.status == "simulated"
    assert result.mode == "simulation"
    assert "No SMTP connection was made" in result.message


def test_smtp_validation_missing_host():
    original_host = settings.SMTP_HOST
    try:
        settings.SMTP_HOST = ""
        with pytest.raises(DeliveryConfigError):
            DeliveryAdapter.validate_smtp_configuration()
    finally:
        settings.SMTP_HOST = original_host
