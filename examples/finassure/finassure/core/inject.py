"""Named fault injection points for workflow packs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from agentic_chaos import chaos_call
from agentic_chaos.chaos import get_active_session

T = TypeVar("T")


_CHAOS_OPTIONS = {"step_id", "step_name", "_chaos_edge_id", "_chaos_from_node", "_chaos_to_node"}


def inject(fault_names: tuple[str, ...], fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Call `fn` through `chaos_call()` only if the active session carries one of `fault_names`.

    Each call site declares which faults it is an injection point for, so a scenario's
    fault fires where the scenario says it does instead of at the first `chaos_call()`.
    `step_id`, `step_name` and the `_chaos_*` edge options go to `chaos_call()`; every
    other keyword argument goes to `fn`.
    """
    session = get_active_session()
    configured = {fault.name for fault in session.faults} if session else set()
    selected = [name for name in fault_names if name in configured]
    if not selected:
        return fn(*args, **{k: v for k, v in kwargs.items() if k not in _CHAOS_OPTIONS})
    return chaos_call(fn, *args, faults=selected, **kwargs)
