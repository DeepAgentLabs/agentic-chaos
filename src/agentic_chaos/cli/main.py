import runpy
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console

from agentic_chaos.chaos.faults import FAULT_REGISTRY, resolve_faults
from agentic_chaos.chaos.session import chaos_session
from agentic_chaos.cli.render import render_chaos_events
from agentic_chaos.models.report import ChaosReport

app = typer.Typer(
    name="agentic-chaos",
    help="Fault injection toolkit for LLM calls and agentic workflows.",
    no_args_is_help=True,
)
chaos_app = typer.Typer(
    help="LLM-level chaos: inject faults into individual LLM calls.",
    no_args_is_help=True,
)
agent_app = typer.Typer(
    help="Agent-orchestration chaos (LangGraph/CrewAI/AutoGen). Planned for v0.2.",
    no_args_is_help=True,
)
drift_app = typer.Typer(
    help="Prompt/model drift detection. Planned for v0.3.",
    no_args_is_help=True,
)
app.add_typer(chaos_app, name="chaos")
app.add_typer(agent_app, name="agent")
app.add_typer(drift_app, name="drift")
console = Console()


@chaos_app.command("run")
def chaos_run(
    script: Path = typer.Argument(
        ...,
        help="Path to a Python script that calls agentic_chaos.chaos_call(). No other "
        "library is required -- this works on any plain Python script.",
    ),
    inject: str = typer.Option(
        ...,
        "--inject",
        help="Comma-separated fault names to enable, e.g. 'token_timeout,rate_limit_storm'.",
    ),
    save: Path | None = typer.Option(
        None, "--save", help="Save the resulting chaos report to this file."
    ),
) -> None:
    """Run a script with the requested faults active, then report what happened.

    Saves this package's own standalone `ChaosReport` -- if you also have
    AgenticLens installed and want a merged workflow.json with cost/latency
    data too, use `agentic_chaos.integrations.agenticlens.attach_events()` in
    your own script instead of relying on this command's --save.
    """
    if not script.exists():
        console.print(f"[red]Script not found:[/red] {script}")
        raise typer.Exit(code=1)

    try:
        resolve_faults(inject)  # validate fault names up front for a clean error message
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    started_at = datetime.now(timezone.utc)
    crashed: Exception | None = None
    with chaos_session(inject) as session:
        try:
            runpy.run_path(str(script), run_name="__main__")
        except Exception as exc:  # the whole point is observing how the script fails
            crashed = exc
    ended_at = datetime.now(timezone.utc)

    if crashed is not None:
        console.print(f"[red]Script raised under chaos:[/red] {crashed!r}")

    render_chaos_events(console, session.events)

    if save is not None:
        report = ChaosReport(
            name=script.stem,
            start_time=started_at,
            end_time=ended_at,
            chaos_events=session.events_as_json(),
        )
        save.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"\nSaved chaos report to {save}")

    if crashed is not None:
        raise typer.Exit(code=1)


@chaos_app.command("list-faults")
def list_faults() -> None:
    """List the fault types available to --inject."""
    for name in sorted(FAULT_REGISTRY):
        console.print(f"- {name}")


@agent_app.command("run")
def agent_run() -> None:
    """Agent-orchestration fault injection. Not implemented yet."""
    console.print(
        "[yellow]agentic-chaos agent run[/yellow] is planned for v0.2 (LangGraph/CrewAI/"
        "AutoGen adapters). See ROADMAP.md."
    )
    raise typer.Exit(code=1)


@drift_app.command("snapshot")
def drift_snapshot() -> None:
    """Prompt/model drift snapshotting. Not implemented yet."""
    console.print(
        "[yellow]agentic-chaos drift snapshot[/yellow] is planned for v0.3. See ROADMAP.md."
    )
    raise typer.Exit(code=1)


@drift_app.command("compare")
def drift_compare() -> None:
    """Prompt/model drift comparison. Not implemented yet."""
    console.print(
        "[yellow]agentic-chaos drift compare[/yellow] is planned for v0.3. See ROADMAP.md."
    )
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
