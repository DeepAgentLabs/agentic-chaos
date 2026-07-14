"""Agent-level fault types for v0.2: tool-call failure, memory corruption,
and infinite-loop triggering.

These faults extend the same `BaseFault` / `chaos_call()` / `chaos_session()`
engine from v0.1 and are registered in the global `FAULT_REGISTRY` so the CLI
and `resolve_faults()` can find them by name.
"""

import random
import time
from collections.abc import Callable
from typing import Any

from agentic_chaos.chaos.faults import (
    FAULT_REGISTRY,
    BaseFault,
    ChaosFaultError,
    FaultOutcome,
    garble_text,
    mutate_text_attrs,
)
from agentic_chaos.models.chaos_event import ChaosEvent

# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------


class ToolCallFailureError(ChaosFaultError):
    """Raised by `ToolCallFailureFault` to simulate a tool execution error."""


class InfiniteLoopError(ChaosFaultError):
    """Raised by `InfiniteLoopFault` when `raise_after` is enabled and the
    forced-turn budget is exhausted."""


# ---------------------------------------------------------------------------
# ToolCallFailureFault
# ---------------------------------------------------------------------------


class ToolCallFailureFault(BaseFault):
    """Force a tool call to fail — raise an error, simulate a timeout, or
    return empty/null data.

    When `tool_name` is set, the fault only fires for `chaos_call()` invocations
    whose `step_name` matches; other calls pass through untouched. When
    `tool_name` is `None` (the default), every call is a target.

    Modes:
    - ``"error"`` — raise `ToolCallFailureError` immediately (real call never
      happens).
    - ``"timeout"`` — sleep for `timeout_seconds`, then raise
      `ToolCallFailureError`.
    - ``"empty"`` — call the real function but discard its result and return
      `None` (outcome: ``"degraded"``).
    """

    name = "tool_failure"

    def __init__(
        self,
        mode: str = "error",
        timeout_seconds: float = 5.0,
        error_message: str = "Tool execution failed",
        tool_name: str | None = None,
    ) -> None:
        if mode not in ("error", "timeout", "empty"):
            raise ValueError("mode must be 'error', 'timeout', or 'empty'")
        self.mode = mode
        self.timeout_seconds = timeout_seconds
        self.error_message = error_message
        self.tool_name = tool_name

    def trigger(
        self,
        call: Callable[[], Any],
        *,
        step_id: str | None,
        step_name: str | None,
    ) -> FaultOutcome:
        # If tool_name is set, only fire for matching step_name.
        if self.tool_name is not None and step_name != self.tool_name:
            return FaultOutcome(result=call())

        detail: dict[str, Any] = {
            "mode": self.mode,
            "tool_name": self.tool_name,
        }

        if self.mode == "timeout":
            time.sleep(self.timeout_seconds)
            detail["timeout_seconds"] = self.timeout_seconds
            message = f"tool timed out after {self.timeout_seconds:.1f}s: {self.error_message}"
            event = ChaosEvent(
                fault_type=self.name,
                step_id=step_id,
                step_name=step_name,
                outcome="errored",
                message=message,
                detail=detail,
            )
            return FaultOutcome(event=event, raised=ToolCallFailureError(message, event))

        if self.mode == "empty":
            call()  # real call happens, but result is discarded
            message = "tool returned empty/null result (real output discarded)"
            event = ChaosEvent(
                fault_type=self.name,
                step_id=step_id,
                step_name=step_name,
                outcome="degraded",
                message=message,
                detail=detail,
            )
            return FaultOutcome(result=None, event=event)

        # mode == "error"
        message = f"tool execution failed: {self.error_message}"
        event = ChaosEvent(
            fault_type=self.name,
            step_id=step_id,
            step_name=step_name,
            outcome="errored",
            message=message,
            detail=detail,
        )
        return FaultOutcome(event=event, raised=ToolCallFailureError(message, event))


# ---------------------------------------------------------------------------
# MemoryCorruptionFault
# ---------------------------------------------------------------------------


def _truncate_result(result: Any, rng: random.Random) -> Any:
    """Truncate the result to roughly half its content."""
    if isinstance(result, str):
        cut = max(1, len(result) // 2)
        return result[:cut]
    if isinstance(result, list):
        cut = max(1, len(result) // 2)
        return result[:cut]
    if isinstance(result, dict):
        keys = list(result.keys())
        keep = max(1, len(keys) // 2)
        rng.shuffle(keys)
        return {k: result[k] for k in keys[:keep]}
    return mutate_text_attrs(result, lambda text: text[: max(1, len(text) // 2)])


def _inject_garbage(result: Any, rng: random.Random) -> Any:
    """Inject garbage data into the result."""
    garbage = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(20))
    if isinstance(result, str):
        pos = rng.randint(0, max(0, len(result)))
        return result[:pos] + f" [INJECTED: {garbage}] " + result[pos:]
    if isinstance(result, list):
        pos = rng.randint(0, len(result))
        list_copy = list(result)
        list_copy.insert(pos, f"__garbage_{garbage}__")
        return list_copy
    if isinstance(result, dict):
        dict_copy = dict(result)
        dict_copy[f"__injected_{rng.randint(0, 999)}__"] = garbage
        return dict_copy

    def _inject_into_text(text: str) -> str:
        pos = rng.randint(0, max(0, len(text)))
        return text[:pos] + f" [INJECTED: {garbage}] " + text[pos:]

    return mutate_text_attrs(result, _inject_into_text)


def _garble_result(result: Any, rng: random.Random) -> Any:
    """Garble text content in the result using the existing garble_text utility."""
    return mutate_text_attrs(result, lambda text: garble_text(text, rng))


class MemoryCorruptionFault(BaseFault):
    """Corrupt shared agent state — truncate, inject garbage, or garble content.

    Calls the real function to get a genuine result, then corrupts it before
    returning. Simulates corrupted shared memory, stale caches, or damaged
    state stores that multi-agent systems rely on.

    Modes:
    - ``"truncate"`` — cut the result to roughly half its content.
    - ``"inject"`` — insert garbage data into a random position.
    - ``"garble"`` — replace alphabetic content with random letters (preserves
      shape, like `SilentDegradationFault`).
    """

    name = "memory_corruption"

    _CORRUPTORS = {
        "truncate": _truncate_result,
        "inject": _inject_garbage,
        "garble": _garble_result,
    }

    def __init__(self, mode: str = "garble", seed: int | None = None) -> None:
        if mode not in self._CORRUPTORS:
            raise ValueError(f"mode must be one of {sorted(self._CORRUPTORS)}")
        self.mode = mode
        self._rng = random.Random(seed)

    def trigger(
        self,
        call: Callable[[], Any],
        *,
        step_id: str | None,
        step_name: str | None,
    ) -> FaultOutcome:
        result = call()
        corrupted = self._CORRUPTORS[self.mode](result, self._rng)
        event = ChaosEvent(
            fault_type=self.name,
            step_id=step_id,
            step_name=step_name,
            outcome="degraded",
            message=f"agent state corrupted via {self.mode}",
            detail={"mode": self.mode},
        )
        return FaultOutcome(result=corrupted, event=event)


# ---------------------------------------------------------------------------
# InfiniteLoopFault
# ---------------------------------------------------------------------------


class InfiniteLoopFault(BaseFault):
    """Force an agent to loop past its normal termination point.

    For the first `force_turns` calls, replaces the real return value with
    `continue_value` (a response that tells the agent to keep going). After
    that, passes through normally so the agent can terminate.

    Use this to test whether your agent has turn-limit safeguards and whether
    it degrades gracefully under excessive iterations.
    """

    name = "infinite_loop"

    def __init__(
        self,
        force_turns: int = 5,
        continue_value: Any = "I need to continue processing this request.",
    ) -> None:
        self.force_turns = force_turns
        self.continue_value = continue_value
        self._fired = 0

    def trigger(
        self,
        call: Callable[[], Any],
        *,
        step_id: str | None,
        step_name: str | None,
    ) -> FaultOutcome:
        result = call()

        if self._fired >= self.force_turns:
            return FaultOutcome(result=result)

        self._fired += 1
        event = ChaosEvent(
            fault_type=self.name,
            step_id=step_id,
            step_name=step_name,
            outcome="looped",
            message=(
                f"forced extra turn {self._fired}/{self.force_turns} (original result replaced)"
            ),
            detail={
                "forced_turn": self._fired,
                "force_turns": self.force_turns,
            },
        )
        return FaultOutcome(result=self.continue_value, event=event)


# ---------------------------------------------------------------------------
# Register v0.2 faults in the global FAULT_REGISTRY
# ---------------------------------------------------------------------------

FAULT_REGISTRY["tool_failure"] = ToolCallFailureFault
FAULT_REGISTRY["memory_corruption"] = MemoryCorruptionFault
FAULT_REGISTRY["infinite_loop"] = InfiniteLoopFault
