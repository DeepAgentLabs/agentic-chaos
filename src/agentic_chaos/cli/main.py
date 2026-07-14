import runpy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

import agentic_chaos.agents  # noqa: F401 -- ensures agent faults are registered
from agentic_chaos.agents.topology import get_active_tracker, reset_active_tracker
from agentic_chaos.chaos.faults import FAULT_REGISTRY, resolve_faults
from agentic_chaos.chaos.session import chaos_session
from agentic_chaos.cli.render import render_chaos_events, render_topology
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
    help="Agent-orchestration chaos: inject faults at the multi-agent level.",
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


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _run_script_with_chaos(
    script: Path,
    inject: str,
    *,
    include_topology: bool = False,
) -> tuple[Any, datetime, datetime, Exception | None]:
    """Run a script within a chaos_session and return (session, start, end, crash).

    Shared by `chaos run` and `agent run` to avoid code duplication.
    """
    started_at = datetime.now(timezone.utc)
    crashed: Exception | None = None
    with chaos_session(inject) as session:
        try:
            runpy.run_path(str(script), run_name="__main__")
        except Exception as exc:
            crashed = exc
    ended_at = datetime.now(timezone.utc)
    return session, started_at, ended_at, crashed


# ---------------------------------------------------------------------------
# chaos subcommand
# ---------------------------------------------------------------------------


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
        resolve_faults(inject)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    session, started_at, ended_at, crashed = _run_script_with_chaos(script, inject)

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


# ---------------------------------------------------------------------------
# agent subcommand
# ---------------------------------------------------------------------------


@agent_app.command("run")
def agent_run(
    script: Path = typer.Argument(
        ...,
        help="Path to a Python script that uses agent-level chaos_call() wrappers "
        "(wrap_tool, wrap_node, or direct chaos_call with agent faults).",
    ),
    inject: str = typer.Option(
        ...,
        "--inject",
        help="Comma-separated fault names to enable, e.g. 'tool_failure,memory_corruption'.",
    ),
    framework: str = typer.Option(
        "generic",
        "--framework",
        help="Agent framework hint (generic, langgraph, crewai, autogen). Currently informational.",
    ),
    save: Path | None = typer.Option(
        None,
        "--save",
        help="Save the resulting chaos report to this file. If the script "
        "uses TopologyTracker, topology data is included automatically.",
    ),
) -> None:
    """Run an agent script with agent-level faults active, then report what happened.

    Supports all v0.1 LLM faults plus v0.2 agent faults: tool_failure,
    memory_corruption, infinite_loop. The script should use wrap_tool(),
    wrap_node(), or chaos_call() with the appropriate fault names.

    If the script creates a TopologyTracker, the recorded topology is rendered
    and included in the saved report automatically.
    """
    if not script.exists():
        console.print(f"[red]Script not found:[/red] {script}")
        raise typer.Exit(code=1)

    try:
        resolve_faults(inject)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if framework not in ("generic", "langgraph", "crewai", "autogen"):
        console.print(f"[yellow]Unknown framework '{framework}', using generic.[/yellow]")

    session, started_at, ended_at, crashed = _run_script_with_chaos(script, inject)

    if crashed is not None:
        console.print(f"[red]Script raised under chaos:[/red] {crashed!r}")

    render_chaos_events(console, session.events)

    # Pick up topology if the script registered a TopologyTracker.
    tracker = get_active_tracker()
    topology_data: dict[str, Any] | None = None
    if tracker is not None and tracker.topology.nodes:
        render_topology(console, tracker.topology)
        topology_data = tracker.topology.as_json()
    # Reset the active tracker to prevent leaking across sequential invocations.
    reset_active_tracker()

    if save is not None:
        report = ChaosReport(
            name=script.stem,
            start_time=started_at,
            end_time=ended_at,
            chaos_events=session.events_as_json(),
            agent_topology=topology_data,
        )
        save.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"\nSaved chaos report to {save}")

    if crashed is not None:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# drift subcommand (placeholder)
# ---------------------------------------------------------------------------


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
