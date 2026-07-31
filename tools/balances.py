"""Access to employee leave balances — backed by ServiceNow's u_pto_balance
table (coursework Part 3) instead of local JSON. Function signatures are
unchanged from the JSON version, so nothing upstream (validation, the
LangGraph handlers) needed to change at all.
"""

from __future__ import annotations

from tools.servicenow_client import query, update

_TABLE = "u_pto_balance"


def _to_balance(record: dict) -> dict:
    return {
        "employee_id": record["u_employee_id"],
        "leave_type": record["u_leave_type"],
        "remaining_days": int(record["u_remaining_days"]),
    }


def get_balances(employee_id: str) -> list[dict]:
    """All leave-type balances for an employee."""
    records = query(_TABLE, f"u_employee_id={employee_id}")
    return [_to_balance(r) for r in records]


def get_remaining_days(employee_id: str, leave_type: str) -> int | None:
    for b in get_balances(employee_id):
        if b["leave_type"] == leave_type:
            return b["remaining_days"]
    return None


def deduct_balance(employee_id: str, leave_type: str, days: int) -> dict:
    """Decrement remaining_days on approval — the point where a held-but-
    not-yet-deducted pending request becomes an actual balance change.
    """
    records = query(_TABLE, f"u_employee_id={employee_id}^u_leave_type={leave_type}")
    if not records:
        raise ValueError(f"No {leave_type!r} balance on file for {employee_id!r}")
    record = records[0]
    new_remaining = int(record["u_remaining_days"]) - days
    updated = update(_TABLE, record["sys_id"], {"u_remaining_days": new_remaining})
    return _to_balance(updated)
