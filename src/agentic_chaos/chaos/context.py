from collections.abc import Callable
from contextvars import ContextVar
from copy import copy, deepcopy
from typing import Any

from agentic_chaos.chaos.faults import BaseFault
from agentic_chaos.models.chaos_event import ChaosEvent
from agentic_chaos.safety import CircuitBreaker, SafetyState


class ChaosSession:
    """Holds the faults active for a `with chaos_session(...):` block and the
    `ChaosEvent`s recorded while it was active."""

    def __init__(
        self,
        faults: list[BaseFault],
        *,
        breaker: CircuitBreaker | None = None,
        dry_run: bool = False,
        safety: SafetyState | None = None,
    ) -> None:
        self.faults = faults
        self.dry_run = dry_run
        self._preview_faults: dict[int, BaseFault] = {}
        self.planned_events: list[dict[str, Any]] = []
        self.safety = safety if safety is not None else SafetyState(breaker)
        self.events: list[ChaosEvent] = []
        self.cleanups: list[Callable[[], None]] = []

    def preview_fault(self, fault: BaseFault) -> BaseFault:
        """Keep selection RNG and stateful eligibility separate from real faults."""
        key = id(fault)
        if key not in self._preview_faults:
            shadow = copy(fault)
            shadow._trigger_rng = deepcopy(fault._trigger_rng)
            self._preview_faults[key] = shadow
        return self._preview_faults[key]

    def record_cost(self, cost_usd: float) -> None:
        """Record actual/estimated cost explicitly; may raise ChaosAbortedError."""
        self.safety.record_cost(cost_usd)

    def record_usage(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        input_usd_per_million: float,
        output_usd_per_million: float,
    ) -> None:
        """Record tokens using caller-supplied prices; pricing is never inferred."""
        import math

        for value in (input_tokens, output_tokens):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("token counts must be non-negative integers")
        for price in (input_usd_per_million, output_usd_per_million):
            if isinstance(price, bool) or not math.isfinite(price) or price < 0:
                raise ValueError("prices must be finite and non-negative")
        self.record_cost(
            (input_tokens * input_usd_per_million + output_tokens * output_usd_per_million)
            / 1_000_000
        )

    def plan(self, fault: BaseFault, step_id: str | None, step_name: str | None) -> None:
        self.safety.check()
        self.planned_events.append(
            {
                "fault_type": fault.name,
                "step_id": step_id,
                "step_name": step_name,
                "outcome": "would_inject",
            }
        )

    def report_fields(self) -> dict[str, Any]:
        return {
            **self.safety.snapshot(),
            "dry_run": self.dry_run,
            "planned_events": list(self.planned_events),
        }

    def events_as_json(self) -> list[dict[str, Any]]:
        """JSON-serialized events, ready to drop into any `chaos_events` array
        -- this package's own `ChaosReport`, or (via the optional
        `agentic_chaos.integrations.agenticlens` adapter) an AgenticLens
        `Workflow`'s `chaos_events` field (schema v1.1)."""
        return [event.model_dump(mode="json") for event in self.events]

    def select_faults(self, names: list[str] | None) -> list[BaseFault]:
        """Return the configured faults matching `names`, or all of them if
        `names` is `None`. Raises if a requested name wasn't configured for
        this session."""
        if names is None:
            return self.faults
        by_name = {fault.name: fault for fault in self.faults}
        try:
            return [by_name[name] for name in names]
        except KeyError as exc:
            known = ", ".join(sorted(by_name))
            raise ValueError(
                f"Fault {exc} was not configured for this chaos_session(). "
                f"Configured faults: {known}"
            ) from exc


active_session: ContextVar[ChaosSession | None] = ContextVar("active_session", default=None)


def get_active_session() -> ChaosSession | None:
    """Return the chaos session active in the current context, or `None`.

    Unlike AgenticLens's `get_active_workflow()`, this does not raise when no
    session is active -- `chaos_call()` treats "no session" as "call through
    with no chaos applied" so instrumented code behaves identically outside a
    `chaos_session(...)` block.
    """
    return active_session.get()
