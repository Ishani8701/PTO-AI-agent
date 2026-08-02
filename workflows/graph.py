"""Assembles the LangGraph graph for one /api/chat turn and exposes
run_turn() as the single entry point main.py calls.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from guardrails import check_input, check_output
from tools.servicenow_client import ServiceNowError
from workflows.advisory import handle_advisory_question
from workflows.classify import classify
from workflows.handlers import (
    clarification_node,
    confirmation_node,
    handle_balance,
    handle_cancel,
    handle_declined,
    handle_list,
    handle_list_pending_requests,
    handle_not_manager,
    handle_off_topic,
    handle_policy,
    handle_team_availability,
    manager_action_submission_node,
    resolve_manager_action_node,
    submission_node,
    validate_node,
)
from workflows.respond import response_generation_node
from workflows.session import get_session
from workflows.state import AgentState


_BLOCKED_INPUT_REPLY = (
    "I'm not able to help with that. I can help with policy questions, checking your "
    "balance, submitting or managing PTO requests, and planning advice for when to take "
    "time off — and if you're a manager, checking your team's availability or reviewing "
    "pending requests too."
)


def input_guardrail_node(state: AgentState) -> dict:
    """Runs before classify() even sees the message — the entry point of
    the whole graph. A flagged message never reaches any tool or LLM
    downstream. The user gets a fixed, generic decline (never told the
    specific reason — that helps an attacker iterate, it doesn't help a
    legitimate user); the real reason is logged for audit purposes. Session
    state (active_intent, pending_confirmation) is left untouched, so a
    false positive doesn't cost a user their in-progress flow.
    """
    is_safe, reason = check_input(state["message"])
    if not is_safe:
        print(f"[input guardrail] blocked message from {state['employee']['id']}: {reason}")
        return {"outcome": "blocked_input", "reply": _BLOCKED_INPUT_REPLY}
    return {}


def route_after_input_guardrail(state: AgentState) -> str:
    return "memory_update" if state["outcome"] == "blocked_input" else "classify"


def classify_node(state: AgentState) -> dict:
    result = classify(
        state["message"],
        state["employee"],
        state["active_intent"],
        state["partial_entities"],
        state["pending_confirmation"],
    )
    return {
        "intent": result["intent"],
        "entities": {
            "leave_type": result["leave_type"],
            "start_date": result["start_date"],
            "end_date": result["end_date"],
            "target_employee_names": result["target_employee_names"],
            "request_id": result["request_id"],
        },
        "mentions_other_employee": result["mentions_other_employee"],
        "confirmation_response": result["confirmation_response"],
    }


def _safe(fn):
    """Wrap a node so a ServiceNow API failure becomes a graceful outcome
    instead of crashing the request — real latency/errors are exactly what
    coursework.md Part 3 wants handled, not left to fail silently. Applied
    uniformly to every node; nodes that never touch ServiceNow simply never
    trigger the except branch.
    """

    def wrapped(state: AgentState) -> dict:
        try:
            return fn(state)
        except ServiceNowError as e:
            return {"outcome": "api_error", "tool_result": {"error": str(e)}}

    return wrapped


_MANAGER_ONLY_INTENTS = (
    "team_availability", "list_pending_requests", "approve_request", "reject_request",
)


def route_after_classify(state: AgentState) -> str:
    if state["outcome"] == "api_error":
        # classify() itself calls get_balances() (for valid leave types), so
        # a ServiceNow outage can fail classification before intent is even
        # set — route straight to response_generation rather than indexing
        # the intent dict below with a None key.
        return "response_generation"
    intent = state["intent"]
    if intent in _MANAGER_ONLY_INTENTS and state["employee"].get("role") != "manager":
        return "handle_not_manager"
    if state["mentions_other_employee"]:
        return "handle_declined"
    return {
        "policy_question": "handle_policy",
        "check_balance": "handle_balance",
        "list_requests": "handle_list",
        "submit_request": "clarification_node",
        "cancel_pending": "handle_cancel",
        "off_topic": "handle_off_topic",
        "team_availability": "handle_team_availability",
        "list_pending_requests": "handle_list_pending_requests",
        "approve_request": "resolve_manager_action_node",
        "reject_request": "resolve_manager_action_node",
        "advisory_question": "handle_advisory_question",
    }[intent]


def route_after_clarification(state: AgentState) -> str:
    if state["outcome"] in ("need_clarification", "api_error"):
        return "response_generation"
    return "validate_node"


def route_after_validation(state: AgentState) -> str:
    if state["outcome"] in ("validation_error", "api_error"):
        return "response_generation"
    return "confirmation_node"


def route_after_confirmation(state: AgentState) -> str:
    return "submission_node" if state["outcome"] == "confirmed" else "response_generation"


def route_after_manager_action(state: AgentState) -> str:
    return "manager_action_submission_node" if state["outcome"] == "confirmed" else "response_generation"


def route_after_advisory(state: AgentState) -> str:
    # success sets `reply` directly and skips response_generation (see
    # workflows/advisory.py); a ServiceNowError caught by _safe() sets
    # outcome="api_error" instead, with no `reply` — that case still needs
    # response_generation to phrase a graceful failure message. Either way,
    # a real reply ends up going through output_guardrail_node before
    # memory_update, same as every other path.
    return "response_generation" if state["outcome"] == "api_error" else "output_guardrail_node"


_BLOCKED_OUTPUT_REPLY = (
    "I wasn't able to confirm that response is accurate, so I don't want to share it "
    "as-is — could you try rephrasing, or ask something more specific?"
)


def output_guardrail_node(state: AgentState) -> dict:
    """Runs after a reply is fully formed (from either response_generation
    or the advisory branch's direct reply) and before memory_update — so a
    blocked/replaced reply is what actually gets persisted to session
    history, not the discarded original. Unsafe output is replaced with a
    fixed fallback, never retried/regenerated (see design discussion — a
    retry adds cost/latency with no guarantee it fixes the underlying
    issue). The real reply and reason are logged even though the user only
    ever sees the generic fallback.
    """
    is_safe, reason = check_output(state["reply"], state["tool_result"])
    if not is_safe:
        print(f"[output guardrail] blocked reply for {state['employee']['id']}: {reason}")
        print(f"[output guardrail] original reply was: {state['reply']!r}")
        return {"reply": _BLOCKED_OUTPUT_REPLY}
    return {}


def memory_update_node(state: AgentState) -> dict:
    session = get_session(state["employee"]["id"])
    session.active_intent = state["active_intent"]
    session.partial_entities = state["partial_entities"]
    session.pending_confirmation = state["pending_confirmation"]
    session.advisory_history = state["advisory_history"]
    return {}


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("classify", _safe(classify_node))
    graph.add_node("handle_declined", handle_declined)
    graph.add_node("handle_not_manager", handle_not_manager)
    graph.add_node("handle_policy", _safe(handle_policy))
    graph.add_node("handle_balance", _safe(handle_balance))
    graph.add_node("handle_list", _safe(handle_list))
    graph.add_node("handle_cancel", handle_cancel)
    graph.add_node("handle_off_topic", handle_off_topic)
    graph.add_node("handle_team_availability", _safe(handle_team_availability))
    graph.add_node("handle_list_pending_requests", _safe(handle_list_pending_requests))
    graph.add_node("handle_advisory_question", _safe(handle_advisory_question))
    graph.add_node("clarification_node", clarification_node)
    graph.add_node("validate_node", _safe(validate_node))
    graph.add_node("confirmation_node", confirmation_node)
    graph.add_node("submission_node", _safe(submission_node))
    graph.add_node("resolve_manager_action_node", _safe(resolve_manager_action_node))
    graph.add_node("manager_action_submission_node", _safe(manager_action_submission_node))
    graph.add_node("response_generation", response_generation_node)
    graph.add_node("input_guardrail_node", input_guardrail_node)
    graph.add_node("output_guardrail_node", output_guardrail_node)
    graph.add_node("memory_update", memory_update_node)

    graph.set_entry_point("input_guardrail_node")
    graph.add_conditional_edges("input_guardrail_node", route_after_input_guardrail)
    graph.add_conditional_edges("classify", route_after_classify)
    graph.add_conditional_edges("clarification_node", route_after_clarification)
    graph.add_conditional_edges("validate_node", route_after_validation)
    graph.add_conditional_edges("confirmation_node", route_after_confirmation)
    graph.add_conditional_edges("resolve_manager_action_node", route_after_manager_action)
    graph.add_conditional_edges("handle_advisory_question", route_after_advisory)

    for node in (
        "handle_declined", "handle_not_manager", "handle_policy", "handle_balance",
        "handle_list", "handle_cancel", "handle_off_topic", "handle_team_availability",
        "handle_list_pending_requests", "submission_node", "manager_action_submission_node",
    ):
        graph.add_edge(node, "response_generation")

    graph.add_edge("response_generation", "output_guardrail_node")
    graph.add_edge("output_guardrail_node", "memory_update")
    graph.add_edge("memory_update", END)

    return graph.compile()


_GRAPH = build_graph()


def run_turn(employee: dict, message: str) -> str:
    session = get_session(employee["id"])
    initial_state: AgentState = {
        "employee": employee,
        "message": message,
        "active_intent": session.active_intent,
        "partial_entities": dict(session.partial_entities),
        "pending_confirmation": session.pending_confirmation,
        "advisory_history": list(session.advisory_history),
        "intent": None,
        "entities": {},
        "confirmation_response": None,
        "mentions_other_employee": False,
        "outcome": None,
        "tool_result": None,
        "reply": "",
    }
    final_state = _GRAPH.invoke(initial_state)
    return final_state["reply"]
