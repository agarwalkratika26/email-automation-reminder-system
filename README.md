# Email Automation and Reminder System

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/deploy?repository=https://github.com/agarwalkratika26/email-automation-reminder-system&branch=main&mainModule=streamlit_app.py)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/agarwalkratika26/email-automation-reminder-system)
[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/agarwalkratika26/email-automation-reminder-system&root-directory=frontend)

A local Python application for scheduling and managing one-off or recurring email campaigns and personal or team reminders. Built with FastAPI, Next.js, and SQLite as a student portfolio project suitable for Python Developer, Automation Engineer, Operations, HR, and Business Productivity roles.

The system operates in **Simulation Mode** by default. All emails are personalized, validated, scheduled, and recorded with full audit trails without requiring an email account or sending real emails. Live SMTP delivery is available as an optional, explicitly configured mode.

---

## Table of Contents

1. [Features](#features)
2. [Architecture Overview](#architecture-overview)
3. [Technology Stack](#technology-stack)
4. [Project Structure](#project-structure)
5. [Prerequisites](#prerequisites)
6. [Installation](#installation)
7. [Running the Application](#running-the-application)
8. [Usage Guide](#usage-guide)
9. [Configuration Reference](#configuration-reference)
10. [Testing](#testing)
11. [Screenshots](#screenshots)
12. [Technical Documentation](#technical-documentation)
13. [Known Limitations](#known-limitations)
14. [License](#license)

---

## Features

**Contact Management**
- Import contacts from CSV files with row-level validation and duplicate detection.
- Create, read, update, and delete contacts through the API and dashboard.
- Email address syntax validation following RFC 5322 conventions.
- Clear error reporting with row numbers and reasons for invalid entries.

**Email Campaigns**
- Create one-off and recurring campaigns (daily, weekly, monthly).
- Load reusable email templates from the `templates/` directory.
- Personalize both subject and body using documented placeholders such as `{name}` and `{company}`.
- Preview rendered emails in the dashboard before scheduling.
- Detect missing fields or unknown placeholders and show actionable errors.

**Reminders**
- Create, view, update, complete, and cancel personal and team reminders.
- Import reminders from CSV with validation.
- Support for priority levels (low, medium, high, urgent) and recurrence.
- Due reminders remain actionable until a user explicitly completes or dismisses them.
- Notification history is persisted for audit purposes.

**Delivery System**
- Simulation mode (default): records all sends as `simulated` without opening any network connection.
- SMTP mode (optional): uses Python `smtplib` and `email.message.EmailMessage` with configurable TLS/SSL.
- Supports both authenticated SMTP (Gmail, SendGrid) and unauthenticated local relays (MailHog, Postfix).
- Per-recipient send records track status as `queued`, `processing`, `simulated`, `sent`, or `failed`.
- Each recurring campaign occurrence creates distinct send records; prior history is never overwritten.

**Scheduler and Worker**
- Separate background worker process that polls SQLite for due jobs every 5 seconds.
- Scheduled jobs are processed even if the dashboard browser tab is closed.
- PID-checked lockfile prevents concurrent worker instances.
- Stale job recovery with configurable timeout (default 300 seconds).
- Atomic status transitions prevent duplicate sends on restart.

**Reporting**
- Downloadable CSV reports for email send history and reminder activity.
- Reports include campaign/reminder ID, recipient, scheduled time, attempt time, status, and error detail.
- No secrets or unnecessary personal data included in reports.

**Dashboard**
- Overview with campaign and reminder counts and recent activity.
- Contact list with CSV import and validation result display.
- Campaign creation with template preview and recurrence controls.
- Reminder management with due/completed/dismissed status tracking.
- Send history with status filters and error visibility.
- CSV report download.
- Visible indicator when simulated delivery is active.

---

## Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                            Next.js 15 Web Dashboard                               |
|   - Campaign and Reminder Metrics          - Contact Directory and CSV Ingestion  |
|   - Live Template Personalization Preview  - Send History and Error Inspector     |
|   - CSV Audit Report Downloader            - Simulation Mode Active Indicator     |
+------------------------------------------+----------------------------------------+
                                           | HTTP REST API (JSON)
                                           v
+-----------------------------------------------------------------------------------+
|                             FastAPI Backend Server                                 |
|   - /api/contacts (CRUD and CSV Import)        - /api/templates and /api/preview  |
|   - /api/campaigns (Schedule, Cancel, Retry)   - /api/reminders (CRUD, Status)    |
|   - /api/send-records (Audit Log, Filter)      - /api/reports (CSV Export)        |
+-----------------+-------------------------------------------------+---------------+
                  |                                                 |
                  v                                                 v
+-------------------------------------+   +-------------------------------------+
|   Local SQLite Database Storage     |   |    Template Filesystem Store        |
|  - contacts (unique email indexed)  |   |  - templates/*.txt                  |
|  - campaigns (recurrence, schedule) |   |  - Subject header parsing           |
|  - recipient_send_records (audit)   |   |  - Placeholder: {name}, {company}   |
|  - reminders (personal and team)    |   +-------------------------------------+
|  - reminder_notification_records    |
+-----------------+-------------------+
                  ^
                  | Polling and State Updates (every 5 seconds)
+-----------------+-------------------------------------------------------------+
|                     Autonomous Python Scheduler / Worker                       |
|   - Recurrence: one-off, daily (+1d), weekly (+7d), monthly (+1m)             |
|   - Stale Recovery: timeout-based reset of abandoned processing jobs          |
|   - Batch Dispatcher: atomic transitions (queued > processing > simulated)    |
+------------------------------------------+------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                             Delivery Adapter Layer                                |
|                                                                                   |
|   [DRY_RUN=true (Default)]                      [DRY_RUN=false (Explicit)]        |
|   - Simulation Mode                             - Live Authenticated SMTP         |
|   - No network socket opened                    - smtplib + EmailMessage (MIME)   |
|   - Status: simulated                           - TLS / SSL transport             |
|   - Safe for demos and grading                  - Status: sent or failed          |
+-----------------------------------------------------------------------------------+
```

For detailed architecture documentation, see [docs/architecture.md](docs/architecture.md).

---

## Technology Stack

| Component | Technology |
| :--- | :--- |
| Backend API | Python 3.10+, FastAPI, Uvicorn |
| Database | SQLite via SQLAlchemy ORM |
| Scheduler | Python `schedule` library with SQLite polling |
| Email Construction | `smtplib`, `email.message.EmailMessage` |
| CSV Processing | Pandas |
| Recurrence Logic | `python-dateutil` (relativedelta) |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Testing | pytest |

---

## Project Structure

```
Email-Automation-Reminder-System/
|-- data/                               # Sample CSV data for testing
|   |-- sample_contacts.csv             # Fictional corporate contacts
|   +-- sample_reminders.csv            # Fictional operational reminders
|-- templates/                          # File-based email templates
|   |-- welcome_onboarding.txt          # New hire welcome template
|   |-- meeting_reminder.txt            # Operational sync reminder
|   |-- payment_notice.txt              # Billing notice
|   |-- webinar_invitation.txt          # Briefing invite
|   +-- task_deadline.txt               # Deadline notice
|-- src/                                # Backend Python package
|   +-- email_automation/
|       |-- api/
|       |   |-- app.py                  # FastAPI app, lifespan, CORS
|       |   +-- routes.py              # REST API route handlers
|       |-- scheduler/
|       |   |-- recurrence.py           # Recurrence calculations
|       |   +-- worker.py              # Polling worker daemon
|       |-- services/
|       |   |-- csv_service.py          # CSV parsing and validation
|       |   |-- delivery.py            # Simulation and SMTP adapter
|       |   |-- personalization.py     # Template rendering
|       |   +-- reporting.py           # Audit CSV export
|       |-- storage/
|       |   |-- database.py            # SQLAlchemy engine and sessions
|       |   +-- models.py             # ORM models
|       +-- config.py                  # Pydantic settings
|-- frontend/                           # Next.js 15 web dashboard
|   |-- src/app/                        # App Router pages and layout
|   |-- package.json                    # Frontend dependencies
|   +-- tsconfig.json                  # TypeScript configuration
|-- images/                             # Screenshots and diagrams (see below)
|-- docs/                               # Technical documentation
|-- tests/                              # Automated test suite
|-- outputs/                            # Exported CSV reports (gitkeep tracked)
|-- logs/                               # Runtime logs (gitkeep tracked)
|-- main.py                             # Backend server entry point
|-- requirements.txt                    # Python dependencies
|-- pytest.ini                          # Pytest configuration
|-- .env.example                        # Environment variable template
|-- .gitignore                          # Files excluded from version control
|-- LICENSE                             # MIT License
+-- README.md                          # This file
```

---

## Prerequisites

- **Python**: 3.10 or later. Verify with `python --version`.
- **Node.js**: 18.0 or later. Verify with `node --version`.
- **npm**: Included with Node.js. Verify with `npm --version`.
- **Git**: Required for cloning. Verify with `git --version`.

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/Email-Automation-Reminder-System.git
cd Email-Automation-Reminder-System
```

### 2. Set Up Python Virtual Environment

Windows PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Configure Environment

```bash
cp .env.example .env
```

On Windows PowerShell: `Copy-Item .env.example .env`

The default configuration uses `DRY_RUN=true` (simulation mode). No email credentials are needed to run the project.

---

## Running the Application

The system requires three separate terminal windows running simultaneously.

### Terminal 1: Backend API Server

```bash
# Windows
.\.venv\Scripts\python.exe main.py

# macOS / Linux
python main.py
```

The API starts at `http://localhost:8000`. Interactive API documentation is available at `http://localhost:8000/docs`.

### Terminal 2: Background Scheduler Worker

```bash
# Windows
.\.venv\Scripts\python.exe -m src.email_automation.scheduler.worker

# macOS / Linux
python -m src.email_automation.scheduler.worker
```

The worker polls the database every 5 seconds for due campaigns and reminders.

### Terminal 3: Next.js Dashboard

```bash
cd frontend
npm run dev
```

Open your browser and navigate to `http://localhost:3000`.

### Stopping

Press `Ctrl+C` in each terminal window. Run `deactivate` to exit the Python virtual environment.

---

## Usage Guide

1. Open the dashboard at `http://localhost:3000`.
2. Navigate to the Contacts section and upload `data/sample_contacts.csv`.
3. Navigate to Campaigns, select a template (such as `welcome_onboarding.txt`), and select contacts.
4. Use the template preview to verify personalized content before scheduling.
5. Set the schedule time and recurrence (one-off, daily, weekly, or monthly), then create the campaign.
6. The worker terminal will process due campaigns automatically. You can also trigger a manual cycle from the dashboard.
7. Check the Send History section to inspect rendered dispatches. All records will show status `SIMULATED` in default mode.
8. Download audit reports from the Reports section as CSV files.

For a complete simulation walkthrough, see [docs/virtual_simulation_guide.md](docs/virtual_simulation_guide.md).

---

## Configuration Reference

All configuration is managed through environment variables in the `.env` file. The `.env.example` file documents every available setting.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DRY_RUN` | `true` | When true, emails are simulated. Set to `false` only after configuring SMTP. |
| `APP_ENV` | `development` | Application environment identifier. |
| `API_HOST` | `127.0.0.1` | Backend server bind address. |
| `API_PORT` | `8000` | Backend server port. |
| `SMTP_AUTH_REQUIRED` | `true` | Set to `false` for unauthenticated local relays (MailHog, Postfix). |
| `SMTP_HOST` | `smtp.example.com` | SMTP server hostname. |
| `SMTP_PORT` | `587` | SMTP server port. |
| `SMTP_USERNAME` | (empty) | SMTP login username. Required when `SMTP_AUTH_REQUIRED=true`. |
| `SMTP_PASSWORD` | (empty) | SMTP login password. Required when `SMTP_AUTH_REQUIRED=true`. |
| `SMTP_FROM_EMAIL` | `no-reply@example.com` | Sender email address. |
| `SMTP_USE_TLS` | `true` | Enable STARTTLS. |
| `SMTP_USE_SSL` | `false` | Enable SSL/TLS on connect. |
| `WORKER_POLL_INTERVAL_SECONDS` | `5` | How often the worker checks for due jobs. |
| `STALE_JOB_TIMEOUT_SECONDS` | `300` | Grace period before abandoned processing jobs are recovered. |

**Important**: The `.env` file is excluded from version control by `.gitignore`. Never commit real credentials. The `.env.example` file contains only placeholder values.

**Note on "sent" status**: A status of `sent` indicates that the configured SMTP server accepted the message. It does not confirm that the email was delivered to the recipient's inbox or that the recipient read it.

### Date and Time Format

Campaign schedule times and reminder due times are stored as UTC-aware ISO 8601 timestamps. The dashboard displays times in the user's local timezone. When submitting times through the API, use the format `YYYY-MM-DDTHH:MM:SS` (interpreted as UTC) or include a timezone offset such as `YYYY-MM-DDTHH:MM:SS+05:30`.

### Recurrence Rules

| Recurrence | Next Run Calculation |
| :--- | :--- |
| `one-off` | No next run. Campaign is marked completed after execution. |
| `daily` | Previous run + 1 day. |
| `weekly` | Previous run + 7 days. |
| `monthly` | Previous run + 1 calendar month (uses `relativedelta` for accurate month-end handling). |

---

## Testing

The project includes 25 automated tests covering template parsing, CSV validation, recurrence calculations, delivery adapter safety, worker execution, crash recovery, and API endpoints.

Run the test suite:

```bash
# Windows
.\.venv\Scripts\pytest.exe -v

# macOS / Linux
pytest -v
```

Expected output:

```
======================== 25 passed, 1 warning in 1.97s ========================
```

All tests run in simulation mode. No SMTP connections are made during testing.

Run the frontend production build to verify:

```bash
cd frontend
npx next build
```

---

## Screenshots

### Web Dashboard Interface

#### 1. Dashboard Overview and Metrics
![Dashboard Overview](images/web%20interface/interafce1.png)

#### 2. Contact Directory and CSV Validation
![Contact Directory](images/web%20interface/interface%202.png)

#### 3. Campaign Scheduling and Live Template Preview
![Campaign Scheduling](images/web%20interface/interface%203.png)

#### 4. Personal and Team Reminders Management
![Reminders Management](images/web%20interface/interface%204.png)

#### 5. Send History and Delivery Audit Log
![Send History](images/web%20interface/interface5.png)

#### 6. Compliance and Activity CSV Reports
![Report Downloads](images/web%20interface/interface%206.png)

### System Execution and Verification

#### System Overview and Terminal Activity
![System Execution View 1](images/github/Screenshot%202026-11-21%20025718.png)

![System Execution View 2](images/github/Screenshot%202026-11-21%20025731.png)

![System Execution View 3](images/github/Screenshot%202026-11-21%20025745.png)

![System Execution View 4](images/github/Screenshot%202026-11-21%20025806.png)

![System Execution View 5](images/github/Screenshot%202026-11-21%20025819.png)

![System Execution View 6](images/github/Screenshot%202026-11-21%20025836.png)

---

## Technical Documentation

The `docs/` directory contains detailed technical documentation:

| Document | Description |
| :--- | :--- |
| [Technical Manager Report](docs/technical_manager_report.md) | Formal engineering review report with test results and sign-off checklist. |
| [Architecture](docs/architecture.md) | System architecture, component relationships, and design decisions. |
| [Data Flow](docs/data_flow.md) | Data pipeline from CSV ingestion through delivery and reporting. |
| [Modules](docs/modules.md) | Backend module specifications and API route documentation. |
| [Implementation Phases](docs/ten_phases.md) | 10-phase build walkthrough with rationale and common pitfalls. |
| [Simulation Guide](docs/virtual_simulation_guide.md) | Step-by-step guide for safe demonstration and testing. |
| [Interview Preparation](docs/interview_prep.md) | Project pitch, technical questions, and suggested answers. |
| [Execution Log](docs/execution_log.md) | Build verification journal with test run records. |

---

## Known Limitations

1. **SQLite single-writer constraint**: SQLite supports one writer at a time. Concurrent writes from the API and worker may queue briefly. This is acceptable for local use but would require PostgreSQL for multi-user production deployment.

2. **Delivery feedback**: A status of `sent` reflects SMTP server acceptance only. Bounce tracking, open rates, and spam folder detection are outside the scope of this project. Production systems would use transactional email APIs (SendGrid, Amazon SES) with webhook receivers.

3. **Worker must be started manually**: The scheduler worker runs as a foreground Python process. No OS-level service manager, systemd unit, or Windows service is included. The worker must be running for scheduled jobs to be processed.

4. **No authentication on the API**: The FastAPI backend has no login or authentication layer. It is designed for local or localhost use only. CORS is restricted to `localhost:3000` and `127.0.0.1:3000`.

5. **Local project scope**: This project is designed as a student portfolio piece and local automation tool. It is not configured for cloud deployment, containerization, or multi-tenant use without additional infrastructure.

---

## License

MIT License. See [LICENSE](LICENSE) for the full text.
