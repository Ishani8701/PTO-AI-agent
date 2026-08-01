"""Read and write employee time-off requests — backed by ServiceNow's
u_pto_request table (coursework Part 3) instead of local JSON. Function
signatures are unchanged from the JSON version, so nothing upstream
(validation, the LangGraph handlers) needed to change at all.

u_number is assigned by ServiceNow's own Number Maintenance auto-numbering
(System Definition > Number Maintenance, prefix "REQ") — not generated here.
That's what makes it atomic under concurrent writes, unlike a client-side
"read the max, add one" approach.
"""

from __future__ import annotations

from datetime import datetime

from tools.servicenow_client import create, query, update
from tracing import traced

_TABLE = "u_pto_request"


def _to_request(record: dict) -> dict:
    return {
        "id": record["u_number"],
        "employee_id": record["u_employee_id"],
        "leave_type": record["u_leave_type"],
        "start_date": record["u_start_date"],
        "end_date": record["u_end_date"],
        "status": record["u_status"],
    }


@traced("list_requests")
def list_requests(employee_id: str) -> list[dict]:
    records = query(_TABLE, f"u_employee_id={employee_id}")
    return [_to_request(r) for r in records]


def get_held_days(employee_id: str, leave_type: str) -> int:
    """Days committed to this employee's pending (not yet approved) requests
    of this leave type. Not yet deducted from their balance, but should
    count against what's available for a new request — otherwise several
    smaller pending requests could together exceed the real balance.
    """
    total = 0
    for r in list_requests(employee_id):
        if r["status"] == "pending" and r["leave_type"] == leave_type:
            start = datetime.strptime(r["start_date"], "%Y-%m-%d").date()
            end = datetime.strptime(r["end_date"], "%Y-%m-%d").date()
            total += (end - start).days + 1
    return total


@traced("submit_request")
def create_request(employee_id: str, leave_type: str, start_date: str, end_date: str) -> dict:
    """Create a new pending request. Does not validate — callers must run
    validate_request() first. Kept separate so "write the record" stays a
    pure, simple operation independent of business-rule changes.
    """
    record = create(
        _TABLE,
        {
            "u_employee_id": employee_id,
            "u_leave_type": leave_type,
            "u_start_date": start_date,
            "u_end_date": end_date,
            "u_status": "pending",
        },
    )
    return _to_request(record)


@traced("update_request_status")
def update_request_status(request_id: str, status: str) -> dict:
    """Change a request's status (e.g. a manager's approve/reject decision).
    Does not touch balances — deducting on approval is a separate step,
    since not every status change should affect a balance.
    """
    records = query(_TABLE, f"u_number={request_id}")
    if not records:
        raise ValueError(f"No request with id {request_id!r}")
    updated = update(_TABLE, records[0]["sys_id"], {"u_status": status})
    return _to_request(updated)
