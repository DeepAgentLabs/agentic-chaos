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
