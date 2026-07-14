"""Agent topology data model — tracks which agent/node communicated with
which during a chaos run (schema extension v1.2).
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class AgentNode(BaseModel):
    """A node in the agent topology graph (an agent, tool, memory store, or router)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: str = "agent"  # "agent", "tool", "memory", "router"


class AgentEdge(BaseModel):
    """A directed edge representing communication between two topology nodes."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    target_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message_type: str = "call"  # "tool_call", "tool_result", "memory_read", etc.


class AgentTopology(BaseModel):
    """The full topology graph of an agent run — which nodes exist and how
    they communicated.

    Serializes into the ``agent_topology`` field of a ``ChaosReport``
    (schema v1.2). AgenticLens's ``AgentResilienceRecommender`` reads this
    to produce resilience scores at the workflow level.
    """

    nodes: list[AgentNode] = Field(default_factory=list)
    edges: list[AgentEdge] = Field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        """JSON-serialized topology, ready to embed in a ``ChaosReport``."""
        return self.model_dump(mode="json")
