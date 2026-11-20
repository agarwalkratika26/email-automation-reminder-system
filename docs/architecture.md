# System Architecture & Tech Stack Options

## 1. High-Level Architecture Diagram

```
+---------------------------------------------------------------------------------------+
|                               Next.js Web Dashboard                                   |
|   - Real-time Campaign / Reminder Metrics       - Contact Directory & CSV Ingestion   |
|   - Live Template Personalization Preview       - Send History & Error Inspector      |
|   - CSV Audit Report Downloader                 - Simulation Mode Active Indicator    |
+------------------------------------------+--------------------------------------------+
                                           | HTTP REST API (JSON)
                                           v
+---------------------------------------------------------------------------------------+
|                               FastAPI Backend Server                                  |
|   - /api/contacts (CRUD & CSV Import)           - /api/templates & /api/preview       |
|   - /api/campaigns (Schedule, Cancel, Retry)    - /api/reminders (CRUD, Status)       |
|   - /api/send-records (Audit Log, Filter)       - /api/reports (CSV Streamers)        |
+-------------------+-----------------------------------------------+-------------------+
                    |                                               |
                    v                                               v
+-----------------------------------------+   +-----------------------------------------+
|     Local SQLite Database Storage       |   |       Template Filesystem Store         |
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

---

## 2. Tech Stack Options Comparison

When designing an automated communication and scheduling system, three architectural tiers can be considered:

| Tier | Libraries / Tools | Difficulty | Expected Output & Scope | Best Fit For |
| :--- | :--- | :--- | :--- | :--- |
| **Easy** | Python CLI, standard CSV, `datetime`, `schedule`, `logging`, `smtplib`, `email.message`. | Beginner (1/5) | Terminal-only CLI script that reads a local CSV, substitutes strings, and prints console logs or calls localhost SMTP. | Quick personal scripts or simple automation exercises. |
| **Intermediate (Chosen)** | **FastAPI, Next.js, SQLite, SQLAlchemy, Pandas/CSV, `schedule`, `python-dateutil`, `smtplib`, `email.message`.** | Intermediate (3/5) | Full-stack runnable application with interactive web dashboard, OpenAPI backend, crash-resilient worker, and audit CSV exports. | **Portfolio proof-of-work for Python Developer, Automation, and Ops roles.** |
| **Advanced** | FastAPI, PostgreSQL, Redis, Celery / RQ worker queue, Docker, Kubernetes, Next.js. | Advanced (5/5) | Distributed microservices architecture with cloud pub/sub message brokers, distributed lock managers, and horizontal scaling. | High-throughput enterprise SaaS processing millions of emails per hour. |

### Why Intermediate is the Recommended Balance
1. **Zero External Infrastructure Required:** Uses local SQLite persistence and lightweight file storage rather than requiring Redis, PostgreSQL, or Docker daemons.
2. **Complete Separation of Concerns:** Decouples user-facing API/dashboard management from background worker processing.
3. **Safe by Design:** Defaults to simulated delivery (`DRY_RUN=true`), allowing students and interviewers to run and verify the entire system without risking accidental email dispatches or leaking credentials.
