# Engineering Project & Technical Review Report

**Project Title:** Email Automation & Reminder System  
**Prepared For:** Technical Manager / Engineering Lead Review  
**Date:** November 21, 2026  
**Status:** Completed, Verified & Ready for Evaluation  
**Test Suite:** 25/25 Tests Passing (100% Pass Rate) | Frontend Build: Verified (Exit Code 0)  
**Primary Tech Stack:** Python 3.10+ (FastAPI, SQLAlchemy, Pandas, Schedule), Next.js 15, TypeScript, SQLite  

---

## 1. Executive Summary

The **Email Automation & Reminder System** is a local automation platform for student portfolio and educational use, designed to eliminate repetitive manual communication workflows across business operations, Human Resources, sales, and administration.

The system automates the complete 6-stage lifecycle:
$$\text{Contact List} \longrightarrow \text{Message Template} \longrightarrow \text{Scheduled Job} \longrightarrow \text{Email Sending} \longrightarrow \text{Status Tracking} \longrightarrow \text{Report Generation}$$

Crucially, the application operates in **Simulation Mode (`DRY_RUN=true`) by default**, enabling comprehensive end-to-end evaluation, testing, and grading without requiring third-party email accounts, credentials, or network socket connections, while maintaining the architecture necessary to connect to corporate SMTP relays.

---

## 2. System Architecture & Components

```
+---------------------------------------------------------------------------------------+
|                               Next.js 15 Web Dashboard                                |
|   - Real-time Campaign / Reminder Metrics       - Contact Directory & CSV Ingestion   |
|   - Live Template Personalization Preview       - Send History & Error Inspector      |
|   - CSV Audit Report Downloader                 - Simulation Mode Active Indicator    |
+------------------------------------------+--------------------------------------------+
                                           | HTTP REST API (JSON)
                                           v
+---------------------------------------------------------------------------------------+
|                                FastAPI Backend Server                                 |
|   - /api/contacts (CRUD & CSV Import)           - /api/templates & /api/preview       |
|   - /api/campaigns (Schedule, Cancel, Retry)    - /api/reminders (CRUD, Status)       |
|   - /api/send-records (Audit Log, Filter)       - /api/reports (CSV Streamers)        |
+-------------------+-----------------------------------------------+-------------------+
                    |                                               |
                    v                                               v
+-----------------------------------------+   +-----------------------------------------+
|      Local SQLite Database Storage      |   |       Template Filesystem Store         |
|  - contacts (unique email indexed)      |   |  - templates/*.txt                      |
|  - campaigns (recurrence, schedule)     |   |  - Subject header parsing               |
|  - recipient_send_records (audit log)   |   |  - Token extraction: {name}, {company}  |
|  - reminders (personal & team tasks)    |   +-----------------------------------------+
+-------------------+---------------------+
                    ^
                    | Polling & State Updates (every N seconds)
+-------------------+-------------------------------------------------------------------+
|                        Autonomous Python Scheduler / Worker                           |
|   - Recurrence Calculation: one-off, daily (+1d), weekly (+7d), monthly (+1m)         |
|   - Crash Recovery: resets orphaned 'processing' records to 'queued' on startup       |
|   - Batch Dispatcher: atomic transitions (queued -> processing -> simulated/sent)     |
+------------------------------------------+--------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                                Delivery Adapter Layer                                 |
|                                                                                       |
|   [DRY_RUN=true (Default)]                             [DRY_RUN=false (Explicit)]     |
|   ------------------------                             --------------------------     |
|   - Simulation Mode                                    - Live Authenticated SMTP      |
|   - NO network socket opened                           - smtplib + EmailMessage (MIME)|
|   - Status: 'simulated'                                - TLS / SSL transport          |
|   - Completely safe for student demos                  - Status: 'sent' or 'failed'   |
+---------------------------------------------------------------------------------------+
```

### Key Architectural Decisions
1. **Decoupled Asynchronous Worker:** Long-running batch dispatches are decoupled from FastAPI request handlers. Dispatches execute in an independent background worker daemon, keeping web endpoints responsive and non-blocking.
2. **Local Relational Persistence (SQLite):** Eliminates dependencies on external database daemons (PostgreSQL) or memory stores (Redis) while providing ACID compliance, indexed lookups, and relational integrity.
3. **Template & Code Separation:** Email copy lives in `templates/*.txt`. Business stakeholders can adjust text without modifying Python source code.
4. **Idempotency & Crash Resilience:** Dispatches follow atomic status transitions (`queued` $\to$ `processing` $\to$ `simulated`/`sent`/`failed`). Orphaned `processing` records caused by worker crashes are automatically reset on restart.

---

## 3. Detailed Feature Matrix

| Functional Area | Technical Implementation | Business & Operational Value |
| :--- | :--- | :--- |
| **Contact Directory & CSV Ingestion** | Pandas-powered parser with RFC 5322 email syntax validation, unique email indexing, and row-by-row diagnostic error logging. | Uploads contact lists cleanly; reports malformed rows by exact CSV row number and reason without discarding valid data. |
| **Template Personalization** | File-based template loader extracting `{name}`, `{company}`, `{role}`, `{department}` tokens with strict error detection (`PersonalizationError`). | Prevents placeholder leakages (e.g., `Hello {name}`) and personalizes subject and body simultaneously. |
| **Campaign Scheduling & Recurrence** | UTC-aware datetimes with deterministic recurrence calculation (`one-off`, `daily`, `weekly`, `monthly` via `relativedelta`). | Accurately accounts for calendar quirks (28, 30, 31-day months, leap years, timezone offsets). |
| **Delivery Adapter (Simulation & SMTP)** | Pluggable delivery interface. Defaults to simulated delivery (`simulated` status) with optional authenticated SMTP (`smtplib`, `EmailMessage`). | Guaranteed zero-cost, zero-spam evaluation for student portfolio; supports optional SMTP relay configuration documented in `.env.example`. |
| **Autonomous Scheduler Worker** | Background daemon utilizing the Python `schedule` library with batch dispatching, retry mechanisms, and crash recovery. | Scheduled jobs run reliably even if the dashboard browser tab is closed. |
| **Personal & Team Reminders** | Relational model supporting priorities (`low`, `medium`, `high`, `urgent`), assignees, team filters, and recurrence rules. | Centralizes task deadlines and team operational reminders with status toggling. |
| **Compliance Audit Reporting** | Streamed CSV downloads generated via Pandas for email attempts and reminder histories. | Provides full auditability for HR, Operations, and Compliance officers. |
| **Next.js Web Dashboard** | Next.js 15 App Router, TypeScript, Tailwind CSS, real-time counters, live template preview, and inspect modals. | Modern, intuitive user experience for non-technical administrators and reviewers. |

---

## 4. Security, Safety & Compliance Guardrails

- **Zero Accidental Sends:** `DRY_RUN=true` is hardcoded as the default configuration. Real email dispatching requires an explicit `.env` modification.
- **Credential Sanitization:** Passwords and tokens are never logged, printed in exceptions, or exposed in API payloads.
- **Safe Versioned Data:** The repository contains only fictional dummy data (`data/sample_contacts.csv`, `data/sample_reminders.csv`).
- **Strict `.gitignore` Policy:** Excludes `.env`, SQLite databases (`*.db`), virtual environments (`.venv`), temporary output files, and runtime logs.

---

## 5. Verification & Test Suite Summary

The backend and frontend were subjected to automated validation:

### A. Backend Pytest Test Suite
Command executed:
```powershell
.\.venv\Scripts\pytest.exe -v
```
**Results:** **25 Passed, 0 Failed (100% Pass Rate)**

```text
tests/test_api.py::test_health_endpoint PASSED                           [  4%]
tests/test_api.py::test_stats_endpoint PASSED                            [  8%]
tests/test_api.py::test_contacts_crud_and_validation PASSED              [ 12%]
tests/test_api.py::test_templates_list_and_preview PASSED                [ 16%]
tests/test_api.py::test_reminders_crud PASSED                            [ 20%]
tests/test_api.py::test_download_reports PASSED                          [ 24%]
tests/test_csv_service.py::test_email_syntax_validation PASSED           [ 28%]
tests/test_csv_service.py::test_import_contacts_csv_valid_and_invalid PASSED [ 32%]
tests/test_csv_service.py::test_import_reminders_csv PASSED              [ 36%]
tests/test_delivery_and_recurrence.py::test_recurrence_one_off PASSED    [ 40%]
tests/test_delivery_and_recurrence.py::test_recurrence_daily PASSED      [ 44%]
tests/test_delivery_and_recurrence.py::test_recurrence_weekly PASSED     [ 48%]
tests/test_delivery_and_recurrence.py::test_recurrence_monthly PASSED    [ 52%]
tests/test_delivery_and_recurrence.py::test_delivery_adapter_simulation_mode PASSED [ 56%]
tests/test_delivery_and_recurrence.py::test_smtp_validation_missing_host PASSED [ 60%]
tests/test_personalization.py::test_parse_raw_content_with_subject PASSED [ 64%]
tests/test_personalization.py::test_parse_raw_content_without_subject PASSED [ 68%]
tests/test_personalization.py::test_extract_placeholders PASSED          [ 72%]
tests/test_personalization.py::test_personalize_email_success PASSED     [ 76%]
tests/test_personalization.py::test_personalize_email_missing_placeholder_raises_error PASSED [ 80%]
tests/test_review_regression.py::test_reminder_due_keeps_actionable_and_records_notification PASSED [ 84%]
tests/test_review_regression.py::test_recurring_campaign_preserves_separate_occurrence_history PASSED [ 88%]
tests/test_review_regression.py::test_worker_stale_job_timeout_safety PASSED [ 92%]
tests/test_worker.py::test_worker_processes_due_campaign PASSED          [ 96%]
tests/test_worker.py::test_worker_stale_processing_recovery PASSED       [100%]
======================== 25 passed, 1 warning in 1.97s ========================
```

### B. Frontend Production Build Verification
Command executed:
```powershell
cd frontend; node ./node_modules/next/dist/bin/next build
```
**Results:** Compiled in 2.5s; all static routes and App Router bundles generated without errors (Exit Code 0).

### C. End-to-End Simulation Run
- Ingested 8 contacts and 7 reminders from sample CSVs.
- Created and scheduled a due campaign (`welcome_onboarding.txt`).
- Worker executed 4 dispatches, transitioned status to `simulated`, and exported sample audit reports to `outputs/sample_reports/`.

---

## 6. Local Runbook for Reviewers

To inspect and run the project locally:

1. **Activate Environment & Copy Configuration:**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   Copy-Item .env.example .env
   ```
2. **Terminal 1 — Start Backend Server:**
   ```powershell
   .\.venv\Scripts\python.exe main.py
   ```
   *FastAPI server runs at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.*

3. **Terminal 2 — Start Background Worker Daemon:**
   ```powershell
   .\.venv\Scripts\python.exe -m src.email_automation.scheduler.worker
   ```
   *Worker continuously polls SQLite every 5 seconds for due dispatches.*

4. **Terminal 3 — Start Next.js Dashboard:**
   ```powershell
   cd frontend
   npm run dev
   ```
   *Dashboard opens at `http://localhost:3000`.*

---

## 7. Limitations & Production Scalability Roadmap

| Component | Current Implementation (Student/Portfolio) | Enterprise Production Recommendation |
| :--- | :--- | :--- |
| **Database** | SQLite (Single file, local concurrency) | PostgreSQL with connection pooling (e.g., PgBouncer) for concurrent writes. |
| **Worker Queue** | Python `schedule` with SQLite polling | Celery or RQ backed by Redis for multi-node distributed task workers. |
| **Delivery Relay** | Simulated (`DRY_RUN=true`) / Local SMTP | Transactional Email API (SendGrid, Mailgun, Amazon SES) with TLS 1.3. |
| **Delivery Feedback** | Server acceptance status (`sent`) | Inbound webhook receivers tracking bounces, open rates, and spam complaints. |

---

## 8. Reviewer Sign-off Checklist

- [x] **Architecture:** Client-server separation with independent worker daemon verified. CORS restricted to `localhost:3000`/`127.0.0.1:3000` only.
- [x] **Due Reminders:** Reminders transition to `due` status and remain actionable; `ReminderNotificationRecord` table persists alert history.
- [x] **Recurring Campaign History:** Each campaign occurrence creates distinct `RecipientSendRecord` rows (tracked by `occurrence_number`); prior history is never overwritten.
- [x] **Worker Safety:** PID-checked lockfile prevents concurrent workers; stale jobs reset only after `STALE_JOB_TIMEOUT_SECONDS` (default 300s), not on every poll.
- [x] **SMTP Configuration:** `SMTP_AUTH_REQUIRED` flag distinguishes authenticated Gmail mode from unauthenticated relay mode; validation enforced accordingly.
- [x] **Data Hygiene:** No real credentials, secrets, or private customer data in repository.
- [x] **Safety:** Strict default simulation mode (`DRY_RUN=true`) confirmed.
- [x] **Code Quality:** Type annotations, Pydantic validation schemas, and structured error handling.
- [x] **Test Coverage:** 25/25 automated unit and integration tests passing (100%). Includes 3 new regression tests for review findings 2, 3, and 4.
- [x] **Documentation:** Comprehensive README, module breakdowns, simulation guides, and interview prep in place.

---
*Report generated and archived at:* `docs/technical_manager_report.md`
