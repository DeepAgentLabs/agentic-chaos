from rich import box
from rich.console import Console
from rich.table import Table

from agentic_chaos.models.chaos_event import ChaosEvent

_OUTCOME_STYLES = {
    "errored": "red",
    "degraded": "red",
    "delayed": "yellow",
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
