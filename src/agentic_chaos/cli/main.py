import runpy
from pathlib import Path

import typer
from agenticlens.exporters import JSONExporter
from agenticlens.profiler.context import completed_workflows
from rich.console import Console

from agentic_chaos.chaos.faults import FAULT_REGISTRY, resolve_faults
from agentic_chaos.chaos.session import chaos_session
from agentic_chaos.cli.render import render_chaos_events

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
        help=(
            "Path to a Python script instrumented with agenticlens.profile()/step() "
            "and agentic_chaos.chaos_call()."
        ),
    ),
    inject: str = typer.Option(
        ...,
        "--inject",
        help="Comma-separated fault names to enable, e.g. 'token_timeout,rate_limit_storm'.",
    ),
    save: Path | None = typer.Option(
        None, "--save", help="Save the resulting workflow (with chaos_events) to this file."
    ),
) -> None:
    """Run a script with the requested faults active, then report what happened."""
    if not script.exists():
        console.print(f"[red]Script not found:[/red] {script}")
        raise typer.Exit(code=1)

    try:
        resolve_faults(inject)  # validate fault names up front for a clean error message
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    before = len(completed_workflows)
    with chaos_session(inject) as session:
        runpy.run_path(str(script), run_name="__main__")

    new_workflows = completed_workflows[before:]
    if not new_workflows:
        console.print(
            "[yellow]No workflow was profiled.[/yellow] "
            "Did the script call `agenticlens.profile()`?"
        )
        raise typer.Exit(code=1)

    workflow = new_workflows[-1]
    session.apply_to(workflow)
    render_chaos_events(console, workflow)

    if save is not None:
        JSONExporter().export(workflow, save)
        console.print(f"\nSaved workflow (with chaos_events) to {save}")
        console.print(f"Next: [bold]agenticlens analyze {save}[/bold]")


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
