"""
Background Scheduler & Execution Worker.

Polls local SQLite database for due campaigns and reminders.
Features:
- Single-worker process locking to prevent multiple workers conflicting on the database.
- Safe timeout-based stale job recovery (only recovers jobs exceeding STALE_JOB_TIMEOUT_SECONDS).
- Atomic conditional job claiming to prevent duplicate dispatching.
- Complete recurrence history preservation: creates distinct per-recipient records for each occurrence
  without overwriting past runs.
- Reminders remain actionable in 'due' status with persistent ReminderNotificationRecord history.
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime, timezone, timedelta
from typing import Optional
import schedule
from sqlalchemy.orm import Session

from src.email_automation.config import settings
from src.email_automation.storage.database import SessionLocal, init_db
from src.email_automation.storage.models import (
    Campaign, RecipientSendRecord, Reminder, ReminderNotificationRecord, Contact, get_utc_now
)
from src.email_automation.services.delivery import DeliveryAdapter
from src.email_automation.services.personalization import TemplateService
from src.email_automation.scheduler.recurrence import compute_next_run


# Configure structured logging for worker
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(settings.LOGS_DIR / "worker.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("email_automation.worker")


class WorkerProcessLock:
    """
    Ensures only a single worker instance runs against the local database at a time.
    Uses a PID-checked lockfile to detect active or crashed worker processes.
    """
    def __init__(self, lock_file_path: Optional[str] = None):
        self.lock_file = settings.LOGS_DIR / (lock_file_path or settings.WORKER_LOCK_FILE)

    def is_pid_running(self, pid: int) -> bool:
        """Checks if a process with given PID is currently active."""
        if pid <= 0:
            return False
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            process = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if process != 0:
                kernel32.CloseHandle(process)
                return True
            return False
        else:
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False

    def acquire(self) -> bool:
        """Acquires process lock. Returns True if acquired, False if another worker is running."""
        current_pid = os.getpid()
        if self.lock_file.exists():
            try:
                content = self.lock_file.read_text(encoding="utf-8").strip()
                existing_pid = int(content.split(":")[0])
                if self.is_pid_running(existing_pid) and existing_pid != current_pid:
                    logger.error(
                        f"Another worker daemon (PID {existing_pid}) is already active. "
                        f"Cannot start multiple concurrent workers."
                    )
                    return False
                else:
                    logger.warning(f"Found stale lockfile from dead PID {existing_pid}. Overwriting lock.")
            except Exception:
                pass

        try:
            self.lock_file.write_text(f"{current_pid}:{datetime.now(timezone.utc).isoformat()}", encoding="utf-8")
            return True
        except Exception as e:
            logger.error(f"Failed to write worker lockfile: {e}")
            return False

    def release(self) -> None:
        """Releases the process lock file upon graceful exit."""
        try:
            if self.lock_file.exists():
                self.lock_file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Could not remove lockfile on exit: {e}")


class SchedulerWorker:
    """Worker service that polls and processes scheduled campaigns and reminders."""

    def __init__(self, db_factory=SessionLocal):
        self.db_factory = db_factory
        self.template_service = TemplateService()

    def recover_stale_processing(self, db: Session) -> int:
        """
        Safe timeout-based stale job recovery.
        ONLY resets jobs whose last_attempt_at is older than STALE_JOB_TIMEOUT_SECONDS.
        Does NOT touch active jobs currently being dispatched.
        """
        now = get_utc_now()
        stale_cutoff = now - timedelta(seconds=settings.STALE_JOB_TIMEOUT_SECONDS)

        stale_records = db.query(RecipientSendRecord).filter(
            RecipientSendRecord.status == "processing",
            (
                (RecipientSendRecord.last_attempt_at.is_(None)) |
                (RecipientSendRecord.last_attempt_at < stale_cutoff)
            )
        ).all()

        recovered_count = 0
        if stale_records:
            logger.warning(
                f"Found {len(stale_records)} abandoned 'processing' records older than "
                f"{settings.STALE_JOB_TIMEOUT_SECONDS}s. Resetting them to 'queued'."
            )
            for record in stale_records:
                record.status = "queued"
                recovered_count += 1
            db.commit()

        return recovered_count

    def process_due_campaigns(self, db: Session) -> int:
        """
        Finds campaigns due for execution and dispatches recipient emails.
        Preserves complete history for recurring runs by creating distinct records for each occurrence.
        """
        now = get_utc_now()

        due_campaigns = db.query(Campaign).filter(
            Campaign.status.in_(["pending", "running"]),
            (
                ((Campaign.next_run_at.is_(None)) & (Campaign.scheduled_at <= now)) |
                (Campaign.next_run_at <= now)
            )
        ).all()

        processed_count = 0

        for campaign in due_campaigns:
            campaign.status = "running"
            db.commit()

            # Query queued records strictly for the current occurrence
            queued_candidates = db.query(RecipientSendRecord).filter(
                RecipientSendRecord.campaign_id == campaign.id,
                RecipientSendRecord.occurrence_number == campaign.current_run_number,
                RecipientSendRecord.status == "queued"
            ).limit(settings.BATCH_SEND_SIZE).all()

            if not queued_candidates:
                # Check if there are any records still processing for this occurrence
                in_flight = db.query(RecipientSendRecord).filter(
                    RecipientSendRecord.campaign_id == campaign.id,
                    RecipientSendRecord.occurrence_number == campaign.current_run_number,
                    RecipientSendRecord.status.in_(["queued", "processing"])
                ).count()

                if in_flight == 0:
                    # Current occurrence is finished
                    campaign.last_run_at = now
                    if campaign.recurrence and campaign.recurrence != "one-off":
                        next_run = compute_next_run(now, campaign.recurrence)
                        campaign.next_run_at = next_run
                        campaign.current_run_number += 1
                        campaign.status = "pending"
                        logger.info(
                            f"Campaign #{campaign.id} completed occurrence {campaign.current_run_number - 1}. "
                            f"Rescheduling occurrence #{campaign.current_run_number} for {next_run.isoformat()}"
                        )

                        # Create DISTINCT records for the new occurrence (do NOT overwrite past history!)
                        prior_occurrence_records = db.query(RecipientSendRecord).filter(
                            RecipientSendRecord.campaign_id == campaign.id,
                            RecipientSendRecord.occurrence_number == 1
                        ).all()

                        for prior in prior_occurrence_records:
                            new_rec = RecipientSendRecord(
                                campaign_id=campaign.id,
                                contact_id=prior.contact_id,
                                occurrence_number=campaign.current_run_number,
                                recipient_email=prior.recipient_email,
                                recipient_name=prior.recipient_name,
                                rendered_subject=prior.rendered_subject,
                                rendered_body=prior.rendered_body,
                                status="queued",
                                delivery_mode="simulation" if settings.DRY_RUN else "smtp"
                            )
                            db.add(new_rec)
                    else:
                        campaign.status = "completed"
                        campaign.next_run_at = None
                        logger.info(f"One-off Campaign #{campaign.id} marked as completed.")
                    db.commit()
                continue

            for candidate in queued_candidates:
                # Conditional atomic claim: only update if status is still 'queued'
                claimed = db.query(RecipientSendRecord).filter(
                    RecipientSendRecord.id == candidate.id,
                    RecipientSendRecord.status == "queued"
                ).update({
                    "status": "processing",
                    "attempt_count": RecipientSendRecord.attempt_count + 1,
                    "last_attempt_at": now
                }, synchronize_session=False)
                db.commit()

                if not claimed:
                    # Job claimed by concurrent poll/worker
                    continue

                # Refresh instance
                db.refresh(candidate)

                # Execute dispatch via DeliveryAdapter
                result = DeliveryAdapter.send_email(
                    to_email=candidate.recipient_email,
                    to_name=candidate.recipient_name,
                    subject=candidate.rendered_subject,
                    body=candidate.rendered_body
                )

                candidate.status = result.status
                candidate.delivery_mode = result.mode
                candidate.completed_at = get_utc_now()
                candidate.error_detail = result.error_detail
                db.commit()

                processed_count += 1
                logger.info(
                    f"SendRecord #{candidate.id} [Camp #{campaign.id} Occ #{candidate.occurrence_number}] "
                    f"-> {result.status.upper()} (Attempt {candidate.attempt_count})"
                )

        return processed_count

    def process_due_reminders(self, db: Session) -> int:
        """
        Transitions due reminders to 'due' status, records a persistent ReminderNotificationRecord,
        and keeps the reminder visible and actionable in the dashboard until user action.
        """
        now = get_utc_now()
        due_reminders = db.query(Reminder).filter(
            Reminder.status == "pending",
            Reminder.due_time <= now
        ).all()

        count = 0
        for reminder in due_reminders:
            logger.info(
                f"[REMINDER DUE] ID: {reminder.id} | Title: '{reminder.title}' | "
                f"Owner: {reminder.owner} | Team: {reminder.team} | Priority: {reminder.priority.upper()}"
            )
            reminder.status = "due"
            reminder.last_notified_at = now

            # Persist notification history log
            notification = ReminderNotificationRecord(
                reminder_id=reminder.id,
                notified_at=now,
                notification_type="due_alert",
                status="pending_action",
                detail=(
                    f"Reminder '{reminder.title}' reached due time ({reminder.due_time.isoformat()}). "
                    f"Owner: {reminder.owner}, Priority: {reminder.priority}."
                )
            )
            db.add(notification)
            db.commit()
            count += 1

        return count

    def run_cycle(self) -> dict:
        """Executes a single polling and processing cycle for due jobs."""
        db = self.db_factory()
        try:
            stale_recovered = self.recover_stale_processing(db)
            emails_processed = self.process_due_campaigns(db)
            reminders_notified = self.process_due_reminders(db)
            return {
                "stale_recovered": stale_recovered,
                "emails_processed": emails_processed,
                "reminders_notified": reminders_notified,
                "timestamp": get_utc_now().isoformat()
            }
        finally:
            db.close()

    def start_polling(self) -> None:
        """
        Continuous worker loop using Python schedule library.
        Enforces single-worker process locking.
        """
        lock = WorkerProcessLock()
        if not lock.acquire():
            logger.error("Exiting worker startup due to active lockfile.")
            sys.exit(1)

        logger.info(
            f"Starting Email Automation Worker (Polling interval: {settings.WORKER_POLL_INTERVAL_SECONDS}s, "
            f"Dry Run Mode: {settings.DRY_RUN}, Stale Timeout: {settings.STALE_JOB_TIMEOUT_SECONDS}s)"
        )

        schedule.every(settings.WORKER_POLL_INTERVAL_SECONDS).seconds.do(self.run_cycle)
        self.run_cycle()

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Worker process received shutdown signal. Exiting gracefully.")
        finally:
            lock.release()


def main():
    parser = argparse.ArgumentParser(description="Email Automation & Reminder System Worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll/execution cycle and exit (useful for automated testing or cron triggers)"
    )
    args = parser.parse_args()

    init_db()

    worker = SchedulerWorker()
    if args.once:
        logger.info("Running single worker execution cycle...")
        result = worker.run_cycle()
        logger.info(f"Cycle completed: {result}")
    else:
        worker.start_polling()


if __name__ == "__main__":
    main()
