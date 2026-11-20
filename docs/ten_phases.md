# The Ten Implementation Phases

This document details the ten sequential engineering phases used to construct the **Email Automation & Reminder System**. Each phase outlines its core objectives, architectural importance, expected output, and common mistakes beginners make.

---

### Phase 1: Environment & Virtual Setup
- **What to do:** Install Python (>=3.10) and Node.js (>=18). Create an isolated virtual environment (`.venv`) and configure `.gitignore`.
- **Why it matters:** Isolates project dependencies from the global operating system and prevents accidental commits of binary virtual environments or secrets.
- **Expected Output:** Activated `.venv` and verified clean Python/Node runtimes.
- **Beginner Mistakes:** Installing packages globally without a venv; committing `.venv` or `.env` to Git.

---

### Phase 2: Project Folder Structure Creation
- **What to do:** Establish the standard directory layout (`data/`, `templates/`, `src/email_automation/`, `frontend/`, `outputs/`, `logs/`, `docs/`).
- **Why it matters:** Clean folder separation enables modular development where backend, frontend, templates, and storage have designated boundaries.
- **Expected Output:** Complete directory tree with `.gitkeep` files in empty directories.
- **Beginner Mistakes:** Dumping all Python scripts into the root directory with no package hierarchy.

---

### Phase 3: Contact CSV Creation & Ingestion Engine
- **What to do:** Create fictional sample contact data (`data/sample_contacts.csv`) and build `CSVService` with row-by-row syntax validation and duplicate detection.
- **Why it matters:** Real-world CSV uploads frequently contain syntax errors, missing fields, and duplicate entries. A robust system must report exact row numbers and diagnostic reasons rather than crashing.
- **Expected Output:** Parser that returns total rows, imported count, updated count, and an array of invalid rows with reasons.
- **Beginner Mistakes:** Silently skipping invalid rows without notifying the user; using naive string splitting that breaks on quoted commas.

---

### Phase 4: Email Template Creation
- **What to do:** Write reusable template text files (`welcome_onboarding.txt`, `meeting_reminder.txt`, `payment_notice.txt`, `webinar_invitation.txt`) supporting `{token}` placeholders.
- **Why it matters:** Decouples message copy from backend logic, allowing non-technical business teams to edit templates freely.
- **Expected Output:** File-based templates with parsed `Subject:` headers and multi-line message bodies.
- **Beginner Mistakes:** Hardcoding email text directly into Python functions.

---

### Phase 5: Delivery Adapter & SMTP Safety Configuration
- **What to do:** Implement `DeliveryAdapter` with strict default Simulation Mode (`DRY_RUN=true`) and optional authenticated SMTP mode using `smtplib` and `EmailMessage`.
- **Why it matters:** Ensures the project can be safely demonstrated, evaluated, and tested without real email accounts, credentials, or spam risks.
- **Expected Output:** Delivery result objects capturing `simulated`, `sent`, or `failed` statuses.
- **Beginner Mistakes:** Defaulting to live sending; hardcoding SMTP passwords in code; printing passwords in logs.

---

### Phase 6: Template Personalization Engine
- **What to do:** Build `TemplateService` to parse placeholders, validate context dictionaries, and substitute values into both subject and body.
- **Why it matters:** Delivers personalized communications at scale while preventing embarrassing raw tokens like `Hello {name}` from reaching recipients.
- **Expected Output:** Fully rendered messages or descriptive `PersonalizationError` exceptions when fields are missing.
- **Beginner Mistakes:** Using simple `.replace()` which fails to detect unhandled tokens.

---

### Phase 7: Reminder & Campaign Scheduling
- **What to do:** Implement UTC-aware scheduling with recurrence calculations for `daily`, `weekly`, and `monthly` cycles using `dateutil.relativedelta`.
- **Why it matters:** Handles real-world calendar complexities (varying month lengths, leap years, timezone offsets) reliably.
- **Expected Output:** Deterministic next-run calculations and persistent SQLite job records.
- **Beginner Mistakes:** Using local system time instead of UTC; adding a fixed 30 days for monthly recurrence.

---

### Phase 8: Autonomous Worker Execution
- **What to do:** Create `SchedulerWorker` that periodically polls due campaigns and reminders, transitions job states atomically, and recovers from unexpected restarts.
- **Why it matters:** Allows scheduled dispatches to execute even when the browser dashboard is closed.
- **Expected Output:** Standalone CLI worker (`python -m src.email_automation.scheduler.worker`) processing batches safely.
- **Beginner Mistakes:** Processing jobs inside FastAPI request handlers, which blocks the web server.

---

### Phase 9: Structured Logging & CSV Report Generation
- **What to do:** Implement `ReportingService` using Pandas to export downloadable CSV audit logs for email attempts and reminder histories.
- **Why it matters:** Provides auditability and compliance proof for operations, HR, and business stakeholders.
- **Expected Output:** Filterable audit reports with recipient, timestamp, status, and error details.
- **Beginner Mistakes:** Including passwords or sensitive PII in exported audit reports.

---

### Phase 10: Next.js Dashboard & GitHub Publication
- **What to do:** Build the interactive Next.js dashboard, verify all automated tests pass, review `.gitignore`, and push clean code to GitHub.
- **Why it matters:** Delivers an impressive, complete portfolio asset with clear documentation and visual verification.
- **Expected Output:** Fully working dashboard at `http://localhost:3000` and a clean GitHub repository suitable for student portfolio submission.
- **Beginner Mistakes:** Committing `.env` or local databases; omitting local run instructions in the README.
