"""Optional LangGraph adapter for agent-level chaos injection.

Provides utilities to wrap LangGraph tool functions and graph nodes with
`chaos_call()` so faults are injected transparently during graph execution.
Also integrates with `TopologyTracker` to record the agent topology.

LangGraph is **not** a required dependency — this module is only useful if
you have it installed. Imports are guarded behind `TYPE_CHECKING`.
"""

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

from agentic_chaos.agents.topology import TopologyTracker
from agentic_chaos.chaos.inject import chaos_call

if TYPE_CHECKING:
    pass  # LangGraph types would go here once we add type stubs

T = TypeVar("T")


def wrap_tool(
    fn: Callable[..., T],
    *,
    tool_name: str | None = None,
    faults: list[str] | None = None,
    tracker: TopologyTracker | None = None,
    caller_node: str | None = None,
) -> Callable[..., T]:
    """Wrap a tool function for chaos injection and optional topology tracking.

    The returned wrapper calls ``chaos_call(fn, ...)`` with
    ``step_name=tool_name`` so that ``ToolCallFailureFault(tool_name=...)`` can
    target this specific tool.

    If a ``tracker`` is provided, registers the tool as a ``"tool"`` node and
    (when ``caller_node`` is given) records a ``"tool_call"`` edge from
    ``caller_node``. If ``caller_node`` is ``None``, only the node is
    registered — no edge is recorded.

    ```python
    tracker = TopologyTracker()
    search = wrap_tool(raw_search, tool_name="search", tracker=tracker, caller_node="Agent")

    with chaos_session([ToolCallFailureFault(tool_name="search")]):
        search("query")  # fault fires here
    ```
    """
    name = tool_name or getattr(fn, "__name__", "unknown_tool")

    @wraps(fn)
    def wrapped(*args: Any, **kwargs: Any) -> T:
        if tracker is not None:
            tracker.register_node(name, type="tool")
            if caller_node is not None:
                tracker.record_edge(
                    caller_node,
                    name,
                    message_type="tool_call",
                    source_type="agent",
                    target_type="tool",
                )
        return chaos_call(
            fn, *args, step_id=name, step_name=name, faults=faults, **kwargs
        )

    return wrapped


def wrap_node(
    fn: Callable[..., T],
    *,
    node_name: str | None = None,
    node_type: str = "agent",
    faults: list[str] | None = None,
    tracker: TopologyTracker | None = None,
    caller_node: str | None = None,
) -> Callable[..., T]:
    """Wrap a LangGraph node function for chaos injection.

    Similar to `wrap_tool()` but uses ``node_type`` (default ``"agent"``)
    instead of ``"tool"`` for topology tracking, and records a ``"handoff"``
    edge from ``caller_node`` (when provided). If ``caller_node`` is ``None``,
    only the node is registered — no edge is recorded.

    ```python
    planner = wrap_node(planner_fn, node_name="Planner", tracker=tracker, caller_node="Router")
    ```
    """
    name = node_name or getattr(fn, "__name__", "unknown_node")

    @wraps(fn)
    def wrapped(*args: Any, **kwargs: Any) -> T:
        if tracker is not None:
            tracker.register_node(name, type=node_type)
            if caller_node is not None:
                tracker.record_edge(
                    caller_node,
                    name,
                    message_type="handoff",
                    source_type="agent",
                    target_type=node_type,
                )
        return chaos_call(
            fn, *args, step_id=name, step_name=name, faults=faults, **kwargs
        )

    return wrapped
