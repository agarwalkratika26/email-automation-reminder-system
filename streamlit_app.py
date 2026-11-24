"""
Streamlit Web Application & Interactive Dashboard
Email Automation & Reminder System

Runs as a standalone Streamlit app for local execution and 1-click
public deployment via Streamlit Community Cloud (share.streamlit.io).
"""

import sys
import io
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import streamlit as st

# Configure page settings
st.set_page_config(
    page_title="Email Automation & Reminder System",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.email_automation.config import settings
from src.email_automation.storage.database import SessionLocal, init_db
from src.email_automation.storage.models import (
    Contact, Campaign, RecipientSendRecord, Reminder, ReminderNotificationRecord, get_utc_now
)
from src.email_automation.services.personalization import TemplateService, PersonalizationError
from src.email_automation.services.csv_service import CSVService
from src.email_automation.services.reporting import ReportingService
from src.email_automation.scheduler.worker import SchedulerWorker
from src.email_automation.scheduler.recurrence import compute_next_run

# Ensure database tables exist
init_db()

template_service = TemplateService()
csv_service = CSVService()
reporting_service = ReportingService()


def get_db():
    """Provides a fresh database session."""
    return SessionLocal()


# =============================================================================
# Sidebar Navigation & System Status
# =============================================================================

st.sidebar.title("📧 Email & Reminder System")

# Delivery Mode Banner in Sidebar
if settings.DRY_RUN:
    st.sidebar.success("🛡️ **Mode: SIMULATION (Safe Dry Run)**\nEmails recorded without outbound network traffic.")
else:
    st.sidebar.warning(f"⚠️ **Mode: LIVE SMTP**\nHost: `{settings.SMTP_HOST}:{settings.SMTP_PORT}`")

# Navigation Menu
nav_choice = st.sidebar.radio(
    "Navigation",
    [
        "📊 Dashboard Overview",
        "👥 Contacts Directory",
        "📨 Campaigns & Preview",
        "⏰ Reminders Hub",
        "📜 Audit & Send Logs",
        "📥 Export Reports",
        "⚙️ System Status",
    ]
)

st.sidebar.markdown("---")
# Quick Worker Action
st.sidebar.subheader("⚡ Background Scheduler")
if st.sidebar.button("Run Scheduler Polling Cycle Now"):
    worker = SchedulerWorker()
    cycle_res = worker.run_cycle()
    st.sidebar.success(
        f"Processed {cycle_res['emails_processed']} emails, "
        f"notified {cycle_res['reminders_notified']} reminders."
    )
    st.rerun()

st.sidebar.caption("Portfolio Project | FastAPI, Next.js & Streamlit")


# =============================================================================
# Page 1: Dashboard Overview
# =============================================================================

if nav_choice == "📊 Dashboard Overview":
    st.title("📊 System Overview & Metrics")
    st.markdown(
        "A local & cloud-ready automation platform for scheduled email campaigns, "
        "personalized corporate communications, and actionable reminder tracking."
    )

    db = get_db()
    try:
        total_contacts = db.query(Contact).filter(Contact.is_active == True).count()
        total_campaigns = db.query(Campaign).count()
        pending_campaigns = db.query(Campaign).filter(Campaign.status.in_(["pending", "running"])).count()
        total_reminders = db.query(Reminder).count()
        due_reminders = db.query(Reminder).filter(Reminder.status == "due").count()
        total_sends = db.query(RecipientSendRecord).count()
        simulated_sends = db.query(RecipientSendRecord).filter(RecipientSendRecord.status == "simulated").count()
        live_sends = db.query(RecipientSendRecord).filter(RecipientSendRecord.status == "sent").count()
        failed_sends = db.query(RecipientSendRecord).filter(RecipientSendRecord.status == "failed").count()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Active Contacts", total_contacts)
        col2.metric("Active Campaigns", pending_campaigns, delta=f"{total_campaigns} Total")
        col3.metric("Due Reminders", due_reminders, delta=f"{total_reminders} Total", delta_color="inverse")
        col4.metric("Dispatched Records", total_sends, delta=f"{simulated_sends} Sim / {live_sends} Live")

        st.markdown("---")
        
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.subheader("Recent Email Campaign Dispatches")
            recent_sends = (
                db.query(RecipientSendRecord)
                .order_by(RecipientSendRecord.created_at.desc())
                .limit(10)
                .all()
            )
            if recent_sends:
                send_data = [
                    {
                        "ID": s.id,
                        "Recipient": s.recipient_email,
                        "Status": s.status.upper(),
                        "Subject": s.rendered_subject,
                        "Attempt Time": s.last_attempt_at.strftime("%Y-%m-%d %H:%M:%S") if s.last_attempt_at else "Queued",
                    }
                    for s in recent_sends
                ]
                st.dataframe(pd.DataFrame(send_data), use_container_width=True, hide_index=True)
            else:
                st.info("No campaign email records yet. Schedule your first campaign from the Campaigns tab!")

        with col_right:
            st.subheader("Actionable Due Reminders")
            actionable = (
                db.query(Reminder)
                .filter(Reminder.status.in_(["due", "pending"]))
                .order_by(Reminder.due_time.asc())
                .limit(10)
                .all()
            )
            if actionable:
                rem_data = [
                    {
                        "ID": r.id,
                        "Title": r.title,
                        "Owner": r.owner,
                        "Priority": r.priority.upper(),
                        "Due Date (UTC)": r.due_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "Status": r.status.upper(),
                    }
                    for r in actionable
                ]
                st.dataframe(pd.DataFrame(rem_data), use_container_width=True, hide_index=True)
            else:
                st.success("All reminders are completed or up to date!")

    finally:
        db.close()


# =============================================================================
# Page 2: Contacts Directory & CSV Ingestion
# =============================================================================

elif nav_choice == "👥 Contacts Directory":
    st.title("👥 Contact Directory Management")
    st.markdown("Manage contact recipients, import contacts from CSV with row-level RFC-5322 validation.")

    tabs = st.tabs(["📋 View Contacts", "➕ Add Single Contact", "📂 Ingest CSV File"])
    db = get_db()

    try:
        with tabs[0]:
            contacts = db.query(Contact).order_by(Contact.name.asc()).all()
            st.subheader(f"Total Contacts: {len(contacts)}")
            if contacts:
                df = pd.DataFrame([
                    {
                        "ID": c.id,
                        "Name": c.name,
                        "Email": c.email,
                        "Company": c.company or "-",
                        "Role": c.role or "-",
                        "Department": c.department or "-",
                        "Active": "✅" if c.is_active else "❌",
                    }
                    for c in contacts
                ])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No contacts found. Add contacts manually or upload a CSV below.")

        with tabs[1]:
            st.subheader("Add Individual Contact")
            with st.form("add_contact_form", clear_on_submit=True):
                c_name = st.text_input("Full Name *", placeholder="Jane Doe")
                c_email = st.text_input("Email Address *", placeholder="jane.doe@example.com")
                c_company = st.text_input("Company", placeholder="Acme Corp")
                c_role = st.text_input("Role / Job Title", placeholder="Software Engineer")
                c_dept = st.text_input("Department", placeholder="Engineering")
                submit_contact = st.form_submit_button("Save Contact")

                if submit_contact:
                    if not c_name or not c_email:
                        st.error("Name and Email are required fields.")
                    else:
                        existing = db.query(Contact).filter(Contact.email == c_email.strip().lower()).first()
                        if existing:
                            st.error(f"Contact with email '{c_email}' already exists.")
                        else:
                            new_c = Contact(
                                name=c_name.strip(),
                                email=c_email.strip().lower(),
                                company=c_company.strip(),
                                role=c_role.strip(),
                                department=c_dept.strip(),
                            )
                            db.add(new_c)
                            db.commit()
                            st.success(f"Contact '{c_name}' created successfully!")
                            st.rerun()

        with tabs[2]:
            st.subheader("Batch CSV Import with Row-Level Validation")
            st.markdown(
                "Upload a CSV with headers `name`, `email`, and optional `company`, `role`, `department`. "
                "Invalid emails or missing fields are caught with row-level error reporting."
            )
            csv_file = st.file_uploader("Select Contact CSV File", type=["csv"])
            if csv_file is not None:
                content = csv_file.getvalue().decode("utf-8")
                res = csv_service.parse_and_validate_contacts_csv(content, db)

                st.write(
                    f"**Ingestion Summary:** {res['valid_count']} valid contacts, "
                    f"{res['invalid_count']} invalid rows, {res['duplicate_count']} duplicates in file."
                )

                if res["errors"]:
                    st.error("⚠️ Validation Errors Found:")
                    st.dataframe(pd.DataFrame(res["errors"]), use_container_width=True, hide_index=True)

                if res["contacts"] and st.button("Commit Valid Contacts to Database"):
                    db_added = 0
                    for c_data in res["contacts"]:
                        existing = db.query(Contact).filter(Contact.email == c_data["email"]).first()
                        if not existing:
                            new_c = Contact(
                                name=c_data["name"],
                                email=c_data["email"],
                                company=c_data.get("company", ""),
                                role=c_data.get("role", ""),
                                department=c_data.get("department", ""),
                            )
                            db.add(new_c)
                            db_added += 1
                    db.commit()
                    st.success(f"Successfully saved {db_added} new contacts into the system!")
                    st.rerun()

    finally:
        db.close()


# =============================================================================
# Page 3: Campaigns & Template Preview
# =============================================================================

elif nav_choice == "📨 Campaigns & Preview":
    st.title("📨 Campaign Management & Personalization")

    db = get_db()
    try:
        available_templates = template_service.list_templates()
        active_contacts = db.query(Contact).filter(Contact.is_active == True).all()

        tabs = st.tabs(["📅 Schedule Campaign", "👁️ Live Template Preview", "📋 Campaign History"])

        with tabs[0]:
            st.subheader("Create and Schedule an Email Campaign")
            with st.form("create_campaign_form"):
                camp_title = st.text_input("Campaign Title *", placeholder="Quarterly All-Hands Sync")
                
                selected_template = st.selectbox("Select Email Template *", available_templates)
                
                col_sub, col_rec = st.columns(2)
                with col_sub:
                    recurrence_val = st.selectbox(
                        "Recurrence Schedule",
                        ["one-off", "daily", "weekly", "monthly"],
                        help="Recurring campaigns automatically reschedule their next occurrence upon execution."
                    )
                with col_rec:
                    delay_mins = st.number_input("Schedule Time: Minutes from now", min_value=0, max_value=1440, value=0)

                st.markdown("**Target Recipients**")
                target_mode = st.radio(
                    "Recipient Selection",
                    ["All Active Contacts", "Specific Contacts Selection"],
                    horizontal=True
                )

                chosen_contact_ids = []
                if target_mode == "Specific Contacts Selection" and active_contacts:
                    chosen_contacts = st.multiselect(
                        "Choose Target Contacts",
                        options=active_contacts,
                        format_func=lambda c: f"{c.name} ({c.email}) - {c.company or 'N/A'}"
                    )
                    chosen_contact_ids = [c.id for c in chosen_contacts]

                custom_subject_override = st.text_input(
                    "Custom Subject Override (Optional)",
                    placeholder="Leave blank to use default template subject"
                )
                custom_body_override = st.text_area(
                    "Custom Body Override (Optional)",
                    placeholder="Leave blank to use default template body"
                )

                submit_campaign = st.form_submit_button("🚀 Schedule Campaign")

                if submit_campaign:
                    if not camp_title:
                        st.error("Campaign title is required.")
                    else:
                        scheduled_time = get_utc_now() + timedelta(minutes=delay_mins)
                        new_camp = Campaign(
                            title=camp_title.strip(),
                            template_name=selected_template,
                            custom_subject=custom_subject_override.strip() if custom_subject_override else None,
                            custom_body=custom_body_override.strip() if custom_body_override else None,
                            recurrence=recurrence_val,
                            scheduled_at=scheduled_time,
                            status="pending",
                        )
                        db.add(new_camp)
                        db.flush()

                        # Determine targets
                        if target_mode == "All Active Contacts":
                            target_contacts = active_contacts
                        else:
                            target_contacts = [c for c in active_contacts if c.id in chosen_contact_ids]

                        # Create queued send records
                        for c in target_contacts:
                            context = {
                                "name": c.name,
                                "email": c.email,
                                "company": c.company or "",
                                "role": c.role or "",
                                "department": c.department or "",
                            }
                            try:
                                rendered_sub, rendered_body = template_service.render_template(
                                    selected_template,
                                    context=context,
                                    custom_subject=new_camp.custom_subject,
                                    custom_body=new_camp.custom_body
                                )
                            except PersonalizationError as pe:
                                rendered_sub = "Render Error"
                                rendered_body = f"Error rendering template: {str(pe)}"

                            send_rec = RecipientSendRecord(
                                campaign_id=new_camp.id,
                                contact_id=c.id,
                                recipient_email=c.email,
                                occurrence_number=1,
                                rendered_subject=rendered_sub,
                                rendered_body=rendered_body,
                                status="queued",
                            )
                            db.add(send_rec)

                        db.commit()
                        st.success(
                            f"Campaign '{camp_title}' scheduled with {len(target_contacts)} queued recipient dispatches!"
                        )
                        st.rerun()

        with tabs[1]:
            st.subheader("Live Template Personalization Preview")
            if not available_templates:
                st.warning("No templates found in the `templates/` folder.")
            else:
                prev_col1, prev_col2 = st.columns(2)
                with prev_col1:
                    prev_tmpl = st.selectbox("Template to Preview", available_templates, key="prev_tmpl")
                with prev_col2:
                    prev_contact = st.selectbox(
                        "Sample Recipient Context",
                        options=active_contacts,
                        format_func=lambda c: f"{c.name} ({c.company or 'No Company'})",
                        key="prev_contact"
                    ) if active_contacts else None

                if prev_contact:
                    ctx = {
                        "name": prev_contact.name,
                        "email": prev_contact.email,
                        "company": prev_contact.company or "Acme Innovations",
                        "role": prev_contact.role or "Specialist",
                        "department": prev_contact.department or "Operations",
                    }
                    try:
                        sub, body = template_service.render_template(prev_tmpl, context=ctx)
                        st.markdown("#### Rendered Output Preview")
                        st.info(f"**Subject:** {sub}")
                        st.text_area("Body Preview", body, height=220, disabled=True)
                    except PersonalizationError as pe:
                        st.error(f"Personalization Error: {pe}")

        with tabs[2]:
            st.subheader("All Campaigns")
            all_camps = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
            if all_camps:
                camp_df = pd.DataFrame([
                    {
                        "ID": c.id,
                        "Title": c.title,
                        "Template": c.template_name,
                        "Recurrence": c.recurrence.capitalize(),
                        "Run #": c.current_run_number,
                        "Scheduled (UTC)": c.scheduled_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "Status": c.status.upper(),
                    }
                    for c in all_camps
                ])
                st.dataframe(camp_df, use_container_width=True, hide_index=True)
            else:
                st.info("No campaigns created yet.")

    finally:
        db.close()


# =============================================================================
# Page 4: Reminders Hub
# =============================================================================

elif nav_choice == "⏰ Reminders Hub":
    st.title("⏰ Reminders Management")
    st.markdown("Track due reminders, set priority levels, and record notification audit logs.")

    db = get_db()
    try:
        tabs = st.tabs(["📋 Active & Due Reminders", "➕ Create Reminder", "📂 Ingest Reminders CSV"])

        with tabs[0]:
            st.subheader("Reminders List")
            filter_status = st.selectbox("Filter Status", ["all", "due", "pending", "completed", "dismissed"])
            query = db.query(Reminder)
            if filter_status != "all":
                query = query.filter(Reminder.status == filter_status)
            reminders = query.order_by(Reminder.due_time.asc()).all()

            if reminders:
                for rem in reminders:
                    with st.expander(f"[{rem.priority.upper()}] {rem.title} — Status: {rem.status.upper()}"):
                        st.markdown(f"**Description:** {rem.description or 'No description provided.'}")
                        st.markdown(f"**Owner:** `{rem.owner}` | **Team:** `{rem.team}` | **Recurrence:** `{rem.recurrence}`")
                        st.markdown(f"**Due Time (UTC):** `{rem.due_time.strftime('%Y-%m-%d %H:%M:%S')}`")
                        
                        btn_c1, btn_c2, btn_c3 = st.columns(3)
                        with btn_c1:
                            if rem.status != "completed" and st.button("✅ Mark Completed", key=f"comp_{rem.id}"):
                                rem.status = "completed"
                                db.commit()
                                st.rerun()
                        with btn_c2:
                            if rem.status != "dismissed" and st.button("⏹️ Dismiss", key=f"dism_{rem.id}"):
                                rem.status = "dismissed"
                                db.commit()
                                st.rerun()
                        with btn_c3:
                            if st.button("🗑️ Delete", key=f"del_{rem.id}"):
                                db.delete(rem)
                                db.commit()
                                st.rerun()
            else:
                st.info(f"No reminders found with status '{filter_status}'.")

        with tabs[1]:
            st.subheader("Create a New Reminder")
            with st.form("create_reminder_form", clear_on_submit=True):
                r_title = st.text_input("Reminder Title *", placeholder="Submit quarterly timesheets")
                r_desc = st.text_area("Description", placeholder="Check hours logged against billing codes")
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    r_owner = st.text_input("Owner *", placeholder="Alice Smith")
                    r_team = st.text_input("Team", value="Operations")
                with col_r2:
                    r_priority = st.selectbox("Priority", ["low", "medium", "high", "urgent"], index=1)
                    r_recur = st.selectbox("Recurrence", ["one-off", "daily", "weekly", "monthly"])

                r_delay = st.number_input("Due in (Minutes from now)", min_value=0, max_value=10080, value=0)
                submit_rem = st.form_submit_button("Save Reminder")

                if submit_rem:
                    if not r_title or not r_owner:
                        st.error("Title and Owner are required fields.")
                    else:
                        due_dt = get_utc_now() + timedelta(minutes=r_delay)
                        new_rem = Reminder(
                            title=r_title.strip(),
                            description=r_desc.strip(),
                            due_time=due_dt,
                            owner=r_owner.strip(),
                            team=r_team.strip(),
                            priority=r_priority,
                            recurrence=r_recur,
                            status="pending",
                        )
                        db.add(new_rem)
                        db.commit()
                        st.success(f"Reminder '{r_title}' saved successfully!")
                        st.rerun()

        with tabs[2]:
            st.subheader("Batch Reminders CSV Import")
            r_file = st.file_uploader("Upload Reminders CSV", type=["csv"], key="rem_csv")
            if r_file is not None:
                content = r_file.getvalue().decode("utf-8")
                res = csv_service.parse_and_validate_reminders_csv(content)
                st.write(f"Parsed {res['valid_count']} valid reminders, {res['invalid_count']} invalid rows.")
                if res["errors"]:
                    st.error("Validation Errors:")
                    st.dataframe(pd.DataFrame(res["errors"]), use_container_width=True, hide_index=True)
                if res["reminders"] and st.button("Commit Reminders to Database"):
                    for r_data in res["reminders"]:
                        r_model = Reminder(
                            title=r_data["title"],
                            description=r_data.get("description", ""),
                            due_time=r_data["due_time"],
                            owner=r_data["owner"],
                            team=r_data.get("team", "General"),
                            priority=r_data.get("priority", "medium"),
                            recurrence=r_data.get("recurrence", "one-off"),
                            status="pending",
                        )
                        db.add(r_model)
                    db.commit()
                    st.success(f"Imported {len(res['reminders'])} reminders successfully!")
                    st.rerun()

    finally:
        db.close()


# =============================================================================
# Page 5: Audit & Send Logs
# =============================================================================

elif nav_choice == "📜 Audit & Send Logs":
    st.title("📜 Dispatch History & Delivery Audit Logs")
    st.markdown("Detailed granular per-recipient status records and execution history.")

    db = get_db()
    try:
        col_f1, col_f2 = st.columns([1, 2])
        with col_f1:
            status_filter = st.selectbox(
                "Filter Status",
                ["all", "simulated", "sent", "failed", "queued", "processing"]
            )
        with col_f2:
            search_query = st.text_input("Search by Recipient Email", placeholder="e.g. alice@example.com")

        query = db.query(RecipientSendRecord)
        if status_filter != "all":
            query = query.filter(RecipientSendRecord.status == status_filter)
        if search_query:
            query = query.filter(RecipientSendRecord.recipient_email.ilike(f"%{search_query.strip()}%"))

        records = query.order_by(RecipientSendRecord.created_at.desc()).limit(100).all()

        st.subheader(f"Matching Records: {len(records)}")
        if records:
            df_recs = pd.DataFrame([
                {
                    "ID": r.id,
                    "Campaign ID": r.campaign_id,
                    "Recipient": r.recipient_email,
                    "Occurrence": r.occurrence_number,
                    "Status": r.status.upper(),
                    "Subject": r.rendered_subject,
                    "Attempt Time (UTC)": r.last_attempt_at.strftime("%Y-%m-%d %H:%M:%S") if r.last_attempt_at else "-",
                    "Error Detail": r.error_detail or "None",
                }
                for r in records
            ])
            st.dataframe(df_recs, use_container_width=True, hide_index=True)
        else:
            st.info("No matching send records found.")

    finally:
        db.close()


# =============================================================================
# Page 6: Export Reports
# =============================================================================

elif nav_choice == "📥 Export Reports":
    st.title("📥 Export CSV Audit Reports")
    st.markdown("Download comprehensive CSV reports for compliance, operations, and HR tracking.")

    db = get_db()
    try:
        col_rep1, col_rep2 = st.columns(2)

        with col_rep1:
            st.subheader("1. Email Dispatch History Report")
            st.markdown("Contains all recipient delivery attempts, timestamps, occurrence numbers, and error details.")
            csv_sends = reporting_service.generate_send_history_csv(db)
            st.download_button(
                label="📥 Download Send History CSV",
                data=csv_sends,
                file_name=f"email_send_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with col_rep2:
            st.subheader("2. Reminders Activity Report")
            st.markdown("Contains all reminders, priority tags, owners, teams, due times, and current statuses.")
            csv_rems = reporting_service.generate_reminder_activity_csv(db)
            st.download_button(
                label="📥 Download Reminders Report CSV",
                data=csv_rems,
                file_name=f"reminders_activity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    finally:
        db.close()


# =============================================================================
# Page 7: System Status & Configuration Reference
# =============================================================================

elif nav_choice == "⚙️ System Status":
    st.title("⚙️ System Status & Configuration")
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.subheader("Delivery Engine")
        st.markdown(f"- **Simulation Mode (DRY_RUN):** `{'Enabled (Safe)' if settings.DRY_RUN else 'Disabled (Live SMTP)'}`")
        st.markdown(f"- **SMTP Host:** `{settings.SMTP_HOST}:{settings.SMTP_PORT}`")
        st.markdown(f"- **From Address:** `{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>`")
        st.markdown(f"- **TLS / SSL:** `TLS={settings.SMTP_USE_TLS}, SSL={settings.SMTP_USE_SSL}`")
        st.markdown(f"- **Batch Send Size:** `{settings.BATCH_SEND_SIZE} records / cycle`")
        st.markdown(f"- **Stale Job Recovery Timeout:** `{settings.STALE_JOB_TIMEOUT_SECONDS} seconds`")

    with col_s2:
        st.subheader("Database & Environment")
        st.markdown(f"- **Environment:** `{settings.APP_ENV}`")
        st.markdown(f"- **Database URL:** `{settings.DATABASE_URL}`")
        st.markdown(f"- **Interactive Swagger Docs:** `http://localhost:{settings.API_PORT}/docs`")
        st.markdown(f"- **Templates Directory:** `{settings.TEMPLATES_DIR}`")
        st.markdown(f"- **Logs Directory:** `{settings.LOGS_DIR}`")
