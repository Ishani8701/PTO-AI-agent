"""Assembles the LangGraph graph for one /api/chat turn and exposes
run_turn() as the single entry point main.py calls.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

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
    # response_generation to phrase a graceful failure message.
    return "response_generation" if state["outcome"] == "api_error" else "memory_update"


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
    graph.add_node("memory_update", memory_update_node)

    graph.set_entry_point("classify")
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

    graph.add_edge("response_generation", "memory_update")
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
