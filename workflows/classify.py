"""Intent classification + entity extraction, using Claude Haiku — cheap,
fast, this task doesn't need Sonnet-level reasoning (see CLAUDE.md Models).

A single structured-extraction call, not an agentic tool loop like
retrieve_policy: we force Claude through the `classify` tool purely to get
reliable JSON back. Nothing is executed on Claude's behalf, and nothing is
sent back to it — we just read what it filled in.
"""

from __future__ import annotations

import anthropic

from app import config
from prompts.classify_intent import build_system_prompt
from tools.balances import get_balances

_CLASSIFY_TOOL = {
    "name": "classify",
    "description": "Classify the employee's message and extract any time-off details present.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": [
                    "policy_question", "check_balance", "submit_request",
                    "list_requests", "cancel_pending", "off_topic",
                    "team_availability", "list_pending_requests",
                    "approve_request", "reject_request", "advisory_question",
                ],
            },
            "leave_type": {"type": ["string", "null"]},
            "start_date": {"type": ["string", "null"]},
            "end_date": {"type": ["string", "null"]},
            "mentions_other_employee": {"type": "boolean"},
            "confirmation_response": {
                "type": ["string", "null"],
                "enum": ["yes", "no", "edit", None],
                "description": (
                    "Only meaningful if a pending confirmation was described in context. "
                    "'yes' if the employee confirms, 'no' if they reject, 'edit' if they "
                    "want to change a detail, null if the message doesn't address it."
                ),
            },
            "target_employee_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Only for team_availability, list_pending_requests, approve_request, "
                    "or reject_request: the specific employee name(s) if the manager is "
                    "asking about or acting on particular people — can be more than one. "
                    "Empty list for a whole-team query. Whether each person is actually "
                    "this manager's report is checked downstream, not by you."
                ),
            },
            "request_id": {
                "type": ["string", "null"],
                "description": (
                    "Only for approve_request or reject_request: the specific request id "
                    "if the message references one directly (e.g. 'REQ-1002'), or if "
                    "disambiguating which of an employee's several pending requests is "
                    "meant. Null otherwise."
                ),
            },
        },
        "required": [
            "intent", "leave_type", "start_date", "end_date",
            "mentions_other_employee", "confirmation_response", "target_employee_names",
            "request_id",
        ],
    },
}


def classify(
    message: str,
    employee: dict,
    active_intent: str | None,
    partial_entities: dict,
    pending_confirmation: dict | None = None,
) -> dict:
    valid_leave_types = [b["leave_type"] for b in get_balances(employee["id"])]
    system = build_system_prompt(
        employee, active_intent, partial_entities, pending_confirmation, valid_leave_types
    )
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, base_url=config.ANTHROPIC_BASE_URL)
    resp = client.messages.create(
        model=config.ANTHROPIC_HAIKU_MODEL,
        max_tokens=512,
        system=system,
        tools=[_CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "classify"},
        messages=[{"role": "user", "content": message}],
    )
    tool_use = next(b for b in resp.content if b.type == "tool_use")
    return tool_use.input
