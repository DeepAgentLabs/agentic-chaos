from rich import box
from rich.console import Console
from rich.table import Table

from agentic_chaos.models.agent_topology import AgentTopology
from agentic_chaos.models.chaos_event import ChaosEvent

_OUTCOME_STYLES = {
    "errored": "red",
    "degraded": "red",
    "delayed": "yellow",
    "looped": "magenta",
}


def render_chaos_events(console: Console, events: list[ChaosEvent]) -> None:
    """Render recorded `ChaosEvent`s as a table."""
    if not events:
        console.print("[green]No faults triggered.[/green]")
        return

    table = Table(title="Chaos Events", box=box.SIMPLE_HEAVY)
    table.add_column("Step")
    table.add_column("Fault")
    table.add_column("Outcome")
    table.add_column("Message")

    for event in events:
        style = _OUTCOME_STYLES.get(event.outcome, "white")
        table.add_row(
            event.step_name or event.step_id or "n/a",
            event.fault_type,
            f"[{style}]{event.outcome}[/{style}]",
            event.message,
        )

    console.print(table)
    console.print(f"\n[bold]{len(events)}[/bold] chaos event(s) recorded.")


def render_topology(console: Console, topology: AgentTopology) -> None:
    """Render an `AgentTopology` as a table of nodes and edges."""
    if not topology.nodes:
        return

    node_table = Table(title="Agent Topology — Nodes", box=box.SIMPLE_HEAVY)
    node_table.add_column("Name")
    node_table.add_column("Type")
    for node in topology.nodes:
        node_table.add_row(node.name, node.type)
    console.print(node_table)

    if topology.edges:
        nodes_by_id = {n.id: n.name for n in topology.nodes}
        edge_table = Table(title="Agent Topology — Edges", box=box.SIMPLE_HEAVY)
        edge_table.add_column("Source")
        edge_table.add_column("Target")
        edge_table.add_column("Type")
        for edge in topology.edges:
            edge_table.add_row(
                nodes_by_id.get(edge.source_id, edge.source_id),
                nodes_by_id.get(edge.target_id, edge.target_id),
                edge.message_type,
            )
        console.print(edge_table)

    console.print(
        f"\n[bold]{len(topology.nodes)}[/bold] node(s), [bold]{len(topology.edges)}[/bold] edge(s)."
    )
