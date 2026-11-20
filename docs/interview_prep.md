# GitHub Publishing & Technical Interview Preparation

This guide prepares developers to present and explain this project during technical interviews for Python Developer, Automation Engineer, DevOps, Operations, and Business Productivity roles.

---

## 1. The 30-Second Elevator Pitch

> *"The **Email Automation & Reminder System** is a full-stack Python application that automates business communication workflows—such as employee onboarding, meeting alerts, and payment follow-ups. Built with FastAPI, SQLite, and Next.js, it features a background worker that handles one-off and recurring schedules with crash resilience. Crucially, it defaults to a safe simulation mode so it can be evaluated end-to-end without credentials or accidental email dispatches, while providing downloadable audit CSV reports for compliance."*

---

## 2. Key Architectural Decisions & Rationale

### A. Why FastAPI over Flask or Django?
- **Automatic OpenAPI Documentation:** Interactive Swagger UI at `/docs` without external tooling.
- **Pydantic Validation:** Strict request/response validation with type safety.
- **Async & Threading Capabilities:** Fast, modern, and lightweight for service APIs.

### B. Why decouple the Scheduler Worker from the Web API?
- **Server Responsiveness:** Processing long email batches inside an API request would block HTTP threads and lead to request timeouts.
- **Reliability:** The worker runs as an independent daemon. The browser or API does not need to remain open for scheduled dispatches to execute on time.

### C. Why SQLite and File-Based Templates?
- **Zero Configuration:** Eliminates heavy external dependencies like Redis, Celery, or PostgreSQL for local development and reviewer grading.
- **Separation of Concerns:** Business users can update email templates in `templates/*.txt` without writing code or modifying database tables.

### D. Why Default Simulation Mode (`DRY_RUN=true`)?
- **Safety First:** Prevents accidental spamming, quota depletion, or credential leaks.
- **Deterministic Testing:** Automated test suites can run repeatedly in CI/CD without network mocking or external SMTP dependencies.

---

## 3. Likely Interview Questions & Answers

### Q1: How do you prevent duplicate email sends if the worker crashes mid-batch?
**Answer:** *"We use atomic state transitions in SQLite. Before attempting delivery, the worker marks the recipient record as `processing`. If the worker crashes, a recovery routine on startup resets orphaned `processing` records back to `queued`. Completed dispatches are marked `simulated` or `sent` with timestamps, ensuring they are excluded from future query filters."*

### Q2: How does the system handle variable month lengths for monthly recurring campaigns?
**Answer:** *"Instead of adding a fixed 30 days (which drifts over time), we use `python-dateutil.relativedelta`. When advancing a monthly recurrence from January 31st, `relativedelta(months=1)` correctly snaps the next run to February 28th (or 29th in a leap year), preserving exact calendar alignment."*

### Q3: What is the difference between a status of `sent` and actual inbox delivery?
**Answer:** *"A status of `sent` means the configured SMTP server accepted the RFC 5322 MIME envelope for onward relay. It does not guarantee that the message bypassed spam filters, reached the recipient's inbox, or was opened. In production systems, delivery confirmation requires webhook integrations with transactional mail providers (e.g. SendGrid or SES)."*

### Q4: How are CSV errors handled during import?
**Answer:** *"Rather than failing silently or crashing the entire batch, `CSVService` validates each row for required fields and RFC-compliant email syntax. Valid rows are persisted or updated, while invalid rows are captured in an error log with their exact CSV row numbers and specific reasons for user correction."*

---

## 4. Limitations & Future Scalability Enhancements

1. **Horizontal Worker Scaling:** In high-volume enterprise production, SQLite file locks can be replaced with PostgreSQL and Redis queues (e.g., Celery or RQ) for distributed multi-node workers.
2. **Delivery Webhooks:** Integrating SendGrid or Amazon SES webhooks to capture bounce, open, and click tracking metrics in real time.
3. **HTML Visual Template Editor:** Adding a rich-text or drag-and-drop MJML email builder to the dashboard for responsive HTML layouts.
