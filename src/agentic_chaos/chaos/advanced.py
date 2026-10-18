"""Bounded, sequential fault campaigns and reproducible threshold discovery."""

import math
import time
import uuid
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from agentic_chaos.chaos.context import get_active_session
from agentic_chaos.chaos.faults import BaseFault, FaultOutcome, RateLimitStormFault
from agentic_chaos.chaos.session import chaos_session


class FaultCascade(BaseFault):
    """Apply one eligible stage per call, advancing after a triggered outcome.

    Exhaustible stages (such as a rate-limit burst) finish before the next
    stage. Other stages run once. Instances are sequential and session-local.
    """

    name = "cascade"

    def __init__(self, first: BaseFault, then: BaseFault, delay_between: float = 0) -> None:
        super().__init__()
        if not math.isfinite(delay_between) or delay_between < 0:
            raise ValueError("delay_between must be finite and non-negative")
        if first is then or isinstance(first, FaultCascade) or isinstance(then, FaultCascade):
            raise ValueError("cascade stages must be distinct, non-cascade faults")
        if any(
            isinstance(stage, RateLimitStormFault) and stage.burst_count < 1
            for stage in (first, then)
        ):
            raise ValueError("cascade rate-limit stages require a positive burst_count")
        self.stages = [first, then]
        self.delay_between = delay_between
        self.index = 0
        self.id = str(uuid.uuid4())
        self._due = 0.0

    def __copy__(self) -> "FaultCascade":
        return deepcopy(self)

    def eligible(self, **kwargs: Any) -> bool:
        return self.index < len(self.stages) and self.stages[self.index].eligible(**kwargs)

    def should_trigger(self) -> bool:
        return self.index < len(self.stages) and self.stages[self.index].should_trigger()

    def advance_preview(self) -> None:
        stage = self.stages[self.index]
        stage.advance_preview()
        if not stage.eligible() or not isinstance(stage, RateLimitStormFault):
            self.index += 1

    def trigger(self, call: Callable[..., Any], **kwargs: Any) -> FaultOutcome:
        from agentic_chaos.chaos.inject import _trigger_kwargs

        stage = self.stages[self.index]
        delay = max(0.0, self._due - time.monotonic())
        if delay:
            time.sleep(delay)
        session = get_active_session()
        if session is not None:
            session.safety.check()
        selection = {
            key: kwargs.get(key) for key in ("step_name", "edge_id", "from_node", "to_node")
        }
        outcome = stage.trigger(
            call,
            step_id=kwargs.get("step_id"),
            step_name=kwargs.get("step_name"),
            **_trigger_kwargs(
                stage,
                kwargs.get("call_args", ()),
                kwargs.get("call_kwargs") or {},
                kwargs.get("edge_id"),
                kwargs.get("from_node"),
                kwargs.get("to_node"),
            ),
        )
        if outcome.event is not None:
            outcome.event.detail.update({"cascade_id": self.id, "cascade_stage": self.index})
            stage_index = self.index
            if not stage.eligible(**selection) or not isinstance(stage, RateLimitStormFault):
                self.index += 1
            if self.index != stage_index:
                self._due = time.monotonic() + self.delay_between
        return outcome


def cascade(*, first: BaseFault, then: BaseFault, delay_between: float = 0) -> FaultCascade:
    """Build a two-stage cascade for ``chaos_session([cascade(...)])``."""
    return FaultCascade(first, then, delay_between)


@dataclass(frozen=True)
class BreakingPointResult:
    breaking_point: int | None
    trials: tuple[tuple[int, bool], ...]
    assumption: str = "recovery is deterministic and monotonic over the inclusive range"


def find_breaking_point(
    app: Callable[[], Any],
    *,
    fault: Callable[..., BaseFault],
    param: str,
    range: tuple[int, int],
    recovered: Callable[[Any], bool] | None = None,
    fault_kwargs: dict[str, Any] | None = None,
) -> BreakingPointResult:
    """Binary search first failing severity using a fresh fault/session per trial.

    Exceptions from the target count as failure. Setup and predicate errors
    propagate. The caller must reset external application state per invocation.
    """
    if get_active_session() is not None:
        raise ValueError("breaking-point search requires no active chaos session")
    low, high = range
    if any(isinstance(v, bool) or not isinstance(v, int) for v in range) or low > high:
        raise ValueError("range must be an ordered inclusive pair of integers")
    if not param or param in (fault_kwargs or {}):
        raise ValueError("param must be nonempty and absent from fault_kwargs")
    trials: list[tuple[int, bool]] = []
    point = None
    while low <= high:
        severity = (low + high) // 2
        configured = fault(**{**(fault_kwargs or {}), param: severity})
        with chaos_session([configured]):
            try:
                output = app()
            except Exception:
                passed = False
            else:
                passed = recovered(output) if recovered is not None else True
        trials.append((severity, passed))
        if passed:
            low = severity + 1
        else:
            point, high = severity, severity - 1
    return BreakingPointResult(point, tuple(trials))
