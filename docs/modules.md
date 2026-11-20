# System Modules & Component Specifications

## 1. Module Overview

The backend code is organized under `src/email_automation/` with strict modular boundaries:

```text
src/email_automation/
├── api/
│   ├── app.py           # FastAPI initialization, CORS, lifespan handlers
│   └── routes.py        # REST endpoints (Contacts, Campaigns, Reminders, Reports)
├── scheduler/
│   ├── recurrence.py    # Deterministic next-run datetime calculations
│   └── worker.py        # Background polling worker daemon and CLI runner
├── services/
│   ├── csv_service.py   # Pandas-powered CSV parsing and row validation
│   ├── delivery.py      # Simulation / SMTP delivery adapter
│   ├── personalization.py # Template discovery and token substitution
│   └── reporting.py     # Downloadable audit report generators
├── storage/
│   ├── database.py      # SQLAlchemy engine, session factories, init_db
│   └── models.py        # Relational models: Contact, Campaign, SendRecord, Reminder
└── config.py            # Pydantic Settings with strict DRY_RUN safety
```

---

## 2. Component Deep Dive

### Storage Layer (`storage/`)
- **`Contact`:** Stores contact details. Enforces unique, indexed emails. Tracks `is_active` status.
- **`Campaign`:** Defines campaign title, template, recurrence rule, scheduled UTC timestamp, and operational status (`pending`, `running`, `completed`, `cancelled`).
- **`RecipientSendRecord`:** Granular per-recipient dispatch log. Stores snapshots of rendered subject and body, delivery mode (`simulation` vs `smtp`), status (`queued`, `processing`, `simulated`, `sent`, `failed`), timestamps, and diagnostic error detail.
- **`Reminder`:** Personal and team task reminder model with priority (`low`, `medium`, `high`, `urgent`), assignee owner, team, and recurrence rule.

### Personalization Service (`services/personalization.py`)
- Discovers text templates in `templates/`.
- Extracts dynamic tokens (`{name}`, `{company}`, etc.) via regular expressions.
- Personalizes both subject and email body simultaneously.
- Offers `strict=True` mode to catch missing fields before scheduling.

### Delivery Adapter (`services/delivery.py`)
- Unified interface for email dispatches.
- **Simulation Mode:** Active by default (`DRY_RUN=true`). Guarantees no network packets are sent to port 25/465/587. Records `simulated` status.
- **Live SMTP Mode:** Activated strictly by explicit environment configuration. Uses Python standard `smtplib` and `email.message.EmailMessage`. Safely sanitizes credentials and logs errors gracefully without crashing the worker.

### Scheduler & Worker (`scheduler/worker.py`)
- Can run continuously as a daemon (`python -m src.email_automation.scheduler.worker`) or as a single execution cycle (`--once`).
- Uses Python `schedule` library for periodic polling.
- Idempotent and crash-resilient: automatically recovers orphaned `processing` records.
