"""Runs guardrail_dataset.json directly against guardrails.py's check_input/
check_output — distinct from evaluation/runner.py, which exercises full
agent turns through run_turn(). This tests the guardrail functions in
isolation: given this exact text (and, for output cases, these exact
Details), does the guardrail return the expected verdict?

Usage: python3 -m evaluation.guardrail_runner
Exit code 1 if any case's actual verdict doesn't match its expected one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from guardrails import check_input, check_output

_EVAL_DIR = Path(__file__).resolve().parent


def _run_case(case: dict) -> dict:
    if case["layer"] == "input":
        is_safe, reason = check_input(case["text"])
    else:
        is_safe, reason = check_output(case["text"], case.get("details"))

    actual = "SAFE" if is_safe else "UNSAFE"
    return {
        "id": case["id"],
        "layer": case["layer"],
        "category": case["category"],
        "expected": case["expect"],
        "actual": actual,
        "passed": actual == case["expect"],
        "reason": reason,
    }


def run_all() -> list[dict]:
    cases = json.loads((_EVAL_DIR / "guardrail_dataset.json").read_text())
    return [_run_case(c) for c in cases]


if __name__ == "__main__":
    results = run_all()
    out_path = _EVAL_DIR / "guardrail_report.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))

    failed = [r for r in results if not r["passed"]]
    for r in results:
        mark = "OK" if r["passed"] else "MISMATCH"
        print(f"[{mark}] {r['id']} ({r['layer']}/{r['category']}): expected {r['expected']}, got {r['actual']}")
        if not r["passed"]:
            print(f"         reason: {r['reason']}")

    print()
    print(f"{len(results) - len(failed)}/{len(results)} guardrail cases matched expected verdict")
    print(f"Full report written to {out_path}")

    if failed:
        print("GUARDRAIL GATE: FAILED")
        sys.exit(1)
    print("GUARDRAIL GATE: PASSED")
