"""Deterministic tool-call accuracy checking — no LLM, per EVAL_PLAN.md's
explicit guidance ("Tool evaluation should not use an LLM").

Checks presence, not exact call count or sequence: expected_tools must ALL
appear at least once in the trace, forbidden_tools must NONE appear. This
is deliberate, not a shortcut — classify() unconditionally calls
check_balance on every message, and validate_node's balance/held-days check
calls check_balance and list_requests as a side effect on any submit_request
flow that reaches it. An exact-match checker would flag entirely correct
behavior as a failure on nearly every case. See golden_dataset.json's
per-case comments for the concrete code paths this was verified against.
"""

from __future__ import annotations


def check_tool_usage(
    expected_tools: list[str], trace: list[dict], forbidden_tools: list[str] | None = None
) -> dict:
    actual_tools = {t["tool"] for t in trace}
    expected_set = set(expected_tools)
    forbidden_set = set(forbidden_tools or [])

    missing = sorted(expected_set - actual_tools)
    unexpected = sorted(forbidden_set & actual_tools)

    return {
        "passed": not missing and not unexpected,
        "expected_tools": expected_tools,
        "forbidden_tools": forbidden_tools or [],
        "actual_tools": sorted(actual_tools),
        "missing_tools": missing,
        "forbidden_tools_called": unexpected,
    }
