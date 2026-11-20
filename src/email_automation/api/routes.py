"""
FastAPI Route Handlers.

Provides RESTful endpoints for Contacts, Templates, Campaigns, Reminders,
Send Records, Reporting, and System Status.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from dateutil import parser as date_parser

from src.email_automation.storage.database import get_db
from src.email_automation.storage.models import (
    Contact, Campaign, RecipientSendRecord, Reminder, ReminderNotificationRecord, get_utc_now
)
from src.email_automation.config import settings
from src.email_automation.services.personalization import TemplateService, PersonalizationError
from src.email_automation.services.csv_service import CSVService, CSVValidationError
from src.email_automation.services.reporting import ReportingService
from src.email_automation.scheduler.worker import SchedulerWorker
from src.email_automation.scheduler.recurrence import compute_next_run


router = APIRouter(prefix="/api")
template_service = TemplateService()


# =============================================================================
# Pydantic Schemas
# =============================================================================

class ContactCreate(BaseModel):
    email: str
    name: str
    company: Optional[str] = ""
    role: Optional[str] = ""
    department: Optional[str] = ""


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None


class TemplatePreviewRequest(BaseModel):
    template_name: str
    contact_id: Optional[int] = None
    custom_subject: Optional[str] = None
    custom_body: Optional[str] = None
    custom_context: Optional[Dict[str, Any]] = None


class CampaignCreate(BaseModel):
    title: str
    template_name: str
    custom_subject: Optional[str] = None
    custom_body: Optional[str] = None
    recurrence: str = Field(default="one-off", description="one-off, daily, weekly, or monthly")
    scheduled_at: str = Field(description="ISO 8601 UTC timestamp, e.g. 2026-11-25T14:00:00Z")
    recipient_contact_ids: List[int] = Field(default_factory=list, description="IDs of contacts to send to. If empty, all active contacts are targeted.")


class ReminderCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    due_time: str = Field(description="ISO 8601 UTC timestamp, e.g. 2026-11-25T14:00:00Z")
    owner: str
    team: Optional[str] = "General"
    priority: str = Field(default="medium", description="low, medium, high, urgent")
    recurrence: str = Field(default="one-off", description="one-off, daily, weekly, monthly")


class ReminderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_time: Optional[str] = None
    owner: Optional[str] = None
    team: Optional[str] = None
    priority: Optional[str] = None
    recurrence: Optional[str] = None
    status: Optional[str] = None


class ReminderStatusUpdate(BaseModel):
    status: str = Field(description="pending, due, completed, dismissed, cancelled")


# =============================================================================
# System Status & Metrics
# =============================================================================

@router.get("/health")
def get_health():
    """Returns application health, delivery mode status, and active SMTP configuration mode."""
    return {
        "status": "healthy",
        "app_env": settings.APP_ENV,
        "dry_run": settings.DRY_RUN,
        "delivery_mode": "simulation" if settings.DRY_RUN else "smtp",
        "smtp_auth_required": settings.SMTP_AUTH_REQUIRED,
        "current_utc_time": get_utc_now().isoformat()
    }


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Computes high-level counts and metrics for the dashboard overview."""
    total_contacts = db.query(Contact).filter(Contact.is_active == True).count()
    
    total_campaigns = db.query(Campaign).count()
    pending_campaigns = db.query(Campaign).filter(Campaign.status.in_(["pending", "running"])).count()
    completed_campaigns = db.query(Campaign).filter(Campaign.status == "completed").count()

    total_reminders = db.query(Reminder).count()
    pending_reminders = db.query(Reminder).filter(Reminder.status == "pending").count()
    due_reminders = db.query(Reminder).filter(Reminder.status == "due").count()
    completed_reminders = db.query(Reminder).filter(Reminder.status == "completed").count()

    simulated_sends = db.query(RecipientSendRecord).filter(RecipientSendRecord.status == "simulated").count()
    sent_sends = db.query(RecipientSendRecord).filter(RecipientSendRecord.status == "sent").count()
    failed_sends = db.query(RecipientSendRecord).filter(RecipientSendRecord.status == "failed").count()
    queued_sends = db.query(RecipientSendRecord).filter(RecipientSendRecord.status.in_(["queued", "processing"])).count()

    return {
        "contacts": {"total": total_contacts},
        "campaigns": {
            "total": total_campaigns,
            "pending": pending_campaigns,
            "completed": completed_campaigns
        },
        "reminders": {
            "total": total_reminders,
            "pending": pending_reminders,
            "due": due_reminders,
            "action_required": due_reminders,
            "completed": completed_reminders
        },
        "sends": {
            "simulated": simulated_sends,
            "sent": sent_sends,
            "failed": failed_sends,
            "queued": queued_sends,
            "total": simulated_sends + sent_sends + failed_sends + queued_sends
        },
        "dry_run": settings.DRY_RUN
    }


# =============================================================================
# Contacts Management
# =============================================================================

@router.get("/contacts")
def list_contacts(
    search: Optional[str] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Contact)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Contact.name.ilike(search_filter)) |
            (Contact.email.ilike(search_filter)) |
            (Contact.company.ilike(search_filter))
        )
    if department:
        query = query.filter(Contact.department.ilike(f"%{department}%"))

    contacts = query.order_by(Contact.id.desc()).all()
    return [
        {
            "id": c.id,
            "email": c.email,
            "name": c.name,
            "company": c.company,
            "role": c.role,
            "department": c.department,
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat()
        }
        for c in contacts
    ]


@router.post("/contacts", status_code=201)
def create_contact(payload: ContactCreate, db: Session = Depends(get_db)):
    if not CSVService.validate_email_syntax(payload.email):
        raise HTTPException(status_code=400, detail=f"Invalid email address syntax: '{payload.email}'")

    normalized_email = payload.email.strip().lower()
    existing = db.query(Contact).filter(Contact.email == normalized_email).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Contact with email '{normalized_email}' already exists.")

    contact = Contact(
        email=normalized_email,
        name=payload.name.strip(),
        company=payload.company.strip() if payload.company else "",
        role=payload.role.strip() if payload.role else "",
        department=payload.department.strip() if payload.department else "",
        is_active=True
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return {"message": "Contact created successfully", "contact_id": contact.id}


@router.put("/contacts/{contact_id}")
def update_contact(contact_id: int, payload: ContactUpdate, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if payload.name is not None:
        contact.name = payload.name.strip()
    if payload.company is not None:
        contact.company = payload.company.strip()
    if payload.role is not None:
        contact.role = payload.role.strip()
    if payload.department is not None:
        contact.department = payload.department.strip()
    if payload.is_active is not None:
        contact.is_active = payload.is_active

    db.commit()
    return {"message": "Contact updated successfully"}


@router.delete("/contacts/{contact_id}")
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"message": "Contact deleted successfully"}


@router.post("/contacts/import-csv")
async def import_contacts_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Imports contacts from uploaded CSV with rigorous row validation."""
    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV file must be encoded in UTF-8")

    try:
        result = CSVService.import_contacts_csv(csv_text, db=db, update_existing=True)
        return result
    except CSVValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Templates & Personalization
# =============================================================================

@router.get("/templates")
def list_templates():
    """Lists available email templates discovered in templates/ directory."""
    return template_service.list_templates()


@router.post("/templates/preview")
def preview_template(payload: TemplatePreviewRequest, db: Session = Depends(get_db)):
    try:
        subject_tpl, body_tpl = template_service.get_template(payload.template_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if payload.custom_subject:
        subject_tpl = payload.custom_subject
    if payload.custom_body:
        body_tpl = payload.custom_body

    context = {}
    if payload.contact_id:
        contact = db.query(Contact).filter(Contact.id == payload.contact_id).first()
        if not contact:
            raise HTTPException(status_code=404, detail=f"Contact ID {payload.contact_id} not found")
        context = {
            "name": contact.name,
            "email": contact.email,
            "company": contact.company,
            "role": contact.role,
            "department": contact.department
        }
    elif payload.custom_context:
        context = payload.custom_context
    else:
        context = {
            "name": "Jane Doe",
            "email": "jane.doe@example.com",
            "company": "Acme Innovations",
            "role": "Product Lead",
            "department": "Engineering"
        }

    try:
        rendered_subject, rendered_body = template_service.personalize_email(
            subject_tpl, body_tpl, context, strict=True
        )
        return {
            "template_name": payload.template_name,
            "preview_contact": context,
            "rendered_subject": rendered_subject,
            "rendered_body": rendered_body
        }
    except PersonalizationError as e:
        raise HTTPException(status_code=422, detail=f"Template Personalization Error: {str(e)}")


# =============================================================================
# Campaigns Management
# =============================================================================

@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).order_by(Campaign.id.desc()).all()
    results = []
    for c in campaigns:
        total_recipients = len(c.send_records)
        completed = sum(1 for r in c.send_records if r.status in ["simulated", "sent"])
        failed = sum(1 for r in c.send_records if r.status == "failed")
        queued = sum(1 for r in c.send_records if r.status in ["queued", "processing"])
        results.append({
            "id": c.id,
            "title": c.title,
            "template_name": c.template_name,
            "recurrence": c.recurrence,
            "current_run_number": c.current_run_number,
            "scheduled_at": c.scheduled_at.isoformat(),
            "next_run_at": c.next_run_at.isoformat() if c.next_run_at else None,
            "last_run_at": c.last_run_at.isoformat() if c.last_run_at else None,
            "status": c.status,
            "stats": {
                "total": total_recipients,
                "completed": completed,
                "failed": failed,
                "queued": queued
            },
            "created_at": c.created_at.isoformat()
        })
    return results


@router.post("/campaigns", status_code=201)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    try:
        tpl_subject, tpl_body = template_service.get_template(payload.template_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Template '{payload.template_name}' not found.")

    try:
        parsed_schedule = date_parser.parse(payload.scheduled_at)
        if parsed_schedule.tzinfo is None:
            parsed_schedule = parsed_schedule.replace(tzinfo=timezone.utc)
        else:
            parsed_schedule = parsed_schedule.astimezone(timezone.utc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid scheduled_at format. Please use ISO 8601 (e.g., 2026-11-25T14:00:00Z).")

    if payload.recipient_contact_ids:
        contacts = db.query(Contact).filter(
            Contact.id.in_(payload.recipient_contact_ids),
            Contact.is_active == True
        ).all()
        if not contacts:
            raise HTTPException(status_code=400, detail="None of the specified recipient contact IDs were found or active.")
    else:
        contacts = db.query(Contact).filter(Contact.is_active == True).all()
        if not contacts:
            raise HTTPException(status_code=400, detail="No active contacts found in database to schedule campaign for.")

    subject_tpl = payload.custom_subject or tpl_subject
    body_tpl = payload.custom_body or tpl_body

    campaign = Campaign(
        title=payload.title.strip(),
        template_name=payload.template_name,
        custom_subject=payload.custom_subject,
        custom_body=payload.custom_body,
        recurrence=payload.recurrence.lower().strip(),
        current_run_number=1,
        scheduled_at=parsed_schedule,
        status="pending"
    )
    db.add(campaign)
    db.flush()

    validation_failures = []
    queued_count = 0

    for contact in contacts:
        ctx = {
            "name": contact.name,
            "email": contact.email,
            "company": contact.company,
            "role": contact.role,
            "department": contact.department
        }
        try:
            rendered_sub, rendered_body = template_service.personalize_email(
                subject_tpl, body_tpl, ctx, strict=True
            )
            send_rec = RecipientSendRecord(
                campaign_id=campaign.id,
                contact_id=contact.id,
                occurrence_number=1,
                recipient_email=contact.email,
                recipient_name=contact.name,
                rendered_subject=rendered_sub,
                rendered_body=rendered_body,
                status="queued",
                delivery_mode="simulation" if settings.DRY_RUN else "smtp"
            )
            db.add(send_rec)
            queued_count += 1
        except PersonalizationError as e:
            validation_failures.append({
                "contact_id": contact.id,
                "email": contact.email,
                "error": str(e)
            })

    if queued_count == 0:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=f"Campaign could not be queued because personalization failed for all recipients: {validation_failures}"
        )

    db.commit()
    db.refresh(campaign)

    return {
        "message": f"Campaign '{campaign.title}' scheduled successfully with {queued_count} queued recipients.",
        "campaign_id": campaign.id,
        "occurrence_number": 1,
        "queued_recipients": queued_count,
        "skipped_recipients": validation_failures
    }


@router.post("/campaigns/{campaign_id}/cancel")
def cancel_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = "cancelled"
    db.query(RecipientSendRecord).filter(
        RecipientSendRecord.campaign_id == campaign_id,
        RecipientSendRecord.status == "queued"
    ).update({"status": "cancelled"})
    db.commit()
    return {"message": f"Campaign #{campaign_id} cancelled."}


@router.post("/campaigns/{campaign_id}/retry-failed")
def retry_failed_campaign_records(campaign_id: int, db: Session = Depends(get_db)):
    failed_records = db.query(RecipientSendRecord).filter(
        RecipientSendRecord.campaign_id == campaign_id,
        RecipientSendRecord.status == "failed"
    ).all()
    if not failed_records:
        return {"message": "No failed records found to retry for this campaign.", "retried_count": 0}

    for rec in failed_records:
        rec.status = "queued"
        rec.error_detail = None

    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if campaign and campaign.status in ["completed", "failed"]:
        campaign.status = "pending"

    db.commit()
    return {"message": f"Reset {len(failed_records)} failed records back to 'queued'.", "retried_count": len(failed_records)}


# =============================================================================
# Reminders Management & Notification History
# =============================================================================

@router.get("/reminders")
def list_reminders(
    status: Optional[str] = None,
    team: Optional[str] = None,
    owner: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Reminder)
    if status:
        query = query.filter(Reminder.status == status)
    if team:
        query = query.filter(Reminder.team.ilike(f"%{team}%"))
    if owner:
        query = query.filter(Reminder.owner.ilike(f"%{owner}%"))

    reminders = query.order_by(Reminder.due_time.asc()).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "due_time": r.due_time.isoformat(),
            "owner": r.owner,
            "team": r.team,
            "priority": r.priority,
            "recurrence": r.recurrence,
            "status": r.status,
            "last_notified_at": r.last_notified_at.isoformat() if r.last_notified_at else None,
            "dismissed_at": r.dismissed_at.isoformat() if r.dismissed_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "notifications_count": len(r.notifications) if r.notifications else 0,
            "created_at": r.created_at.isoformat()
        }
        for r in reminders
    ]


@router.post("/reminders", status_code=201)
def create_reminder(payload: ReminderCreate, db: Session = Depends(get_db)):
    try:
        parsed_due = date_parser.parse(payload.due_time)
        if parsed_due.tzinfo is None:
            parsed_due = parsed_due.replace(tzinfo=timezone.utc)
        else:
            parsed_due = parsed_due.astimezone(timezone.utc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid due_time. Please provide ISO 8601 format.")

    reminder = Reminder(
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else "",
        due_time=parsed_due,
        owner=payload.owner.strip(),
        team=payload.team.strip() if payload.team else "General",
        priority=payload.priority.lower().strip(),
        recurrence=payload.recurrence.lower().strip(),
        status="pending"
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return {"message": "Reminder created successfully", "reminder_id": reminder.id}


@router.patch("/reminders/{reminder_id}/status")
def update_reminder_status(reminder_id: int, payload: ReminderStatusUpdate, db: Session = Depends(get_db)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    valid_statuses = {"pending", "due", "completed", "dismissed", "cancelled"}
    new_status = payload.status.lower().strip()
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status '{new_status}'. Allowed: {', '.join(sorted(valid_statuses))}")

    reminder.status = new_status
    if new_status == "completed":
        reminder.completed_at = get_utc_now()
        for notif in reminder.notifications:
            if notif.status == "pending_action":
                notif.status = "completed"
    elif new_status == "dismissed":
        reminder.dismissed_at = get_utc_now()
        for notif in reminder.notifications:
            if notif.status == "pending_action":
                notif.status = "dismissed"

    db.commit()
    return {"message": f"Reminder status updated to {new_status}"}


@router.post("/reminders/{reminder_id}/complete")
def complete_reminder(reminder_id: int, db: Session = Depends(get_db)):
    """User action completing a pending or due reminder and updating notification history."""
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    now = get_utc_now()
    reminder.status = "completed"
    reminder.completed_at = now

    # Update active notification records
    for notif in reminder.notifications:
        if notif.status == "pending_action":
            notif.status = "completed"

    # If recurring, calculate and schedule next cycle
    if reminder.recurrence and reminder.recurrence != "one-off":
        next_due = compute_next_run(reminder.due_time, reminder.recurrence)
        reminder.due_time = next_due
        reminder.status = "pending"
        reminder.completed_at = None

    db.commit()
    return {"message": f"Reminder #{reminder_id} marked as completed.", "status": reminder.status}


@router.post("/reminders/{reminder_id}/dismiss")
def dismiss_reminder(reminder_id: int, db: Session = Depends(get_db)):
    """User action dismissing/acknowledging an alert without deleting history."""
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    now = get_utc_now()
    reminder.status = "dismissed"
    reminder.dismissed_at = now

    for notif in reminder.notifications:
        if notif.status == "pending_action":
            notif.status = "dismissed"

    if reminder.recurrence and reminder.recurrence != "one-off":
        next_due = compute_next_run(reminder.due_time, reminder.recurrence)
        reminder.due_time = next_due
        reminder.status = "pending"
        reminder.dismissed_at = None

    db.commit()
    return {"message": f"Reminder #{reminder_id} alert dismissed.", "status": reminder.status}


@router.get("/reminders/{reminder_id}/notifications")
def get_reminder_notifications(reminder_id: int, db: Session = Depends(get_db)):
    """Returns persistent notification and activity audit history for a reminder."""
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    notifs = db.query(ReminderNotificationRecord).filter(
        ReminderNotificationRecord.reminder_id == reminder_id
    ).order_by(ReminderNotificationRecord.id.desc()).all()

    return [
        {
            "id": n.id,
            "reminder_id": n.reminder_id,
            "notified_at": n.notified_at.isoformat(),
            "notification_type": n.notification_type,
            "status": n.status,
            "detail": n.detail
        }
        for n in notifs
    ]


@router.put("/reminders/{reminder_id}")
def update_reminder(reminder_id: int, payload: ReminderUpdate, db: Session = Depends(get_db)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    if payload.title is not None:
        reminder.title = payload.title.strip()
    if payload.description is not None:
        reminder.description = payload.description.strip()
    if payload.due_time is not None:
        try:
            parsed_due = date_parser.parse(payload.due_time)
            if parsed_due.tzinfo is None:
                parsed_due = parsed_due.replace(tzinfo=timezone.utc)
            else:
                parsed_due = parsed_due.astimezone(timezone.utc)
            reminder.due_time = parsed_due
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid due_time format.")
    if payload.owner is not None:
        reminder.owner = payload.owner.strip()
    if payload.team is not None:
        reminder.team = payload.team.strip()
    if payload.priority is not None:
        reminder.priority = payload.priority.lower().strip()
    if payload.recurrence is not None:
        reminder.recurrence = payload.recurrence.lower().strip()
    if payload.status is not None:
        reminder.status = payload.status.lower().strip()

    db.commit()
    return {"message": "Reminder updated successfully"}


@router.delete("/reminders/{reminder_id}")
def delete_reminder(reminder_id: int, db: Session = Depends(get_db)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    db.delete(reminder)
    db.commit()
    return {"message": "Reminder deleted successfully"}


@router.post("/reminders/import-csv")
async def import_reminders_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV file must be UTF-8 encoded")

    try:
        result = CSVService.import_reminders_csv(csv_text, db)
        return result
    except CSVValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Send Records & Delivery History
# =============================================================================

@router.get("/send-records")
def list_send_records(
    status: Optional[str] = None,
    campaign_id: Optional[int] = None,
    occurrence_number: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(RecipientSendRecord)
    if status:
        query = query.filter(RecipientSendRecord.status == status)
    if campaign_id:
        query = query.filter(RecipientSendRecord.campaign_id == campaign_id)
    if occurrence_number:
        query = query.filter(RecipientSendRecord.occurrence_number == occurrence_number)

    records = query.order_by(RecipientSendRecord.id.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "campaign_id": r.campaign_id,
            "occurrence_number": r.occurrence_number,
            "contact_id": r.contact_id,
            "recipient_email": r.recipient_email,
            "recipient_name": r.recipient_name,
            "rendered_subject": r.rendered_subject,
            "rendered_body": r.rendered_body,
            "status": r.status,
            "delivery_mode": r.delivery_mode,
            "attempt_count": r.attempt_count,
            "last_attempt_at": r.last_attempt_at.isoformat() if r.last_attempt_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "error_detail": r.error_detail
        }
        for r in records
    ]


@router.post("/send-records/{record_id}/retry")
def retry_single_send_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(RecipientSendRecord).filter(RecipientSendRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Send record not found")
    record.status = "queued"
    record.error_detail = None
    db.commit()
    return {"message": f"Send record #{record_id} re-queued for delivery attempt."}


# =============================================================================
# Downloadable CSV Audit Reports
# =============================================================================

@router.get("/reports/campaigns/csv")
def download_campaign_report(campaign_id: Optional[int] = None, db: Session = Depends(get_db)):
    csv_data = ReportingService.export_campaign_send_records_csv(db, campaign_id=campaign_id)
    filename = f"campaign_send_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/reports/reminders/csv")
def download_reminders_report(team: Optional[str] = None, db: Session = Depends(get_db)):
    csv_data = ReportingService.export_reminders_csv(db, team=team)
    filename = f"reminders_activity_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# =============================================================================
# Manual Worker Trigger (Convenience for Testing / Immediate UI Action)
# =============================================================================

@router.post("/worker/run-cycle")
def trigger_worker_cycle():
    worker = SchedulerWorker()
    result = worker.run_cycle()
    return {"message": "Worker cycle completed", "result": result}
