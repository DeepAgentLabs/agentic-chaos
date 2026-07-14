"""Topology tracker — records which agents/tools/nodes communicated with each
other during a chaos run.

Instantiate a `TopologyTracker`, register nodes, record edges, then dump the
resulting `AgentTopology` into the `ChaosReport.agent_topology` field.

A module-level `_active_tracker` contextvar makes the most recently created
tracker discoverable by the CLI (similar to how `active_session` works for
`ChaosSession`).
"""

from contextvars import ContextVar, Token

from agentic_chaos.models.agent_topology import AgentEdge, AgentNode, AgentTopology

_active_tracker: ContextVar["TopologyTracker | None"] = ContextVar(
    "_active_tracker", default=None
)


def get_active_tracker() -> "TopologyTracker | None":
    """Return the topology tracker active in the current context, or `None`."""
    return _active_tracker.get()


def reset_active_tracker() -> None:
    """Clear the active tracker contextvar. Called by the CLI after reading
    the tracker to prevent leaking across sequential invocations."""
    _active_tracker.set(None)


class TopologyTracker:
    """Incrementally builds an `AgentTopology` as an agent graph executes.

    Thread-safe for single-writer use (the typical chaos-session pattern).
    Automatically registers itself as the active tracker (discoverable by the
    CLI via `get_active_tracker()`). Pass `auto_activate=False` to opt out.

    Can also be used as a context manager — on exit it resets the contextvar:

    ```python
    with TopologyTracker() as tracker:
        tracker.register_node("Planner", type="agent")
        tracker.register_node("search_tool", type="tool")
        tracker.record_edge("Planner", "search_tool", message_type="tool_call")
    # tracker is no longer active after the block
    ```
    """

    def __init__(self, *, auto_activate: bool = True) -> None:
        self.topology = AgentTopology()
        self._nodes_by_name: dict[str, AgentNode] = {}
        self._token: Token[TopologyTracker | None] | None = (
            _active_tracker.set(self) if auto_activate else None
        )

    def __enter__(self) -> "TopologyTracker":
        return self

    def __exit__(self, *_: object) -> None:
        self.deactivate()

    def deactivate(self) -> None:
        """Reset the contextvar so this tracker is no longer active."""
        if self._token is not None:
            _active_tracker.reset(self._token)
            self._token = None

    def register_node(self, name: str, type: str = "agent") -> AgentNode:
        """Register a node by name. Idempotent — returns the existing node
        without modifying its type. To explicitly change a node's type after
        registration, use `set_node_type()`."""
        if name not in self._nodes_by_name:
            node = AgentNode(name=name, type=type)
            self._nodes_by_name[name] = node
            self.topology.nodes.append(node)
        return self._nodes_by_name[name]

    def set_node_type(self, name: str, type: str) -> AgentNode:
        """Explicitly update the type of an already-registered node. Raises
        `KeyError` if the node hasn't been registered yet."""
        if name not in self._nodes_by_name:
            raise KeyError(f"Node '{name}' has not been registered yet.")
        self._nodes_by_name[name].type = type
        return self._nodes_by_name[name]

    def record_edge(
        self,
        source_name: str,
        target_name: str,
        *,
        message_type: str = "call",
        source_type: str = "agent",
        target_type: str = "agent",
    ) -> AgentEdge:
        """Record a communication edge between two nodes. Auto-registers nodes
        that haven't been registered yet (using `source_type`/`target_type`).
        Does NOT overwrite the type of already-registered nodes."""
        source = self.register_node(source_name, type=source_type)
        target = self.register_node(target_name, type=target_type)
        edge = AgentEdge(
            source_id=source.id,
            target_id=target.id,
            message_type=message_type,
        )
        self.topology.edges.append(edge)
        return edge
