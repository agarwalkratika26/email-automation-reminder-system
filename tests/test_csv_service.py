"""
Unit tests for CSV Ingestion and Validation Service.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import src.email_automation.storage.models  # Ensure models are loaded
from src.email_automation.storage.database import Base
from src.email_automation.storage.models import Contact, Reminder
from src.email_automation.services.csv_service import CSVService


def get_test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    return TestingSession()


def test_email_syntax_validation():
    assert CSVService.validate_email_syntax("user@example.com") is True
    assert CSVService.validate_email_syntax("user.name+tag@sub.example.co.uk") is True
    assert CSVService.validate_email_syntax("invalid-email") is False
    assert CSVService.validate_email_syntax("missing-domain@") is False
    assert CSVService.validate_email_syntax("@missing-user.com") is False
    assert CSVService.validate_email_syntax("") is False


def test_import_contacts_csv_valid_and_invalid():
    db = get_test_db()
    csv_data = """name,email,company,role,department
Alice,alice@example.com,Acme,Lead,Ops
Bob,not-an-email,Innova,Dev,Eng
Carol,,Apex,HR,People
David,david@example.com,Starlight,Finance,Fin
Alice Duplicate,alice@example.com,Acme,Lead,Ops
"""

    result = CSVService.import_contacts_csv(csv_data, db=db, update_existing=True)

    assert result["total_rows"] == 5
    assert result["imported"] == 2  # Alice and David
    assert result["invalid_count"] == 3  # Bob (bad syntax), Carol (empty email), Duplicate Alice

    # Verify invalid row reporting details
    invalid_rows = result["invalid_rows"]
    reasons_combined = " ".join(r["reason"] for r in invalid_rows)
    assert "Invalid email syntax" in reasons_combined
    assert "Email field is empty" in reasons_combined
    assert "Duplicate email" in reasons_combined


def test_import_reminders_csv():
    db = get_test_db()
    # Row 3 has an empty title (starting with empty comma)
    csv_data = """title,description,due_time,owner,team,recurrence,priority
Q3 Budget,Review numbers,2026-11-25T14:00:00Z,Alice,Finance,monthly,high
Invalid Date,Something,invalid-datetime-here,Bob,Engineering,weekly,low
,,2026-11-26T10:00:00Z,Carol,HR,one-off,medium
"""

    result = CSVService.import_reminders_csv(csv_data, db=db)
    assert result["total_rows"] == 3
    assert result["imported"] == 1
    assert result["invalid_count"] == 2

    reminders = db.query(Reminder).all()
    assert len(reminders) == 1
    assert reminders[0].title == "Q3 Budget"
    assert reminders[0].recurrence == "monthly"
