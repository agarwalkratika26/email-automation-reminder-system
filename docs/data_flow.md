# Data Flow & Pipelines

## 1. End-to-End Processing Workflow

The system follows a strict 6-stage lifecycle:
```
[Contact List] ──► [Message Template] ──► [Scheduled Job] ──► [Email Sending] ──► [Status Tracking] ──► [Report Generation]
```

---

## 2. Detailed Data Pipeline Stages

### Stage 1: Ingestion & Validation
- **Inputs:** `data/sample_contacts.csv`, `data/sample_reminders.csv`, or uploaded CSV files via the dashboard.
- **Normalization:** Column names are stripped and lowercased.
- **Syntax Validation:** Email addresses validated against RFC 5322 regex.
- **Error Capture:** Rows failing validation (empty emails, bad syntax, internal duplicates) are appended to an `invalid_rows` array with exact row numbers and human-readable diagnostic reasons.
- **Duplicate Prevention Rule:** Contact emails are unique. When a contact with an existing email is uploaded, the existing contact record is updated with new details rather than creating a duplicate.

### Stage 2: Template Loading & Token Personalization
- **Discovery:** Files in `templates/*.txt` are loaded.
- **Header Parsing:** If the template begins with `Subject: <title>`, the subject is extracted.
- **Token Extraction:** Regular expressions identify `{placeholder}` variables.
- **Validation:** Strict mode checks that all placeholders (`{name}`, `{company}`, `{role}`, `{department}`) are provided by the contact record. If missing, a clear `PersonalizationError` is raised with the missing keys.

### Stage 3: Job Creation & Scheduling
- **Persistence:** Campaigns and reminders are stored in SQLite.
- **Timezone Awareness:** Timestamps are normalized and stored as UTC-aware datetimes (`YYYY-MM-DDTHH:MM:SSZ`).
- **Recurrence Calculation:**
  - `one-off`: No next run (`next_run_at = None`).
  - `daily`: `current_run + 1 day`.
  - `weekly`: `current_run + 7 days`.
  - `monthly`: `current_run + relativedelta(months=1)` (safely handling 28, 30, and 31-day months).

### Stage 4: Worker Dispatch & Delivery
- **Atomic Locking:** Recipient records transition from `queued` to `processing` with attempt counts incremented.
- **Crash Recovery:** If the worker restarts unexpectedly, stale `processing` jobs are restored to `queued`.
- **Delivery Mode Adapter:**
  - **Simulation Mode (`DRY_RUN=true`):** No socket connection opened. Logs simulation message and marks record as `simulated`.
  - **SMTP Mode (`DRY_RUN=false`):** Connects to configured SMTP server with TLS/SSL. Never logs passwords or sensitive credentials. Records status as `sent` upon server acceptance, or `failed` with error details.

### Stage 5: Audit & Reporting
- Every dispatch attempt is recorded in `recipient_send_records`.
- Downloadable CSV audit reports are generated via Pandas on demand.
