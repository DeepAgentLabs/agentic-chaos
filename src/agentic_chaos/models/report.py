import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChaosReport(BaseModel):
    """Standalone report of a chaos run -- no other library required to
    produce or read it.

    Deliberately uses the same top-level field names AgenticLens's
    `Workflow` does for the fields both share (`id`, `name`, `start_time`,
    `end_time`, `chaos_events`) -- not because agentic-chaos depends on
    AgenticLens (it doesn't), but so that *if* you also have AgenticLens
    installed, `agenticlens analyze report.json` can load this file directly:
    AgenticLens's `steps` field defaults to empty, so a `ChaosReport`'s JSON
    is valid `Workflow` JSON as-is. Interop through a shared, documented JSON
    shape, not a code dependency.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    start_time: datetime
    end_time: datetime | None = None
    chaos_events: list[dict[str, Any]] = Field(default_factory=list)
    agent_topology: dict[str, Any] | None = None
    drift_report: dict[str, Any] | None = None
    aborted: bool = False
    abort_reason: dict[str, Any] | None = None
    dry_run: bool = False
    planned_events: list[dict[str, Any]] = Field(default_factory=list)
    cost_usd: float = 0.0
    injections: int = 0
    in_flight: int = 0
    calls: list[dict[str, Any]] = Field(default_factory=list)
    calls_dropped: int = 0
    unhandled_error: dict[str, Any] | None = None
    # v0.8: set when the report merges the steps of a chaos workflow; per-step
    # provenance is also recorded in each event's ``detail.workflow``.
    workflow: dict[str, Any] | None = None
    # v0.9: steady-state probe results (pre/during/post) and the resilience
    # score computed from this report; both are absent on older reports.
    probes: list[dict[str, Any]] = Field(default_factory=list)
    resilience: dict[str, Any] | None = None

    @property
    def resilience_score(self) -> int | None:
        """The 0-100 resilience score, or None when it was not computed or is inconclusive."""
        if self.resilience is None:
            return None
        score = self.resilience.get("score")
        return score if isinstance(score, int) and not isinstance(score, bool) else None
