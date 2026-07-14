"""Agent Failure Injector — framework-level fault injection for LangGraph,
CrewAI, AutoGen (v0.2).

Provides three agent-specific fault types (`ToolCallFailureFault`,
`MemoryCorruptionFault`, `InfiniteLoopFault`), a `TopologyTracker` for
recording which agents/tools communicated, and a LangGraph adapter with
`wrap_tool()` / `wrap_node()` helpers.
"""

from agentic_chaos.agents.faults import (
    InfiniteLoopError,
    InfiniteLoopFault,
    MemoryCorruptionFault,
    ToolCallFailureError,
    ToolCallFailureFault,
)
from agentic_chaos.agents.langgraph import wrap_node, wrap_tool
from agentic_chaos.agents.topology import TopologyTracker, get_active_tracker, reset_active_tracker

__all__ = [
    "InfiniteLoopError",
    "InfiniteLoopFault",
    "MemoryCorruptionFault",
    "ToolCallFailureError",
    "ToolCallFailureFault",
    "TopologyTracker",
    "get_active_tracker",
    "reset_active_tracker",
    "wrap_node",
    "wrap_tool",
]
