"""
Unit tests for Template & Personalization Service.
"""

import pytest
from src.email_automation.services.personalization import (
    TemplateService, PersonalizationError
)


def test_parse_raw_content_with_subject():
    raw = "Subject: Welcome {name}!\n\nHello {name}, welcome to {company}."
    subject, body = TemplateService.parse_raw_content(raw)
    assert subject == "Welcome {name}!"
    assert body == "Hello {name}, welcome to {company}."


def test_parse_raw_content_without_subject():
    raw = "Hello {name}, welcome to {company}."
    subject, body = TemplateService.parse_raw_content(raw)
    assert subject == "Notification"
    assert body == "Hello {name}, welcome to {company}."


def test_extract_placeholders():
    text = "Hi {name}, your role at {company} in {department} is confirmed."
    placeholders = TemplateService.extract_placeholders(text)
    assert placeholders == {"name", "company", "department"}


def test_personalize_email_success():
    sub_tpl = "Sync for {company}"
    body_tpl = "Dear {name}, please attend as {role}."
    context = {"company": "Acme", "name": "Alice", "role": "Engineer"}

    sub, body = TemplateService.personalize_email(sub_tpl, body_tpl, context, strict=True)
    assert sub == "Sync for Acme"
    assert body == "Dear Alice, please attend as Engineer."


def test_personalize_email_missing_placeholder_raises_error():
    sub_tpl = "Sync for {company}"
    body_tpl = "Dear {name}, your deadline is {deadline}."
    context = {"company": "Acme", "name": "Alice"}  # Missing 'deadline'

    with pytest.raises(PersonalizationError) as exc_info:
        TemplateService.personalize_email(sub_tpl, body_tpl, context, strict=True)

    assert "deadline" in str(exc_info.value)
