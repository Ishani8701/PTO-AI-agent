"""MCP server exposing PTO capabilities as discoverable tools (coursework
Part 5), reusing the same tools/ business logic the main app uses — this
is a second interface onto the same capabilities, not a rewrite of them.

Scoped to a single employee, set via the MCP_EMPLOYEE_ID environment
variable at launch — never accepted as a tool parameter, since a generic
MCP client's calling model shouldn't be the one deciding whose PTO data
to access (see CLAUDE.md's identity requirements). Manager-only tools are
only registered at all if that employee's role is "manager" — a
non-manager's server instance doesn't advertise them as existing.

Mutating actions (submitting a request, approving/rejecting one) are each
split into propose_*/confirm_* tool pairs: propose_* validates and stages
a preview with a one-time token, confirm_* only executes given that exact
token. This makes "never submit automatically" a property of the tool
design itself, rather than something every possible MCP client is trusted
to enforce with its own approval UI.

Run standalone for development:
    mcp dev mcp_server/server.py

Configure in Claude Desktop's claude_desktop_config.json:
    {
      "mcpServers": {
        "acme-pto": {
          "command": "/absolute/path/to/.venv-mcp/bin/python3",
          "args": ["/absolute/path/to/mcp_server/server.py"],
          "env": {"MCP_EMPLOYEE_ID": "E002"}
        }
      }
    }
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `tools/` resolves regardless of how this is launched

from mcp.server.fastmcp import FastMCP  # noqa: E402

from tools.balances import deduct_balance, get_balances  # noqa: E402
from tools.requests import create_request, list_requests as _list_requests, update_request_status  # noqa: E402
from tools.team import (  # noqa: E402
    get_team_availability,
    get_team_pending_requests,
    resolve_direct_reports_by_name,
)
from tools.validation import validate_request  # noqa: E402

_EMPLOYEES = {e["id"]: e for e in json.loads((ROOT / "data" / "employees.json").read_text())}

_EMPLOYEE_ID = os.environ.get("MCP_EMPLOYEE_ID")
if not _EMPLOYEE_ID or _EMPLOYEE_ID not in _EMPLOYEES:
    raise SystemExit(
        "MCP_EMPLOYEE_ID must be set to a valid employee id (see data/employees.json). "
        "This server acts on behalf of exactly one employee, configured at launch."
    )
_EMPLOYEE = _EMPLOYEES[_EMPLOYEE_ID]
_IS_MANAGER = _EMPLOYEE.get("role") == "manager"

mcp = FastMCP("acme-pto")

# In-memory token store for the propose/confirm pattern — not persisted
# across restarts, same simplicity tradeoff as workflows/session.py.
_PENDING: dict[str, dict] = {}


@mcp.tool()
def check_balance() -> list[dict]:
    """Check the current employee's PTO balances, by leave type."""
    return get_balances(_EMPLOYEE_ID)


@mcp.tool()
def list_requests() -> list[dict]:
    """List the current employee's own time-off requests, past and present."""
    return _list_requests(_EMPLOYEE_ID)


@mcp.tool()
def propose_request(leave_type: str, start_date: str, end_date: str) -> dict:
    """Validate a new time-off request and stage it for confirmation.
    Does NOT submit anything — call confirm_request with the returned
    token to actually submit it. Dates must be YYYY-MM-DD.
    """
    error = validate_request(_EMPLOYEE_ID, leave_type, start_date, end_date)
    if error:
        return {"error": error}
    token = str(uuid.uuid4())
    _PENDING[token] = {
        "kind": "submit",
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
    }
    return {
        "token": token,
        "preview": f"{leave_type} leave from {start_date} to {end_date}",
        "note": "Nothing has been submitted yet. Call confirm_request with this token to submit.",
    }


@mcp.tool()
def confirm_request(token: str) -> dict:
    """Submit a request previously staged by propose_request. Requires
    the exact token that call returned — this is the only way a request
    actually gets created.
    """
    proposal = _PENDING.pop(token, None)
    if not proposal or proposal["kind"] != "submit":
        return {"error": "Unknown or expired token. Call propose_request again."}
    return create_request(_EMPLOYEE_ID, proposal["leave_type"], proposal["start_date"], proposal["end_date"])


if _IS_MANAGER:

    @mcp.tool()
    def team_availability(start_date: str, end_date: str, employee_names: list[str] | None = None) -> dict:
        """Who on the manager's team has time off overlapping a date
        range. Leave employee_names empty for the whole team, or name
        specific direct reports. Dates must be YYYY-MM-DD.
        """
        report_ids = None
        if employee_names:
            matched, unmatched = resolve_direct_reports_by_name(_EMPLOYEE_ID, employee_names)
            if not matched:
                return {"error": "None of those names match a direct report.", "unmatched": unmatched}
            report_ids = [r["id"] for r in matched]
        return {"overlapping": get_team_availability(_EMPLOYEE_ID, start_date, end_date, report_ids)}

    @mcp.tool()
    def list_pending_requests(employee_names: list[str] | None = None) -> dict:
        """List pending requests awaiting this manager's decision, across
        their whole team or specific named direct reports.
        """
        report_ids = None
        if employee_names:
            matched, unmatched = resolve_direct_reports_by_name(_EMPLOYEE_ID, employee_names)
            if not matched:
                return {"error": "None of those names match a direct report.", "unmatched": unmatched}
            report_ids = [r["id"] for r in matched]
        return {"pending": get_team_pending_requests(_EMPLOYEE_ID, report_ids)}

    @mcp.tool()
    def propose_manager_action(action: str, employee_name: str, request_id: str = "") -> dict:
        """Stage an approve or reject decision on a direct report's
        pending request. action must be "approve" or "reject". Does NOT
        execute anything — call confirm_manager_action with the returned
        token to actually apply the decision. If the named employee has
        more than one pending request, pass request_id to disambiguate
        (call list_pending_requests first to see the options).
        """
        if action not in ("approve", "reject"):
            return {"error": "action must be 'approve' or 'reject'."}
        matched, unmatched = resolve_direct_reports_by_name(_EMPLOYEE_ID, [employee_name])
        if not matched:
            return {"error": f"{employee_name!r} is not one of your direct reports.", "unmatched": unmatched}
        target = matched[0]
        pending = get_team_pending_requests(_EMPLOYEE_ID, [target["id"]])
        if not pending:
            return {"error": f"{target['full_name']} has no pending requests."}
        if request_id:
            pending = [p for p in pending if p["request_id"] == request_id]
        if len(pending) != 1:
            return {
                "error": "More than one pending request matches — call again with request_id to disambiguate.",
                "candidates": pending,
            }
        request = pending[0]
        token = str(uuid.uuid4())
        _PENDING[token] = {"kind": "manager_action", "action": action, **request}
        return {
            "token": token,
            "preview": (
                f"{action} {request['employee_name']}'s {request['leave_type']} leave "
                f"{request['start_date']} to {request['end_date']} ({request['request_id']})"
            ),
            "note": "Nothing has been applied yet. Call confirm_manager_action with this token to apply it.",
        }

    @mcp.tool()
    def confirm_manager_action(token: str) -> dict:
        """Apply an approve/reject decision previously staged by
        propose_manager_action. Requires the exact token that call
        returned.
        """
        proposal = _PENDING.pop(token, None)
        if not proposal or proposal["kind"] != "manager_action":
            return {"error": "Unknown or expired token. Call propose_manager_action again."}
        status = "approved" if proposal["action"] == "approve" else "rejected"
        updated = update_request_status(proposal["request_id"], status)
        if status == "approved":
            deduct_balance(proposal["employee_id"], proposal["leave_type"], proposal["days"])
        return {**updated, "action": status}


if __name__ == "__main__":
    mcp.run()
