"""Lightweight tool-call tracing for evaluation. One contextvar holds the
current run's trace, so the same @traced decorator applied to any tools/
function works uniformly for both the deterministic graph
(workflows/handlers.py) and the advisory branch's multi-round tool loop
(workflows/advisory.py) — no need to thread a trace list through every
handler's return dict.

Zero overhead outside an eval run: start_trace() must be called first, or
@traced is a no-op passthrough (the contextvar defaults to None).

Dependency direction: tools/*.py imports this; evaluation/ reads from it
after a run. Core app code depending on this small, dependency-free module
is fine — evaluation/ never gets imported by the core app.
"""

from __future__ import annotations

import contextvars
import functools
import inspect
from typing import Callable

_trace: contextvars.ContextVar = contextvars.ContextVar("_trace", default=None)


def start_trace() -> None:
    """Call before a run you want to capture — resets to an empty list."""
    _trace.set([])


def get_trace() -> list[dict]:
    """Call after the run — everything traced() since the last start_trace()."""
    return _trace.get() or []


def traced(name: str) -> Callable:
    """Decorator recording every call to the wrapped function as
    {"tool": name, "args": {...}, "result": ...}. Args are bound to their
    parameter names via inspect.signature so the trace is useful regardless
    of whether the function was called positionally or by keyword.
    """

    def decorator(fn: Callable) -> Callable:
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            result = fn(*args, **kwargs)
            trace = _trace.get()
            if trace is not None:
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                trace.append({"tool": name, "args": dict(bound.arguments), "result": result})
            return result

        return wrapper

    return decorator
