"""In-memory per-employee workflow state — pending confirmations and
partial entities collected across turns. Not durable across restarts;
appropriate at this app's mock-data scale (becomes a real store around
roadmap.md's Phase 3 database migration).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WorkflowState:
    active_intent: str | None = None  # e.g. "submit_request" while mid-flow
    partial_entities: dict = field(default_factory=dict)
    pending_confirmation: dict | None = None
    # sliding-window history for the advisory_question branch only — the
    # deterministic flows above don't need raw message history (see
    # workflows/advisory.py), but open-ended multi-turn reasoning does
    advisory_history: list = field(default_factory=list)


_SESSIONS: dict[str, WorkflowState] = {}


def get_session(employee_id: str) -> WorkflowState:
    if employee_id not in _SESSIONS:
        _SESSIONS[employee_id] = WorkflowState()
    return _SESSIONS[employee_id]


def reset_session(employee_id: str) -> None:
    """Clear an employee's in-memory workflow state. Used by evaluation/ for
    test isolation between cases (so a previous case's leftover pending
    confirmation or active_intent can't bleed into the next one run against
    the same employee) — never called by the app's normal request flow.
    """
    _SESSIONS.pop(employee_id, None)
