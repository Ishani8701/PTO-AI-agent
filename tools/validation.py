"""Deterministic validation for time-off requests. Dates, balance, and
overlap checks are pure business logic — never left to the LLM's judgment.
"""

from __future__ import annotations

from datetime import date, datetime

from tools.balances import get_balances, get_remaining_days
from tools.requests import get_held_days, list_requests


def validate_request(
    employee_id: str, leave_type: str, start_date: str, end_date: str
) -> str | None:
    """Return an error message if the request is invalid, else None."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        return f"Dates must be in YYYY-MM-DD format (got {start_date!r}, {end_date!r})."

    if end < start:
        return "The end date can't be before the start date."
    if start < date.today():
        return "Requests can't start in the past."

    requested_days = (end - start).days + 1

    remaining = get_remaining_days(employee_id, leave_type)
    if remaining is None:
        available_types = [b["leave_type"] for b in get_balances(employee_id)]
        return (
            f"You don't have a '{leave_type}' leave balance on file. "
            f"Your available leave types are: {', '.join(available_types)}."
        )

    held = get_held_days(employee_id, leave_type)
    available = remaining - held
    if requested_days > available:
        return (
            f"You're requesting {requested_days} days of {leave_type} leave, but only "
            f"have {available} available ({remaining} remaining, {held} already held by "
            f"pending requests)."
        )

    for existing in list_requests(employee_id):
        if existing["status"] not in ("pending", "approved"):
            continue
        existing_start = datetime.strptime(existing["start_date"], "%Y-%m-%d").date()
        existing_end = datetime.strptime(existing["end_date"], "%Y-%m-%d").date()
        if start <= existing_end and end >= existing_start:
            return (
                f"This overlaps an existing {existing['status']} request "
                f"({existing['start_date']} to {existing['end_date']})."
            )

    return None
