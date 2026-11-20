"""
Integration tests for FastAPI REST Endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.email_automation.storage.models  # Ensure models register with Base.metadata
from src.email_automation.storage.database import Base, get_db
from src.email_automation.api.app import app
from src.email_automation.config import settings


# In-memory database with StaticPool so all connections share the same memory DB
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["dry_run"] is True
    assert data["delivery_mode"] == "simulation"


def test_stats_endpoint():
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "contacts" in data
    assert "campaigns" in data
    assert "reminders" in data
    assert "sends" in data


def test_contacts_crud_and_validation():
    # Valid creation
    post_res = client.post("/api/contacts", json={
        "name": "Sarah Connor",
        "email": "sarah.connor@cyberdyne.fake",
        "company": "Cyberdyne Systems",
        "role": "Security Specialist",
        "department": "Security"
    })
    assert post_res.status_code == 201
    contact_id = post_res.json()["contact_id"]

    # Invalid email syntax
    bad_res = client.post("/api/contacts", json={
        "name": "Bad User",
        "email": "not-an-email"
    })
    assert bad_res.status_code == 400

    # Duplicate email conflict
    dup_res = client.post("/api/contacts", json={
        "name": "Sarah Duplicate",
        "email": "sarah.connor@cyberdyne.fake"
    })
    assert dup_res.status_code == 409

    # List contacts
    list_res = client.get("/api/contacts")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1


def test_templates_list_and_preview():
    list_res = client.get("/api/templates")
    assert list_res.status_code == 200
    templates = list_res.json()
    assert len(templates) > 0
    assert any(t["name"] == "welcome_onboarding.txt" for t in templates)

    # Preview with dummy context
    prev_res = client.post("/api/templates/preview", json={
        "template_name": "welcome_onboarding.txt",
        "custom_context": {
            "name": "Grace Hopper",
            "company": "NextGen Labs",
            "role": "Systems Architect",
            "department": "R&D"
        }
    })
    assert prev_res.status_code == 200
    preview_data = prev_res.json()
    assert "Grace Hopper" in preview_data["rendered_subject"]
    assert "NextGen Labs" in preview_data["rendered_body"]


def test_reminders_crud():
    post_res = client.post("/api/reminders", json={
        "title": "Quarterly Tax Prep",
        "description": "Gather invoices for accountant",
        "due_time": "2026-12-15T10:00:00Z",
        "owner": "David Miller",
        "team": "Finance",
        "priority": "high",
        "recurrence": "one-off"
    })
    assert post_res.status_code == 201
    reminder_id = post_res.json()["reminder_id"]

    # Patch status
    patch_res = client.patch(f"/api/reminders/{reminder_id}/status", json={"status": "completed"})
    assert patch_res.status_code == 200

    # Get reminders
    get_res = client.get(f"/api/reminders?status=completed")
    assert get_res.status_code == 200
    assert len(get_res.json()) >= 1


def test_download_reports():
    # Campaign report
    camp_res = client.get("/api/reports/campaigns/csv")
    assert camp_res.status_code == 200
    assert "text/csv" in camp_res.headers["content-type"]
    assert "record_id,campaign_id" in camp_res.text

    # Reminders report
    rem_res = client.get("/api/reports/reminders/csv")
    assert rem_res.status_code == 200
    assert "text/csv" in rem_res.headers["content-type"]
    assert "reminder_id,title" in rem_res.text
