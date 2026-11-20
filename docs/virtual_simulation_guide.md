# Virtual Simulation & Safe Demonstration Guide

This guide explains how to safely explore, demonstrate, and evaluate the **Email Automation & Reminder System** using default simulation mode without configuring real mail credentials.

---

## 1. Simulation Mode (Safe Dry Run) Explained

By default, the application runs with `DRY_RUN=true` set in configuration.

### What Happens in Simulation Mode?
1. The system performs full data validation, template parsing, token substitution, and SQLite state persistence.
2. When a campaign or reminder triggers, the `DeliveryAdapter` logs the simulated dispatch to console and `logs/worker.log`.
3. The recipient record is marked as **`simulated`**.
4. **No network socket** is opened to port 25, 465, or 587.
5. Zero email messages leave your computer. No mail provider account is required.

---

## 2. Using Fictional Sample Data

The project includes pre-built fictional sample datasets in `data/`:

- **`data/sample_contacts.csv`:** Contains fictional contacts across various roles and companies (e.g. `alice.johnson@acmecorp.fake`).
- **`data/sample_reminders.csv`:** Contains representative team and personal reminders with priority levels and recurrence rules.

### Testing CSV Import in the Dashboard:
1. Navigate to the **Contacts & CSV** tab in the dashboard (`http://localhost:3000`).
2. Upload `data/sample_contacts.csv`.
3. The validation engine confirms valid rows and updates the contact directory.
4. Try creating a small CSV with intentional errors (e.g., missing email or malformed syntax). Observe how the error table highlights exact row numbers and failure reasons.

---

## 3. Scheduling & Inspecting Simulated Delivery

1. Navigate to the **Campaigns & Templates** tab.
2. Enter a campaign title (e.g., `Welcome New Hires`).
3. Select `welcome_onboarding.txt`.
4. Choose a contact to inspect the **Live Personalization Preview**. Notice how `{name}`, `{company}`, `{role}`, and `{department}` are dynamically replaced.
5. Set the scheduled time to the current time or a past time, then click **Confirm & Schedule Campaign**.
6. Trigger the worker in one of two ways:
   - Click the **"⚡ Run Worker Cycle"** button in the dashboard top navigation.
   - Run in your terminal: `python -m src.email_automation.scheduler.worker --once`
7. Check the **Send History & Audit** tab to inspect the generated records marked as **`SIMULATED`**.
8. Click **Inspect** to see the full rendered subject and body stored in SQLite.

---

## 4. Downloading Audit CSV Reports

1. Navigate to the **CSV Reports** tab.
2. Click **Download Campaign CSV Report** to retrieve `campaign_send_report_YYYYMMDD_HHMMSS.csv`.
3. Click **Download Reminders CSV Report** to retrieve `reminders_activity_report_YYYYMMDD_HHMMSS.csv`.
4. Open the files in Excel, Google Sheets, or any text editor to verify column schemas and audit trails.

---

## 5. Transitioning to Real Enterprise SMTP (Optional)

To connect the application to an authorized corporate or transactional email server (such as Gmail App Passwords, SendGrid, Mailgun, or Amazon SES):

1. Copy `.env.example` to `.env` (ensure `.env` remains in `.gitignore`).
2. Set `DRY_RUN=false`.
3. Populate valid SMTP credentials:
   ```env
   DRY_RUN=false
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your_address@gmail.com
   SMTP_PASSWORD=your_16_character_app_password
   SMTP_FROM_EMAIL=your_address@gmail.com
   SMTP_FROM_NAME="Corporate Operations"
   SMTP_USE_TLS=true
   SMTP_USE_SSL=false
   ```
4. Restart the API server and worker process.
5. Verify that dispatches transition to **`sent`** upon acceptance by the SMTP host.

> [!WARNING]
> **Safety Notice:**
> - Never commit `.env` or secrets to GitHub.
> - Never test with real customer email lists without explicit consent.
> - `sent` status indicates the SMTP relay accepted the message; it does not guarantee inbox placement or that the recipient read the email.
