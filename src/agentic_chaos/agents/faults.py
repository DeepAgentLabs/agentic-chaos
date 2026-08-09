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
    snapshot_baseline,
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
# Shared mutation helpers
# ---------------------------------------------------------------------------


def _mutate_payload(value: Any, mutator: Callable[[str], str]) -> Any:
    """Best-effort payload mutation across common handoff/state shapes."""
    if isinstance(value, str):
        return mutator(value)
    if isinstance(value, list):
        return [_mutate_payload(item, mutator) for item in value]
    if isinstance(value, tuple):
        return tuple(_mutate_payload(item, mutator) for item in value)
    if isinstance(value, dict):
        mutated = dict(value)
        for key in ("content", "text", "message", "input", "state"):
            if key in mutated:
                mutated[key] = _mutate_payload(mutated[key], mutator)
                return mutated
        return mutated
    return mutate_text_attrs(value, mutator)


def _mutate_handoff_args(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    mutator: Callable[[str], str],
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Mutate the most likely payload-bearing argument."""
    if args:
        mutated_args = list(args)
        mutated_args[0] = _mutate_payload(mutated_args[0], mutator)
        return tuple(mutated_args), kwargs

    mutated_kwargs = dict(kwargs)
    for key in ("state", "message", "payload", "input", "content", "text"):
        if key in mutated_kwargs:
            mutated_kwargs[key] = _mutate_payload(mutated_kwargs[key], mutator)
            break
    return args, mutated_kwargs


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
        call: Callable[..., Any],
        *,
        step_id: str | None,
        step_name: str | None,
        call_args: tuple[Any, ...] = (),
        call_kwargs: dict[str, Any] | None = None,
        edge_id: str | None = None,
        from_node: str | None = None,
        to_node: str | None = None,
    ) -> FaultOutcome:
        call_kwargs = call_kwargs or {}
        # If tool_name is set, only fire for matching step_name.
        if self.tool_name is not None and step_name != self.tool_name:
            return FaultOutcome(result=call(*call_args, **call_kwargs))

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
            baseline = call(*call_args, **call_kwargs)  # real call happens, but result is discarded
            message = "tool returned empty/null result (real output discarded)"
            event = ChaosEvent(
                fault_type=self.name,
                step_id=step_id,
                step_name=step_name,
                outcome="degraded",
                message=message,
                detail=detail,
            )
            return FaultOutcome(result=None, event=event, baseline=baseline)

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


def _decay_result(result: Any, rng: random.Random, progress: float) -> Any:
    """Progressively increase corruption severity over repeated turns."""
    progress = max(0.0, min(progress, 1.0))
    if isinstance(result, str):
        keep = max(1, int(len(result) * (1.0 - progress * 0.7)))
        truncated = result[:keep]
        return garble_text(truncated, rng)
    if isinstance(result, list):
        keep = max(1, int(len(result) * (1.0 - progress * 0.7)))
        return [_decay_result(item, rng, progress) for item in result[:keep]]
    if isinstance(result, dict):
        keys = list(result.keys())
        rng.shuffle(keys)
        keep = max(1, int(len(keys) * (1.0 - progress * 0.6)))
        return {key: _decay_result(result[key], rng, progress) for key in keys[:keep]}

    def _decay_text(text: str) -> str:
        keep = max(1, int(len(text) * (1.0 - progress * 0.7)))
        return garble_text(text[:keep], rng)

    return _mutate_payload(result, _decay_text)


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
        "decay": None,
    }

    def __init__(
        self,
        mode: str = "garble",
        seed: int | None = None,
        rate: float = 0.25,
    ) -> None:
        if mode not in self._CORRUPTORS:
            raise ValueError(f"mode must be one of {sorted(self._CORRUPTORS)}")
        if mode == "decay" and not 0.0 < rate <= 1.0:
            raise ValueError("rate must be between 0.0 and 1.0 for decay mode")
        self.mode = mode
        self._rng = random.Random(seed)
        self.rate = rate
        self._turn = 0

    def trigger(
        self,
        call: Callable[..., Any],
        *,
        step_id: str | None,
        step_name: str | None,
        call_args: tuple[Any, ...] = (),
        call_kwargs: dict[str, Any] | None = None,
        edge_id: str | None = None,
        from_node: str | None = None,
        to_node: str | None = None,
    ) -> FaultOutcome:
        call_kwargs = call_kwargs or {}
        result = call(*call_args, **call_kwargs)
        baseline = snapshot_baseline(result)
        if self.mode == "decay":
            self._turn += 1
            progress = min(1.0, self._turn * self.rate)
            corrupted = _decay_result(result, self._rng, progress)
            detail = {
                "mode": self.mode,
                "turn": self._turn,
                "rate": self.rate,
                "progress": progress,
            }
            message = f"agent state decayed over turn {self._turn} (progress={progress:.2f})"
        else:
            corruptor = self._CORRUPTORS[self.mode]
            assert corruptor is not None
            corrupted = corruptor(result, self._rng)
            detail = {"mode": self.mode}
            message = f"agent state corrupted via {self.mode}"
        event = ChaosEvent(
            fault_type=self.name,
            step_id=step_id,
            step_name=step_name,
            outcome="degraded",
            message=message,
            detail=detail,
        )
        return FaultOutcome(result=corrupted, event=event, baseline=baseline)


# ---------------------------------------------------------------------------
# HandoffCorruptionFault
# ---------------------------------------------------------------------------


class HandoffCorruptionFault(BaseFault):
    """Corrupt the payload passed between two nodes instead of a node itself.

    In ``"corrupt"`` mode this mutates the payload before delivery and calls
    the downstream node exactly once. That keeps edge faults safe for
    side-effecting nodes, but it also means no clean baseline result exists
    for comparative fidelity scoring unless the caller captures one
    separately.
    """

    name = "handoff_corruption"

    def __init__(
        self,
        *,
        from_node: str | None = None,
        to_node: str | None = None,
        mode: str = "corrupt",
        delay_seconds: float = 1.0,
        seed: int | None = None,
    ) -> None:
        if mode not in ("corrupt", "drop", "delay"):
            raise ValueError("mode must be 'corrupt', 'drop', or 'delay'")
        self.from_node = from_node
        self.to_node = to_node
        self.mode = mode
        self.delay_seconds = delay_seconds
        self._rng = random.Random(seed)

    def trigger(
        self,
        call: Callable[..., Any],
        *,
        step_id: str | None,
        step_name: str | None,
        call_args: tuple[Any, ...] = (),
        call_kwargs: dict[str, Any] | None = None,
        edge_id: str | None = None,
        from_node: str | None = None,
        to_node: str | None = None,
    ) -> FaultOutcome:
        call_kwargs = call_kwargs or {}
        if edge_id is None:
            return FaultOutcome(result=call(*call_args, **call_kwargs))
        if self.from_node is not None and self.from_node != from_node:
            return FaultOutcome(result=call(*call_args, **call_kwargs))
        if self.to_node is not None and self.to_node != to_node:
            return FaultOutcome(result=call(*call_args, **call_kwargs))

        detail: dict[str, Any] = {"mode": self.mode}
        if self.from_node is not None:
            detail["target_from_node"] = self.from_node
        if self.to_node is not None:
            detail["target_to_node"] = self.to_node

        if self.mode == "drop":
            event = ChaosEvent(
                fault_type=self.name,
                step_id=step_id,
                step_name=step_name,
                outcome="degraded",
                message="handoff payload dropped before reaching destination node",
                edge_id=edge_id,
                from_node=from_node,
                to_node=to_node,
                detail=detail,
            )
            return FaultOutcome(result=None, event=event)

        if self.mode == "delay":
            time.sleep(self.delay_seconds)
            detail["delay_seconds"] = self.delay_seconds
            result = call(*call_args, **call_kwargs)
            event = ChaosEvent(
                fault_type=self.name,
                step_id=step_id,
                step_name=step_name,
                outcome="delayed",
                message=f"handoff delayed {self.delay_seconds:.1f}s before delivery",
                edge_id=edge_id,
                from_node=from_node,
                to_node=to_node,
                detail=detail,
            )
            return FaultOutcome(result=result, event=event)

        mutated_args, mutated_kwargs = _mutate_handoff_args(
            call_args,
            call_kwargs,
            lambda text: garble_text(text, self._rng),
        )
        corrupted = call(*mutated_args, **mutated_kwargs)
        event = ChaosEvent(
            fault_type=self.name,
            step_id=step_id,
            step_name=step_name,
            outcome="degraded",
            message="handoff payload corrupted in transit",
            edge_id=edge_id,
            from_node=from_node,
            to_node=to_node,
            detail=detail,
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
        call: Callable[..., Any],
        *,
        step_id: str | None,
        step_name: str | None,
        call_args: tuple[Any, ...] = (),
        call_kwargs: dict[str, Any] | None = None,
        edge_id: str | None = None,
        from_node: str | None = None,
        to_node: str | None = None,
    ) -> FaultOutcome:
        call_kwargs = call_kwargs or {}
        result = call(*call_args, **call_kwargs)

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
FAULT_REGISTRY["handoff_corruption"] = HandoffCorruptionFault
