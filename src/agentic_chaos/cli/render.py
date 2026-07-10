from agenticlens.models import Workflow
from rich import box
from rich.console import Console
from rich.table import Table

_OUTCOME_STYLES = {
    "errored": "red",
    "degraded": "red",
    "delayed": "yellow",
}


def render_chaos_events(console: Console, workflow: Workflow) -> None:
    """Render the `chaos_events` recorded on a workflow as a table."""
    events = workflow.chaos_events
    if not events:
        console.print("[green]No faults triggered.[/green]")
        return

    table = Table(title="Chaos Events", box=box.SIMPLE_HEAVY)
    table.add_column("Step")
    table.add_column("Fault")
    table.add_column("Outcome")
    table.add_column("Message")

    for event in events:
        outcome = str(event.get("outcome", "unknown"))
        style = _OUTCOME_STYLES.get(outcome, "white")
        table.add_row(
            str(event.get("step_name") or event.get("step_id") or "n/a"),
            str(event.get("fault_type", "unknown")),
            f"[{style}]{outcome}[/{style}]",
            str(event.get("message", "")),
        )

    console.print(table)
    console.print(
        f"\n[bold]{len(events)}[/bold] chaos event(s) recorded. "
        "Run `agenticlens analyze` on the saved file for a full impact report."
    )
