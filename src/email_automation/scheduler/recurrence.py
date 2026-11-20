"""
Recurrence Calculation Service.

Calculates deterministic next run timestamps for recurring jobs.
Supports:
  - one-off: No subsequent run (returns None)
  - daily: Advances by exactly 1 day
  - weekly: Advances by exactly 7 days
  - monthly: Advances by 1 calendar month, handling variable month lengths (28, 30, 31 days)
"""

from datetime import datetime, timezone
from typing import Optional
from dateutil.relativedelta import relativedelta


VALID_RECURRENCES = {"one-off", "daily", "weekly", "monthly"}


def compute_next_run(current_run: datetime, recurrence: str) -> Optional[datetime]:
    """
    Computes the next scheduled UTC execution time given the current run time and recurrence rule.
    
    Rules:
    - 'one-off': Returns None (no future runs).
    - 'daily': current_run + 1 day
    - 'weekly': current_run + 7 days
    - 'monthly': current_run + 1 calendar month (e.g., Jan 31 -> Feb 28/29)
    
    Ensures the resulting datetime is timezone-aware in UTC.
    """
    if not recurrence or recurrence.lower() == "one-off":
        return None

    # Ensure UTC timezone awareness
    if current_run.tzinfo is None:
        base_time = current_run.replace(tzinfo=timezone.utc)
    else:
        base_time = current_run.astimezone(timezone.utc)

    rule = recurrence.lower().strip()

    if rule == "daily":
        return base_time + relativedelta(days=1)
    elif rule == "weekly":
        return base_time + relativedelta(weeks=1)
    elif rule == "monthly":
        return base_time + relativedelta(months=1)
    else:
        raise ValueError(
            f"Unsupported recurrence rule '{recurrence}'. "
            f"Supported rules: {', '.join(sorted(VALID_RECURRENCES))}"
        )
