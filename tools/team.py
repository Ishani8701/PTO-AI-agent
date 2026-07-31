"""Manager-facing queries over a manager's direct reports and their time off."""

from __future__ import annotations

import json
from datetime import datetime

from app import config
from tools.requests import list_requests


def get_direct_reports(manager_id: str) -> list[dict]:
    employees = json.loads((config.DATA_DIR / "employees.json").read_text())
    return [e for e in employees if e.get("manager_id") == manager_id]


def is_direct_report(manager_id: str, employee_id: str) -> bool:
    return any(e["id"] == employee_id for e in get_direct_reports(manager_id))


def resolve_direct_reports_by_name(manager_id: str, names: list[str]) -> tuple[list[dict], list[str]]:
    """Match each name against the manager's direct reports (case-insensitive,
    partial match on full_name). Returns (matched reports, names that didn't
    match any direct report — either misspelled, or a real employee who just
    isn't on this manager's team).
    """
    reports = get_direct_reports(manager_id)
    matched = []
    unmatched = []
    for name in names:
        hit = next((r for r in reports if name.lower() in r["full_name"].lower()), None)
        if hit:
            matched.append(hit)
        else:
            unmatched.append(name)
    return matched, unmatched


def get_team_availability(
    manager_id: str, start_date: str, end_date: str, report_ids: list[str] | None = None
) -> list[dict]:
    """Direct reports' requests overlapping [start_date, end_date], restricted
    to pending/approved — the statuses that actually take someone off work.
    If report_ids is given, restrict to just those reports (already validated
    as belonging to this manager by the caller); otherwise, the whole team.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()

    reports = get_direct_reports(manager_id)
    if report_ids is not None:
        reports = [r for r in reports if r["id"] in report_ids]

    overlapping = []
    for report in reports:
        for r in list_requests(report["id"]):
            if r["status"] not in ("pending", "approved"):
                continue
            r_start = datetime.strptime(r["start_date"], "%Y-%m-%d").date()
            r_end = datetime.strptime(r["end_date"], "%Y-%m-%d").date()
            if start <= r_end and end >= r_start:
                overlapping.append(
                    {
                        "employee_name": report["full_name"],
                        "leave_type": r["leave_type"],
                        "start_date": r["start_date"],
                        "end_date": r["end_date"],
                        "status": r["status"],
                    }
                )
    return overlapping


def get_team_pending_requests(manager_id: str, report_ids: list[str] | None = None) -> list[dict]:
    """All pending requests across the manager's direct reports (or a given
    subset) — the manager's actionable approval queue, not scoped to any
    date range, since every pending request needs a decision eventually.
    """
    reports = get_direct_reports(manager_id)
    if report_ids is not None:
        reports = [r for r in reports if r["id"] in report_ids]

    pending = []
    for report in reports:
        for r in list_requests(report["id"]):
            if r["status"] != "pending":
                continue
            start = datetime.strptime(r["start_date"], "%Y-%m-%d").date()
            end = datetime.strptime(r["end_date"], "%Y-%m-%d").date()
            pending.append(
                {
                    "request_id": r["id"],
                    "employee_id": report["id"],
                    "employee_name": report["full_name"],
                    "leave_type": r["leave_type"],
                    "start_date": r["start_date"],
                    "end_date": r["end_date"],
                    "days": (end - start).days + 1,
                }
            )
    return pending
