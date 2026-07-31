"""Handler nodes for each intent. These gather structured facts into
AgentState — outcome + tool_result — but never write natural-language
replies; that's response_generation's job. Kept as small, deterministic
functions per CLAUDE.md's Tool Calling Standards: the LLM decides intent,
these do the calculating, validating, and data access.

The submit_request path is split into four explicit nodes — clarification,
validation, confirmation, submission — mirroring CLAUDE.md's LangGraph
workflow diagram, so each gate is a real, traceable graph step rather than
logic buried inside one function.
"""

from __future__ import annotations

from datetime import datetime

from rag.retrieve import retrieve_policy
from tools.balances import deduct_balance, get_balances
from tools.requests import create_request, list_requests, update_request_status
from tools.team import (
    get_team_availability,
    get_team_pending_requests,
    resolve_direct_reports_by_name,
)
from tools.validation import validate_request
from workflows.state import AgentState

_REQUIRED_FIELDS = ("leave_type", "start_date", "end_date")


def handle_declined(state: AgentState) -> dict:
    return {"outcome": "declined_other_employee", "tool_result": None}


def handle_not_manager(state: AgentState) -> dict:
    return {"outcome": "declined_not_manager", "tool_result": None}


def handle_team_availability(state: AgentState) -> dict:
    """Merge newly extracted fields into what's already known — same pattern
    as clarification_node — so a bare follow-up like "jul 24" after being
    asked for a date range is understood as continuing this query, not
    misclassified as a fresh, unrelated intent.
    """
    manager_id = state["employee"]["id"]
    base = dict(state["partial_entities"])
    for field in ("start_date", "end_date", "target_employee_names"):
        value = state["entities"].get(field)
        if value:
            base[field] = value

    start = base.get("start_date")
    end = base.get("end_date") or start
    if not start:
        return {
            "outcome": "need_clarification",
            "tool_result": {"missing_fields": ["date range"], "known": base},
            "partial_entities": base,
            "active_intent": "team_availability",
        }

    target_names = base.get("target_employee_names") or []
    unmatched = []
    if target_names:
        matched, unmatched = resolve_direct_reports_by_name(manager_id, target_names)
        if not matched:
            # nothing resolved at all — nothing to answer, decline outright
            return {
                "outcome": "declined_not_your_report",
                "tool_result": {"unmatched_names": unmatched},
                "partial_entities": {},
                "active_intent": None,
            }
        report_ids = [r["id"] for r in matched]
        checked = [m["full_name"] for m in matched]
    else:
        report_ids = None
        checked = "whole team"

    availability = get_team_availability(manager_id, start, end, report_ids)
    return {
        "outcome": "team_availability",
        "tool_result": {
            "start_date": start,
            "end_date": end,
            "checked": checked,
            "overlapping": availability,
            "not_your_report": unmatched,
        },
        "partial_entities": {},
        "active_intent": None,
    }


def handle_list_pending_requests(state: AgentState) -> dict:
    manager_id = state["employee"]["id"]
    target_names = state["entities"].get("target_employee_names") or []
    unmatched = []
    if target_names:
        matched, unmatched = resolve_direct_reports_by_name(manager_id, target_names)
        if not matched:
            return {
                "outcome": "declined_not_your_report",
                "tool_result": {"unmatched_names": unmatched},
            }
        report_ids = [r["id"] for r in matched]
    else:
        report_ids = None

    pending = get_team_pending_requests(manager_id, report_ids)
    return {
        "outcome": "list_pending_requests",
        "tool_result": {"pending": pending, "not_your_report": unmatched},
    }


def resolve_manager_action_node(state: AgentState) -> dict:
    """Resolves target employee + specific pending request for
    approve_request/reject_request, or handles a reply to one already
    staged. Merges across turns like clarification_node, since resolving
    "which of several pending requests" can take more than one message —
    by name+dates, or directly by request id.
    """
    action = "approved" if state["intent"] == "approve_request" else "rejected"
    manager_id = state["employee"]["id"]

    if state["pending_confirmation"]:
        confirmation_response = state["confirmation_response"]
        if action != state["pending_confirmation"]["action"]:
            # e.g. a reject was staged, then "actually approve it instead" —
            # both approve_request and reject_request route to this same
            # node, so a switched intent while a confirmation is pending
            # means the manager wants to flip the decision, not start over.
            # Checked BEFORE yes/no: a message like "no, approve it instead"
            # can classify with confirmation_response=yes (a defensible read
            # of the affirmative wording) — but that "yes" is about the NEW
            # action, not the stale pending one, so always re-stage and ask
            # again rather than executing the old action on a "yes" that was
            # never really about it. Matches the same human-in-the-loop rule
            # as edits: a changed decision always gets re-confirmed.
            switched = {**state["pending_confirmation"], "action": action}
            return {
                "outcome": "need_confirmation",
                "tool_result": switched,
                "pending_confirmation": switched,
                "active_intent": state["intent"],
                "confirmation_response": None,
            }
        if confirmation_response == "no":
            return {
                "outcome": "cancelled",
                "tool_result": None,
                "pending_confirmation": None,
                "partial_entities": {},
                "active_intent": None,
            }
        if confirmation_response == "yes":
            return {"outcome": "confirmed"}
        return {"outcome": "need_confirmation", "tool_result": state["pending_confirmation"]}

    base = dict(state["partial_entities"])
    for field in ("target_employee_names", "start_date", "end_date", "request_id"):
        value = state["entities"].get(field)
        if value:
            base[field] = value

    target_names = base.get("target_employee_names") or []
    req_id = base.get("request_id")

    if not target_names and not req_id:
        return {
            "outcome": "need_clarification",
            "tool_result": {"missing_fields": ["which employee or request"], "known": base},
            "partial_entities": base,
            "active_intent": state["intent"],
        }

    if req_id and not target_names:
        # an explicit id is enough on its own — search across the whole team
        candidates = [p for p in get_team_pending_requests(manager_id) if p["request_id"] == req_id]
        if not candidates:
            return {
                "outcome": "declined_not_your_report",
                "tool_result": {"unmatched_names": [], "unmatched_request_id": req_id},
                "partial_entities": {},
                "active_intent": None,
            }
        request = candidates[0]
    else:
        matched, unmatched = resolve_direct_reports_by_name(manager_id, target_names)
        if not matched:
            return {
                "outcome": "declined_not_your_report",
                "tool_result": {"unmatched_names": unmatched},
                "partial_entities": {},
                "active_intent": None,
            }
        if len(matched) > 1:
            return {
                "outcome": "need_clarification",
                "tool_result": {
                    "missing_fields": ["one employee at a time"],
                    "known": {"names": [m["full_name"] for m in matched]},
                },
                "partial_entities": base,
                "active_intent": state["intent"],
            }

        target = matched[0]
        pending = get_team_pending_requests(manager_id, [target["id"]])
        if not pending:
            return {
                "outcome": "nothing_pending",
                "tool_result": {"employee_name": target["full_name"]},
                "partial_entities": {},
                "active_intent": None,
            }

        candidates = pending
        if req_id:
            candidates = [p for p in pending if p["request_id"] == req_id]
        elif base.get("start_date"):
            candidates = [
                p
                for p in pending
                if p["start_date"] == base["start_date"]
                and (not base.get("end_date") or p["end_date"] == base["end_date"])
            ]

        if len(candidates) != 1:
            return {
                "outcome": "need_clarification",
                "tool_result": {
                    "missing_fields": ["which request (by dates or request id)"],
                    "known": {"pending": pending},
                },
                "partial_entities": base,
                "active_intent": state["intent"],
            }
        request = candidates[0]

    proposal = {"action": action, **request}
    return {
        "outcome": "need_confirmation",
        "tool_result": proposal,
        "pending_confirmation": proposal,
        "partial_entities": {},
        "active_intent": state["intent"],
    }


def manager_action_submission_node(state: AgentState) -> dict:
    proposal = state["pending_confirmation"]
    updated = update_request_status(proposal["request_id"], proposal["action"])
    if proposal["action"] == "approved":
        deduct_balance(proposal["employee_id"], proposal["leave_type"], proposal["days"])
    return {
        "outcome": "manager_action_done",
        "tool_result": {
            # from the proposal, not `updated` — update_request_status()'s raw
            # return only has employee_id, never a name, which left
            # response_generation with nothing but {name} (the MANAGER) to
            # address, producing "Alice's leave" for someone else's request
            "action": proposal["action"],
            "employee_name": proposal["employee_name"],
            "request_id": updated["id"],
            "leave_type": updated["leave_type"],
            "start_date": updated["start_date"],
            "end_date": updated["end_date"],
        },
        "pending_confirmation": None,
        "active_intent": None,
    }


def handle_policy(state: AgentState) -> dict:
    chunks = retrieve_policy(state["message"], country=state["employee"]["country"])
    return {"outcome": "policy_answer", "tool_result": {"chunks": [c["text"] for c in chunks]}}


def handle_balance(state: AgentState) -> dict:
    balances = get_balances(state["employee"]["id"])
    return {"outcome": "balance", "tool_result": {"balances": balances}}


def handle_list(state: AgentState) -> dict:
    requests = list_requests(state["employee"]["id"])
    return {"outcome": "list_requests", "tool_result": {"requests": requests}}


def handle_cancel(state: AgentState) -> dict:
    return {
        "outcome": "cancelled",
        "tool_result": None,
        "pending_confirmation": None,
        "partial_entities": {},
        "active_intent": None,
    }


def handle_off_topic(state: AgentState) -> dict:
    return {"outcome": "off_topic", "tool_result": None}


def clarification_node(state: AgentState) -> dict:
    """Merge newly extracted entities into what's already known (partial_entities
    and pending_confirmation are kept in sync by construction — see
    confirmation_node — so partial_entities alone is always the current picture),
    and check whether the request is complete enough to move on to validation.

    Deliberately never touches pending_confirmation here: if a message gets
    misclassified as submit_request while a DIFFERENT flow's confirmation is
    still pending (e.g. a manager approval awaiting yes/no), this node has
    no business clearing it — only the node that owns a confirmation should
    ever clear it. Leaving it alone lets the flow self-heal if the next
    message classifies correctly.
    """
    base = dict(state["partial_entities"])
    for field in _REQUIRED_FIELDS:
        value = state["entities"].get(field)
        if value is not None:
            base[field] = value

    missing = [f for f in _REQUIRED_FIELDS if not base.get(f)]
    if missing:
        return {
            "outcome": "need_clarification",
            "tool_result": {"missing_fields": missing, "known": base},
            "partial_entities": base,
            "active_intent": "submit_request",
        }
    return {"outcome": None, "partial_entities": base, "active_intent": "submit_request"}


def validate_node(state: AgentState) -> dict:
    base = state["partial_entities"]
    error = validate_request(
        state["employee"]["id"], base["leave_type"], base["start_date"], base["end_date"]
    )
    if error:
        return {
            "outcome": "validation_error",
            "tool_result": {"error": error, "known": base},
            "pending_confirmation": None,
        }
    return {"outcome": None}


def confirmation_node(state: AgentState) -> dict:
    """Decide whether we're staging a new proposal or acting on a reply to
    one already staged. The actual write only ever happens from
    submission_node, and only when this returns outcome="confirmed".
    """
    base = state["partial_entities"]
    confirmation_response = state["confirmation_response"]

    if state["pending_confirmation"] and confirmation_response == "no":
        return {
            "outcome": "cancelled",
            "tool_result": None,
            "pending_confirmation": None,
            "partial_entities": {},
            "active_intent": None,
        }

    if state["pending_confirmation"] and confirmation_response == "yes":
        return {"outcome": "confirmed"}

    # fresh complete request, or an edit to an existing proposal — (re)stage it
    start = datetime.strptime(base["start_date"], "%Y-%m-%d").date()
    end = datetime.strptime(base["end_date"], "%Y-%m-%d").date()
    days = (end - start).days + 1
    proposal = {**base, "days": days}
    return {"outcome": "need_confirmation", "tool_result": proposal, "pending_confirmation": proposal}


def submission_node(state: AgentState) -> dict:
    base = state["partial_entities"]
    created = create_request(
        state["employee"]["id"], base["leave_type"], base["start_date"], base["end_date"]
    )
    return {
        "outcome": "submitted",
        "tool_result": created,
        "pending_confirmation": None,
        "partial_entities": {},
        "active_intent": None,
    }
