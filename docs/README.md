# Email Automation and Reminder System -- Technical Documentation Hub

This directory contains the complete technical documentation for the Email Automation and Reminder System. Each document covers a specific aspect of the project, from high-level architecture to implementation details.

---

## Documentation Index

| File | Contents |
| :--- | :--- |
| [technical_manager_report.md](technical_manager_report.md) | Formal project review report prepared for Technical Manager or Engineering Lead evaluation. |
| [architecture.md](architecture.md) | System architecture, ASCII diagrams, tech stack comparisons, and component relationships. |
| [data_flow.md](data_flow.md) | Ingestion pipelines, CSV row validation, template token rendering, job state transitions, and audit generation. |
| [modules.md](modules.md) | Backend module specifications, storage schemas, worker mechanics, and API routes. |
| [ten_phases.md](ten_phases.md) | 10-phase implementation walkthrough with rationale, expected outputs, and common pitfalls. |
| [virtual_simulation_guide.md](virtual_simulation_guide.md) | Safe dry-run testing guide, sample data walkthrough, CSV report verification, and transition to live SMTP. |
| [interview_prep.md](interview_prep.md) | Project pitch, architectural decisions, anticipated technical interview questions and answers. |
| [execution_log.md](execution_log.md) | Implementation journal recording test runs, validation checks, and component verification. |

---

## Core System Overview

The Email Automation and Reminder System is a portfolio-ready Python application designed for automating repetitive communications across HR, Operations, Sales, and Admin functions. It features:

- **FastAPI API** with OpenAPI documentation available at `/docs`.
- **Next.js Dashboard** with real-time counters, template preview, CSV uploader, and history inspector.
- **Local SQLite Persistence** for contacts, campaigns, reminders, and recipient send records.
- **Independent Scheduler Worker** running periodic polling cycles with idempotency and crash recovery.
- **Safe Simulation Delivery (DRY_RUN=true)** by default, requiring zero email accounts or external credentials.
