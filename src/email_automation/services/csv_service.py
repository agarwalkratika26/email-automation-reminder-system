"""
CSV Parsing & Validation Service.

Validates and imports Contact and Reminder records from CSV files or strings.
Produces transparent row-by-row error logs without silently discarding records.
Uses Pandas and Python standard csv library for robust format parsing.
"""

import io
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
import pandas as pd
from dateutil import parser as date_parser
from sqlalchemy.orm import Session
from src.email_automation.storage.models import Contact, Reminder, get_utc_now


# Standard RFC 5322 compatible basic email validation pattern
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class CSVValidationError(Exception):
    """Raised when CSV structure is invalid."""
    pass


class CSVService:
    """Service for validating, parsing, and ingesting CSV data."""

    @staticmethod
    def validate_email_syntax(email: str) -> bool:
        """Validates email format syntax."""
        if not email or not isinstance(email, str):
            return False
        return bool(EMAIL_REGEX.match(email.strip()))

    @classmethod
    def import_contacts_csv(
        cls,
        csv_content: str,
        db: Session,
        update_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Parses contacts CSV, validates row by row, and saves valid records to the database.
        
        Required header:
          - email
          - name
        Optional headers:
          - company, role, department
        
        Returns:
          Summary dict with total, imported, updated, skipped, and invalid_rows details.
        """
        try:
            # Read CSV using pandas to handle quoted commas, whitespace, and varied line breaks
            df = pd.read_csv(io.StringIO(csv_content), dtype=str, keep_default_na=False)
        except Exception as e:
            raise CSVValidationError(f"Could not parse CSV format: {str(e)}")

        # Normalize column headers
        df.columns = [col.strip().lower() for col in df.columns]

        # Check required columns
        required_cols = {"email", "name"}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise CSVValidationError(
                f"Missing required columns in CSV header: {', '.join(sorted(missing_cols))}. "
                f"Found columns: {', '.join(df.columns)}"
            )

        total_rows = len(df)
        imported_count = 0
        updated_count = 0
        skipped_count = 0
        invalid_rows: List[Dict[str, Any]] = []

        # Track emails within this CSV batch to avoid internal duplicates
        seen_batch_emails = set()

        for idx, row in df.iterrows():
            row_number = int(idx) + 2  # +2 accounts for 1-based indexing and header row
            email_val = row.get("email", "").strip()
            name_val = row.get("name", "").strip()
            company_val = row.get("company", "").strip()
            role_val = row.get("role", "").strip()
            department_val = row.get("department", "").strip()

            # Row-level validation
            reasons = []
            if not email_val:
                reasons.append("Email field is empty")
            elif not cls.validate_email_syntax(email_val):
                reasons.append(f"Invalid email syntax '{email_val}'")

            if not name_val:
                reasons.append("Name field is empty")

            normalized_email = email_val.lower()
            if normalized_email in seen_batch_emails:
                reasons.append(f"Duplicate email '{email_val}' within the same CSV upload")

            if reasons:
                invalid_rows.append({
                    "row_number": row_number,
                    "email": email_val,
                    "name": name_val,
                    "reason": "; ".join(reasons)
                })
                continue

            seen_batch_emails.add(normalized_email)

            # Check database for existing contact
            existing = db.query(Contact).filter(Contact.email == normalized_email).first()
            if existing:
                if update_existing:
                    existing.name = name_val
                    existing.company = company_val
                    existing.role = role_val
                    existing.department = department_val
                    existing.is_active = True
                    existing.updated_at = get_utc_now()
                    updated_count += 1
                else:
                    skipped_count += 1
            else:
                new_contact = Contact(
                    email=normalized_email,
                    name=name_val,
                    company=company_val,
                    role=role_val,
                    department=department_val,
                    is_active=True
                )
                db.add(new_contact)
                imported_count += 1

        db.commit()

        return {
            "total_rows": total_rows,
            "imported": imported_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "invalid_count": len(invalid_rows),
            "invalid_rows": invalid_rows
        }

    @classmethod
    def import_reminders_csv(
        cls,
        csv_content: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Parses reminders CSV, validates dates and required fields, and creates records.
        
        Required headers:
          - title
          - due_time (ISO 8601 or parseable datetime string)
          - owner
        Optional headers:
          - description, team, recurrence, priority
        """
        try:
            df = pd.read_csv(io.StringIO(csv_content), dtype=str, keep_default_na=False)
        except Exception as e:
            raise CSVValidationError(f"Could not parse Reminders CSV format: {str(e)}")

        df.columns = [col.strip().lower() for col in df.columns]

        required_cols = {"title", "due_time", "owner"}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise CSVValidationError(
                f"Missing required columns in CSV header: {', '.join(sorted(missing_cols))}. "
                f"Found columns: {', '.join(df.columns)}"
            )

        total_rows = len(df)
        imported_count = 0
        invalid_rows: List[Dict[str, Any]] = []

        valid_recurrences = {"one-off", "daily", "weekly", "monthly"}
        valid_priorities = {"low", "medium", "high", "urgent"}

        for idx, row in df.iterrows():
            row_number = int(idx) + 2
            title_val = row.get("title", "").strip()
            due_time_raw = row.get("due_time", "").strip()
            owner_val = row.get("owner", "").strip()
            desc_val = row.get("description", "").strip()
            team_val = row.get("team", "").strip() or "General"
            rec_val = row.get("recurrence", "one-off").strip().lower() or "one-off"
            prio_val = row.get("priority", "medium").strip().lower() or "medium"

            reasons = []
            if not title_val:
                reasons.append("Title field is empty")
            if not owner_val:
                reasons.append("Owner field is empty")

            # Parse datetime
            parsed_due_time = None
            if not due_time_raw:
                reasons.append("Due time field is empty")
            else:
                try:
                    parsed_due_time = date_parser.parse(due_time_raw)
                    # Ensure UTC timezone awareness
                    if parsed_due_time.tzinfo is None:
                        parsed_due_time = parsed_due_time.replace(tzinfo=timezone.utc)
                    else:
                        parsed_due_time = parsed_due_time.astimezone(timezone.utc)
                except Exception:
                    reasons.append(f"Cannot parse datetime '{due_time_raw}'. Use ISO format (e.g., 2026-11-25T14:00:00Z)")

            if rec_val not in valid_recurrences:
                reasons.append(f"Invalid recurrence '{rec_val}'. Must be one of: {', '.join(sorted(valid_recurrences))}")

            if prio_val not in valid_priorities:
                reasons.append(f"Invalid priority '{prio_val}'. Must be one of: {', '.join(sorted(valid_priorities))}")

            if reasons:
                invalid_rows.append({
                    "row_number": row_number,
                    "title": title_val,
                    "owner": owner_val,
                    "due_time": due_time_raw,
                    "reason": "; ".join(reasons)
                })
                continue

            new_reminder = Reminder(
                title=title_val,
                description=desc_val,
                due_time=parsed_due_time,
                owner=owner_val,
                team=team_val,
                recurrence=rec_val,
                priority=prio_val,
                status="pending"
            )
            db.add(new_reminder)
            imported_count += 1

        db.commit()

        return {
            "total_rows": total_rows,
            "imported": imported_count,
            "invalid_count": len(invalid_rows),
            "invalid_rows": invalid_rows
        }
