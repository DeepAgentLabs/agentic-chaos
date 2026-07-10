from contextvars import ContextVar
from typing import Any

from agentic_chaos.chaos.faults import BaseFault
from agentic_chaos.models.chaos_event import ChaosEvent


class ChaosSession:
    """Holds the faults active for a `with chaos_session(...):` block and the
    `ChaosEvent`s recorded while it was active."""

    def __init__(self, faults: list[BaseFault]) -> None:
        self.faults = faults
        self.events: list[ChaosEvent] = []

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
