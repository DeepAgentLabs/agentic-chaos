import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

Outcome = Literal["errored", "degraded", "delayed", "looped"]


class ChaosEvent(BaseModel):
    """One occurrence of a fault firing on a wrapped call.

    Serializes into the `chaos_events` array of AgenticLens's `workflow.json`
    (schema v1.1 -- see agenticlens's docs/workflow-schema-spec.md). Kept as a
    typed model on this side of the boundary; AgenticLens itself treats each
    entry as a loosely-typed dict so it has no import-time dependency on this
    package.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fault_type: str
    step_id: str | None = None
    step_name: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    outcome: Outcome
    message: str
    fidelity_score: float | None = None
    edge_id: str | None = None
    from_node: str | None = None
    to_node: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
