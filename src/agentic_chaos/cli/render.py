from typing import TYPE_CHECKING

from rich import box
from rich.console import Console
from rich.table import Table

from agentic_chaos.contracts import ContractReport
from agentic_chaos.drift import DriftReport
from agentic_chaos.models.agent_topology import AgentTopology
from agentic_chaos.models.chaos_event import ChaosEvent

if TYPE_CHECKING:
    from agentic_chaos.experiments import ValidationResult
    from agentic_chaos.workflows import FuzzReport, NodeResult, WorkflowReport

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

    show_fidelity = any(event.fidelity_score is not None for event in events)
    table = Table(title="Chaos Events", box=box.SIMPLE_HEAVY)
    table.add_column("Step")
    table.add_column("Fault")
    table.add_column("Outcome")
    if show_fidelity:
        table.add_column("Fidelity")
    table.add_column("Message")

    for event in events:
        style = _OUTCOME_STYLES.get(event.outcome, "white")
        row = [
            event.step_name or event.step_id or "n/a",
            event.fault_type,
            f"[{style}]{event.outcome}[/{style}]",
        ]
        if show_fidelity:
            row.append(f"{event.fidelity_score:.2f}" if event.fidelity_score is not None else "-")
        row.append(event.message)
        table.add_row(*row)

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


def render_drift_report(console: Console, report: DriftReport) -> None:
    """Render a `DriftReport` as a compact findings table."""
    if not report.findings:
        console.print("[green]No comparable drift signals were provided.[/green]")
        return

    table = Table(title="Drift Findings", box=box.SIMPLE_HEAVY)
    table.add_column("Signal")
    table.add_column("Changed")
    table.add_column("Score")
    table.add_column("Message")

    for finding in report.findings:
        style = "red" if finding.changed else "green"
        score = "-"
        if finding.score is not None:
            score = f"{finding.score:.3f}"
            if finding.threshold is not None:
                score = f"{score} / {finding.threshold:.3f}"
        table.add_row(
            finding.kind,
            f"[{style}]{'yes' if finding.changed else 'no'}[/{style}]",
            score,
            finding.message,
        )

    console.print(table)
    summary_style = "red" if report.has_drift else "green"
    console.print(
        f"\n[{summary_style}]Drift detected: "
        f"{'yes' if report.has_drift else 'no'}[/{summary_style}]"
    )


_STATUS_STYLES = {"passed": "green", "failed": "red", "inconclusive": "yellow"}


def render_contract_report(console: Console, contract_report: ContractReport) -> None:
    """Render chaos contract results as a table with a pass/fail verdict."""
    table = Table(title="Chaos Contracts", box=box.SIMPLE_HEAVY)
    table.add_column("Contract")
    table.add_column("Status")
    table.add_column("Message")
    for result in contract_report.results:
        style = _STATUS_STYLES.get(result.status, "white")
        table.add_row(result.contract, f"[{style}]{result.status}[/{style}]", result.message)
    console.print(table)
    passed = len(contract_report.results) - len(contract_report.failures)
    verdict = "[green]passed[/green]" if contract_report.passed else "[red]failed[/red]"
    console.print(f"{passed}/{len(contract_report.results)} contracts passed: {verdict}")


_NODE_STYLES = {
    "passed": "green",
    "approved": "green",
    "resumed": "green",
    "failed": "red",
    "aborted": "red",
    "rejected": "red",
    "suspended": "yellow",
    "would_suspend": "yellow",
    "skipped": "dim",
}


def render_workflow_report(console: Console, report: "WorkflowReport") -> None:
    """Render a chaos workflow's node results, indenting parallel branches."""
    table = Table(title=f"Chaos Workflow — {report.name}", box=box.SIMPLE_HEAVY)
    table.add_column("Node")
    table.add_column("Kind")
    table.add_column("Status")
    table.add_column("Events", justify="right")
    table.add_column("Detail")

    def add(node: "NodeResult", depth: int) -> None:
        style = _NODE_STYLES.get(node.status, "white")
        events = len(node.report.get("chaos_events", [])) if node.report else None
        table.add_row(
            "  " * depth + node.name,
            node.kind,
            f"[{style}]{node.status}[/{style}]",
            str(events) if events is not None else "",
            node.message,
        )
        for index, branch in enumerate(node.branches, 1):
            for child in branch:
                add(child.model_copy(update={"name": f"[{index}] {child.name}"}), depth + 1)

    for node in report.nodes:
        add(node, 0)
    console.print(table)
    style = _NODE_STYLES.get(report.status, "white")
    console.print(
        f"\nWorkflow [bold]{report.name}[/bold]: [{style}]{report.status}[/{style}] "
        f"({len(report.chaos_events)} chaos event(s))"
    )
    if report.message:
        console.print(report.message)


def render_validation(console: Console, result: "ValidationResult") -> None:
    """Render one experiment's validation outcome, one issue per line."""
    if result.ok:
        console.print(f"[green]OK[/green] {result.source}")
    else:
        console.print(f"[red]INVALID[/red] {result.source}")
    for issue in result.issues:
        style = "yellow" if issue.severity == "warning" else "red"
        console.print(f"  [{style}]{issue.severity}[/{style}] {issue.location}: {issue.message}")


def render_fuzz_report(console: Console, report: "FuzzReport") -> None:
    """Render per-node fuzzing outcomes, heaviest (highest fan-out) nodes first."""
    table = Table(title=f"Topology Fuzz — {report.n} trials (seed {report.seed})")
    table.add_column("Node")
    table.add_column("Type")
    table.add_column("Weight", justify="right")
    table.add_column("Trials", justify="right")
    table.add_column("Failures", justify="right")
    table.add_column("Not reached", justify="right")
    for node in report.nodes:
        failures = f"[red]{node.failures}[/red]" if node.failures else "0"
        table.add_row(
            node.node,
            node.node_type,
            f"{node.weight:g}",
            str(node.trials),
            failures,
            str(node.not_reached),
        )
    console.print(table)
    if report.failing_nodes:
        console.print(f"[red]Failing nodes:[/red] {', '.join(report.failing_nodes)}")
    else:
        console.print("[green]Every reached trial recovered.[/green]")
