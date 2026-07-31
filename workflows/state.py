"""LangGraph per-run state — ephemeral, one instance per /api/chat call.

Optional fields use typing.Optional rather than the `X | None` syntax:
LangGraph resolves these type hints at runtime to build its schema, and
`X | None` as a runtime union operation requires Python 3.10+ — this
project's venv is pinned to the system's Python 3.9.
"""

from __future__ import annotations

from typing import Optional, TypedDict


class AgentState(TypedDict):
    employee: dict
    message: str

    # loaded from the employee's WorkflowState at the start of the run
    active_intent: Optional[str]
    partial_entities: dict
    pending_confirmation: Optional[dict]
    advisory_history: list

    # populated by classify_node
    intent: Optional[str]
    entities: dict
    confirmation_response: Optional[str]  # "yes" | "no" | "edit" | None
    mentions_other_employee: bool

    # populated by a handler node; drives response_generation
    outcome: Optional[str]
    tool_result: Optional[dict]

    # populated by response_generation
    reply: str
