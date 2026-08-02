"""Real multi-round agentic tool-use loop for the advisory_question branch —
the first place in this project that actually needed one (Part 1's
retrieve_policy country-selection question, and Part 5's MCP-vs-direct-call
question, were both deliberately deferred to here). Opus decides which
tools to call and in what order; every tool call executes against the SAME
already-hardened tools/ functions every other node uses, so authorization
(never another employee's individual data, manager tools scoped to real
direct reports) is inherited, not re-implemented.
"""

from __future__ import annotations

import anthropic

from app import config
from prompts.advisory import build_system_prompt
from rag.retrieve import retrieve_policy
from tools.balances import get_balances
from tools.calendar_client import CalendarError, get_calendar_events
from tools.requests import list_requests as _list_requests
from tools.team import get_team_availability, get_team_pending_requests, resolve_direct_reports_by_name
from workflows.state import AgentState

_MAX_ROUNDS = 5
_SLIDING_WINDOW = 10  # most recent advisory turns to keep, as {role, content} text pairs


def _tools_for(employee: dict) -> list[dict]:
    tools = [
        {
            "name": "check_balance",
            "description": "Check the employee's own PTO balances, by leave type.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_requests",
            "description": "List the employee's own time-off requests, past and present.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "retrieve_policy",
            "description": "Search Acme's time-off policy documents for the employee's own country.",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "check_calendar",
            "description": (
                "Check the employee's own calendar for existing events/meetings in a date "
                "range — use this to see real commitments, not just PTO, when reasoning "
                "about timing. Read-only; never creates, edits, or cancels anything."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    ]
    if employee["role"] == "manager":
        tools += [
            {
                "name": "team_availability",
                "description": "Who on the manager's team has time off overlapping a date range.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                        "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                        "employee_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Empty for the whole team, or specific direct reports.",
                        },
                    },
                    "required": ["start_date", "end_date"],
                },
            },
            {
                "name": "list_pending_requests",
                "description": "List pending requests awaiting this manager's decision.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "employee_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Empty for the whole team, or specific direct reports.",
                        }
                    },
                },
            },
        ]
    return tools


def _execute_tool(name: str, tool_input: dict, employee: dict) -> dict:
    employee_id = employee["id"]

    if name == "check_balance":
        return {"balances": get_balances(employee_id)}

    if name == "list_requests":
        return {"requests": _list_requests(employee_id)}

    if name == "retrieve_policy":
        chunks = retrieve_policy(tool_input["query"], country=employee["country"])
        return {"chunks": [c["text"] for c in chunks]}

    if name == "check_calendar":
        try:
            events = get_calendar_events(employee_id, tool_input["start_date"], tool_input["end_date"])
        except CalendarError as e:
            # Same graceful-degradation pattern as the rest of this project
            # (roadmap Phase 15: "I couldn't retrieve..." not a crash) — the
            # bridge/Google being unreachable shouldn't kill the whole
            # advisory answer, just mean Opus reasons without calendar data.
            return {"error": str(e)}
        return {"events": events}

    if name in ("team_availability", "list_pending_requests"):
        report_ids = None
        names = tool_input.get("employee_names") or []
        if names:
            matched, unmatched = resolve_direct_reports_by_name(employee_id, names)
            if not matched:
                return {"error": "None of those names match a direct report.", "unmatched": unmatched}
            report_ids = [r["id"] for r in matched]
        if name == "team_availability":
            overlapping = get_team_availability(
                employee_id, tool_input["start_date"], tool_input["end_date"], report_ids
            )
            return {"overlapping": overlapping}
        return {"pending": get_team_pending_requests(employee_id, report_ids)}

    return {"error": f"Unknown tool {name!r}"}


def answer_advisory_question(employee: dict, message: str, history: list) -> tuple[str, list, list]:
    """Runs the Opus tool-use loop. `history` is a simplified list of prior
    {role, content} TEXT turns only — not raw tool-loop internals, which are
    scratch work for a single turn, not something future turns need to see
    (and persisting them risks breaking tool_use/tool_result pairing across
    turns). Returns (final_answer_text, updated_history, collected_tool_results)
    — the third element exists specifically so handle_advisory_question can
    expose what was actually looked up as state["tool_result"], the same way
    every deterministic handler does; without it, output_guardrail_node (see
    workflows/graph.py) would have no real Details to check this branch's
    replies against, and would incorrectly flag every advisory answer as
    ungrounded regardless of how well-grounded it actually was — confirmed:
    this is exactly what happened before this field existed.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, base_url=config.ANTHROPIC_BASE_URL)
    system = build_system_prompt(employee)
    tools = _tools_for(employee)

    messages = list(history) + [{"role": "user", "content": message}]
    collected_results: list[dict] = []

    final_text = "I wasn't able to finish reasoning through this in time — could you narrow the question a bit?"
    for _ in range(_MAX_ROUNDS):
        resp = client.messages.create(
            model=config.ANTHROPIC_OPUS_MODEL,
            max_tokens=1500,
            system=system,
            tools=tools,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            final_text = "".join(b.text for b in resp.content if b.type == "text")
            break

        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                result = _execute_tool(block.name, block.input, employee)
                collected_results.append({"tool": block.name, "input": block.input, "result": result})
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": str(result)}
                )
        messages.append({"role": "user", "content": tool_results})

    updated_history = (
        history
        + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": final_text},
        ]
    )[-_SLIDING_WINDOW:]
    return final_text, updated_history, collected_results


def handle_advisory_question(state: AgentState) -> dict:
    """Graph node wrapper. Sets `reply` directly and skips response_generation
    — Opus's own final message already is the natural-language answer, so
    running it through a second LLM call to "rephrase" it would be a
    redundant cost for no benefit (see workflows/graph.py's routing).
    """
    answer, history, collected_results = answer_advisory_question(
        state["employee"], state["message"], state["advisory_history"]
    )
    return {
        "reply": answer,
        "advisory_history": history,
        "tool_result": collected_results,
        # stays "advisory_question", not None — classify() has no visibility into
        # advisory_history, so this is the only signal it has that a same-topic
        # follow-up ("what about September instead?") continues the conversation
        # rather than starting a fresh submit_request. Tested: clearing it broke
        # exactly that case.
        "active_intent": "advisory_question",
    }
