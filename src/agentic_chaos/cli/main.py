import json
import runpy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pydantic
import typer
from rich.console import Console

import agentic_chaos.agents  # noqa: F401 -- ensures agent faults are registered
from agentic_chaos.agents.topology import get_active_tracker, reset_active_tracker
from agentic_chaos.chaos.faults import FAULT_REGISTRY, BaseFault, resolve_faults
from agentic_chaos.chaos.profiles import load_profile
from agentic_chaos.chaos.session import chaos_session
from agentic_chaos.cli.render import (
    render_chaos_events,
    render_contract_report,
    render_drift_report,
    render_topology,
)
from agentic_chaos.contracts import (
    Contract,
    ContractReport,
    check_contracts,
    describe_contracts,
    load_report,
    parse_contract,
)
from agentic_chaos.drift import (
    DriftSnapshot,
    compare_snapshots,
    default_state_path,
    load_alert_state,
    load_retrieval_items,
    load_snapshot,
    save_alert_state,
    save_report,
    save_snapshot,
    should_emit_report,
    update_alert_state,
)
from agentic_chaos.export.aios import to_aios_run
from agentic_chaos.models.report import ChaosReport
from agentic_chaos.safety import CircuitBreaker

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
    help="Prompt/model drift detection via local snapshots and comparisons.",
    no_args_is_help=True,
)
app.add_typer(chaos_app, name="chaos")
app.add_typer(agent_app, name="agent")
contracts_app = typer.Typer(
    help="Chaos contracts: pass/fail resilience checks over a saved chaos report.",
    no_args_is_help=True,
)
app.add_typer(drift_app, name="drift")
app.add_typer(contracts_app, name="contracts")
console = Console()


def _read_optional_text(value: str | None, path: Path | None) -> str | None:
    if value is not None:
        return value
    if path is not None:
        return path.read_text(encoding="utf-8")
    return None


def _collect_retrieval_items(
    retrieval_items: list[str] | None,
    retrieval_file: Path | None,
) -> list[str]:
    if retrieval_items:
        return list(retrieval_items)
    if retrieval_file is not None:
        return load_retrieval_items(retrieval_file)
    return []


def _build_snapshot_from_inputs(
    *,
    name: str,
    prompt_text: str | None,
    prompt_file: Path | None,
    output_text: str | None,
    output_file: Path | None,
    retrieval_items: list[str] | None,
    retrieval_file: Path | None,
    model: str | None,
    model_fingerprint: str | None,
    embedding_model: str | None,
) -> DriftSnapshot:
    return DriftSnapshot.create(
        name=name,
        prompt_text=_read_optional_text(prompt_text, prompt_file),
        model_name=model,
        model_fingerprint=model_fingerprint,
        output_text=_read_optional_text(output_text, output_file),
        retrieval_items=_collect_retrieval_items(retrieval_items, retrieval_file),
        embedding_model=embedding_model,
    )


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _run_script_with_chaos(
    script: Path,
    inject: list[BaseFault],
    *,
    include_topology: bool = False,
    dry_run: bool = False,
    breaker: CircuitBreaker | None = None,
) -> tuple[Any, datetime, BaseException | None]:
    """Run a script within a chaos_session and return (session, end, crash).

    Shared by `chaos run` and `agent run` to avoid code duplication.
    """
    crashed: BaseException | None = None
    with chaos_session(inject, breaker=breaker, dry_run=dry_run) as session:
        try:
            runpy.run_path(str(script), run_name="__main__")
        except SystemExit as exc:
            # Capture a failing sys.exit() so reports are still saved; the command
            # re-raises it afterwards with the script's own exit code.
            if exc.code not in (None, 0):
                crashed = exc
        except Exception as exc:
            crashed = exc
    ended_at = datetime.now(timezone.utc)
    return session, ended_at, crashed


def _exit_code(crashed: BaseException) -> int:
    """Preserve a script's own non-zero sys.exit() code; other crashes exit 1."""
    if isinstance(crashed, SystemExit):
        return crashed.code if isinstance(crashed.code, int) else 1
    return 1


def _save_reports(
    report: ChaosReport,
    *,
    save: Path | None,
    save_aios: Path | None,
    crashed: BaseException | None,
) -> None:
    """Write the native report and/or its AIOS Run export, as requested."""
    if save is not None:
        save.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"\nSaved chaos report to {save}")
    if save_aios is not None:
        artifact = to_aios_run(report, status="failed" if crashed is not None else "completed")
        save_aios.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
        console.print(f"Saved AIOS v0.4-draft run artifact to {save_aios}")


_CONTRACT_HELP = (
    "Contract to check after the run, e.g. 'max_retries:3' or 'no_unhandled_error'. "
    "Repeatable; see `agentic-chaos contracts list`. Exits 1 unless all pass."
)
_BASELINE_HELP = "Baseline chaos report JSON for max_cost_impact / full_topology_traversal."


def _parse_contracts(specs: list[str] | None) -> list[Contract]:
    return [parse_contract(spec) for spec in specs or []]


def _check_contracts(
    report: ChaosReport,
    contracts: list[Contract],
    *,
    baseline: Path | None,
    save_contracts: Path | None,
) -> ContractReport | None:
    """Check, render and optionally save contract results; None when none requested."""
    if not contracts:
        return None
    contract_report = check_contracts(report, contracts, baseline=baseline)
    render_contract_report(console, contract_report)
    if save_contracts is not None:
        save_contracts.write_text(json.dumps(contract_report.as_json(), indent=2), encoding="utf-8")
        console.print(f"Saved contract results to {save_contracts}")
    return contract_report


def _finish_run(
    session: Any, crashed: BaseException | None, contract_report: ContractReport | None
) -> None:
    """Exit with the script's crash code, then abort, then contract failure."""
    if crashed is not None:
        raise typer.Exit(code=_exit_code(crashed))
    if session.safety.abort is not None:
        raise typer.Exit(code=1)
    if contract_report is not None and not contract_report.passed:
        raise typer.Exit(code=1)


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
    inject: str | None = typer.Option(
        None,
        "--inject",
        help="Comma-separated fault names to enable, e.g. 'token_timeout,rate_limit_storm'.",
    ),
    profile: str | None = typer.Option(None, "--profile", help="Named chaos.toml profile."),
    profile_file: Path = typer.Option(
        Path("chaos.toml"), "--profile-file", help="TOML profile file."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Record planned faults; target calls still execute."
    ),
    max_cost_usd: float | None = typer.Option(
        None, "--max-cost-usd", help="Abort at explicitly recorded cost budget."
    ),
    max_failure_rate: float | None = typer.Option(
        None, "--max-failure-rate", help="Abort above rolling failure rate."
    ),
    failure_window: int = typer.Option(
        20, "--failure-window", help="Completed operations in rolling window."
    ),
    min_calls: int = typer.Option(
        1, "--min-calls", help="Completions before checking failure rate."
    ),
    max_duration_seconds: float | None = typer.Option(
        None, "--max-duration-seconds", help="Cooperative elapsed-time limit."
    ),
    max_injections: int | None = typer.Option(
        None, "--max-injections", help="Maximum admitted fault injections."
    ),
    save: Path | None = typer.Option(
        None, "--save", help="Save the resulting chaos report to this file."
    ),
    save_aios: Path | None = typer.Option(
        None,
        "--save-aios",
        help="Also save the run as an AI Operations Specification v0.4-draft Run artifact.",
    ),
    contract: list[str] | None = typer.Option(None, "--contract", help=_CONTRACT_HELP),
    baseline: Path | None = typer.Option(None, "--baseline", help=_BASELINE_HELP),
    save_contracts: Path | None = typer.Option(
        None, "--save-contracts", help="Save contract results as JSON to this file."
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
        if (inject is None) == (profile is None):
            raise ValueError("Provide exactly one of --inject or --profile")
        configured = (
            load_profile(profile, profile_file)
            if profile is not None
            else resolve_faults(inject or "")
        )
        if not configured:
            raise ValueError("At least one fault is required")
        contracts = _parse_contracts(contract)
        if baseline is not None:
            load_report(baseline)  # fail before running the script on a bad baseline
        breaker = CircuitBreaker(
            max_cost_usd=max_cost_usd,
            max_failure_rate=max_failure_rate,
            window_size=failure_window,
            min_calls=min_calls,
            max_duration_seconds=max_duration_seconds,
            max_injections=max_injections,
        )
    except (ValueError, OSError, pydantic.ValidationError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    session, ended_at, crashed = _run_script_with_chaos(
        script, configured, dry_run=dry_run, breaker=breaker
    )

    if crashed is not None:
        console.print(f"[red]Script raised under chaos:[/red] {crashed!r}")

    render_chaos_events(console, session.events)
    if session.dry_run:
        console.print({"planned_events": session.planned_events})
    if session.safety.abort is not None:
        console.print({"abort_reason": session.safety.abort})

    report = session.to_report(script.stem, end_time=ended_at, error=crashed)
    _save_reports(report, save=save, save_aios=save_aios, crashed=crashed)
    contract_report = _check_contracts(
        report, contracts, baseline=baseline, save_contracts=save_contracts
    )
    _finish_run(session, crashed, contract_report)


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
    inject: str | None = typer.Option(
        None,
        "--inject",
        help="Comma-separated fault names to enable, e.g. 'tool_failure,memory_corruption'.",
    ),
    framework: str = typer.Option(
        "generic",
        "--framework",
        help="Agent framework hint (generic, langgraph, crewai, autogen). Currently informational.",
    ),
    profile: str | None = typer.Option(None, "--profile", help="Named chaos.toml profile."),
    profile_file: Path = typer.Option(
        Path("chaos.toml"), "--profile-file", help="TOML profile file."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Record planned faults; target calls still execute."
    ),
    max_cost_usd: float | None = typer.Option(
        None, "--max-cost-usd", help="Abort at explicitly recorded cost budget."
    ),
    max_failure_rate: float | None = typer.Option(
        None, "--max-failure-rate", help="Abort above rolling failure rate."
    ),
    failure_window: int = typer.Option(
        20, "--failure-window", help="Completed operations in rolling window."
    ),
    min_calls: int = typer.Option(
        1, "--min-calls", help="Completions before checking failure rate."
    ),
    max_duration_seconds: float | None = typer.Option(
        None, "--max-duration-seconds", help="Cooperative elapsed-time limit."
    ),
    max_injections: int | None = typer.Option(
        None, "--max-injections", help="Maximum admitted fault injections."
    ),
    save: Path | None = typer.Option(
        None,
        "--save",
        help="Save the resulting chaos report to this file. If the script "
        "uses TopologyTracker, topology data is included automatically.",
    ),
    save_aios: Path | None = typer.Option(
        None,
        "--save-aios",
        help="Also save the run as an AI Operations Specification v0.4-draft Run artifact.",
    ),
    contract: list[str] | None = typer.Option(None, "--contract", help=_CONTRACT_HELP),
    baseline: Path | None = typer.Option(None, "--baseline", help=_BASELINE_HELP),
    save_contracts: Path | None = typer.Option(
        None, "--save-contracts", help="Save contract results as JSON to this file."
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
        if (inject is None) == (profile is None):
            raise ValueError("Provide exactly one of --inject or --profile")
        configured = (
            load_profile(profile, profile_file)
            if profile is not None
            else resolve_faults(inject or "")
        )
        if not configured:
            raise ValueError("At least one fault is required")
        contracts = _parse_contracts(contract)
        if baseline is not None:
            load_report(baseline)  # fail before running the script on a bad baseline
        breaker = CircuitBreaker(
            max_cost_usd=max_cost_usd,
            max_failure_rate=max_failure_rate,
            window_size=failure_window,
            min_calls=min_calls,
            max_duration_seconds=max_duration_seconds,
            max_injections=max_injections,
        )
    except (ValueError, OSError, pydantic.ValidationError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if framework not in ("generic", "langgraph", "crewai", "autogen"):
        console.print(f"[yellow]Unknown framework '{framework}', using generic.[/yellow]")

    session, ended_at, crashed = _run_script_with_chaos(
        script, configured, dry_run=dry_run, breaker=breaker
    )

    if crashed is not None:
        console.print(f"[red]Script raised under chaos:[/red] {crashed!r}")

    render_chaos_events(console, session.events)
    if session.dry_run:
        console.print({"planned_events": session.planned_events})
    if session.safety.abort is not None:
        console.print({"abort_reason": session.safety.abort})

    # Pick up topology if the script registered a TopologyTracker.
    tracker = get_active_tracker()
    topology_data: dict[str, Any] | None = None
    if tracker is not None and tracker.topology.nodes:
        render_topology(console, tracker.topology)
        topology_data = tracker.topology.as_json()
    # Reset the active tracker to prevent leaking across sequential invocations.
    reset_active_tracker()

    report = session.to_report(
        script.stem, end_time=ended_at, error=crashed, agent_topology=topology_data
    )
    _save_reports(report, save=save, save_aios=save_aios, crashed=crashed)
    contract_report = _check_contracts(
        report, contracts, baseline=baseline, save_contracts=save_contracts
    )
    _finish_run(session, crashed, contract_report)


# ---------------------------------------------------------------------------
# drift subcommand
# ---------------------------------------------------------------------------


@drift_app.command("snapshot")
def drift_snapshot(
    name: str = typer.Option(..., "--name", help="Logical target name for this snapshot."),
    save: Path = typer.Option(..., "--save", help="Where to write the snapshot JSON."),
    prompt_text: str | None = typer.Option(
        None, "--prompt-text", help="Prompt text to snapshot directly."
    ),
    prompt_file: Path | None = typer.Option(
        None, "--prompt-file", help="Read prompt text from this file."
    ),
    output_text: str | None = typer.Option(
        None, "--output-text", help="Captured model output text."
    ),
    output_file: Path | None = typer.Option(
        None, "--output-file", help="Read captured output text from this file."
    ),
    retrieval_items: list[str] | None = typer.Option(
        None,
        "--retrieval-item",
        help="Retrieved item identifier/text. Repeat the flag for multiple items.",
    ),
    retrieval_file: Path | None = typer.Option(
        None,
        "--retrieval-file",
        help="File containing retrieval items as newline-delimited text or a JSON list.",
    ),
    model: str | None = typer.Option(None, "--model", help="Model name, e.g. gpt-5-mini."),
    model_fingerprint: str | None = typer.Option(
        None, "--model-fingerprint", help="Provider model/version fingerprint."
    ),
    embedding_model: str | None = typer.Option(
        None, "--embedding-model", help="Embedding or retrieval model identifier."
    ),
) -> None:
    """Capture a prompt/model/output/retrieval baseline snapshot."""
    snapshot = _build_snapshot_from_inputs(
        name=name,
        prompt_text=prompt_text,
        prompt_file=prompt_file,
        output_text=output_text,
        output_file=output_file,
        retrieval_items=retrieval_items,
        retrieval_file=retrieval_file,
        model=model,
        model_fingerprint=model_fingerprint,
        embedding_model=embedding_model,
    )
    save_snapshot(save, snapshot)
    console.print(f"Saved drift snapshot to {save}")


@drift_app.command("compare")
def drift_compare(
    baseline: Path = typer.Argument(..., help="Baseline snapshot JSON created by drift snapshot."),
    snapshot: Path | None = typer.Option(
        None,
        "--snapshot",
        help="Current snapshot JSON. If omitted, build one from the flags below.",
    ),
    name: str | None = typer.Option(
        None, "--name", help="Name for an inline current snapshot. Defaults to the baseline name."
    ),
    prompt_text: str | None = typer.Option(None, "--prompt-text"),
    prompt_file: Path | None = typer.Option(None, "--prompt-file"),
    output_text: str | None = typer.Option(None, "--output-text"),
    output_file: Path | None = typer.Option(None, "--output-file"),
    retrieval_items: list[str] | None = typer.Option(None, "--retrieval-item"),
    retrieval_file: Path | None = typer.Option(None, "--retrieval-file"),
    model: str | None = typer.Option(None, "--model"),
    model_fingerprint: str | None = typer.Option(None, "--model-fingerprint"),
    embedding_model: str | None = typer.Option(None, "--embedding-model"),
    save: Path | None = typer.Option(
        None, "--save", help="Write the drift report if emission rules allow it."
    ),
    state_path: Path | None = typer.Option(
        None, "--state-path", help="Cooldown state path. Defaults next to the baseline."
    ),
    cooldown_minutes: int = typer.Option(
        1440,
        "--cooldown-minutes",
        min=0,
        help="Minimum minutes between repeated emissions for the same unchanged drift fingerprint.",
    ),
    output_distance_threshold: float = typer.Option(
        0.18, "--output-distance-threshold", min=0.0, max=1.0
    ),
    retrieval_distance_threshold: float = typer.Option(
        0.4, "--retrieval-distance-threshold", min=0.0, max=1.0
    ),
    emit_only_on_change: bool = typer.Option(
        True,
        "--emit-only-on-change/--emit-always",
        help="Suppress repeated reports while the drift fingerprint is unchanged.",
    ),
) -> None:
    """Compare a current snapshot to a stored baseline, with cooldown-aware emission."""
    if not baseline.exists():
        console.print(f"[red]Baseline snapshot not found:[/red] {baseline}")
        raise typer.Exit(code=1)

    baseline_snapshot = load_snapshot(baseline)
    current_snapshot = (
        load_snapshot(snapshot)
        if snapshot is not None
        else _build_snapshot_from_inputs(
            name=name or baseline_snapshot.name,
            prompt_text=prompt_text,
            prompt_file=prompt_file,
            output_text=output_text,
            output_file=output_file,
            retrieval_items=retrieval_items,
            retrieval_file=retrieval_file,
            model=model,
            model_fingerprint=model_fingerprint,
            embedding_model=embedding_model,
        )
    )
    report = compare_snapshots(
        baseline_snapshot,
        current_snapshot,
        output_distance_threshold=output_distance_threshold,
        retrieval_distance_threshold=retrieval_distance_threshold,
    )
    render_drift_report(console, report)

    state_file = state_path or default_state_path(baseline)
    state = load_alert_state(state_file)
    should_emit = should_emit_report(
        report,
        state,
        cooldown_minutes=cooldown_minutes,
        emit_only_on_change=emit_only_on_change,
    )

    if should_emit:
        if save is not None:
            save_report(save, report)
            console.print(f"\nSaved drift report to {save}")
        save_alert_state(state_file, update_alert_state(report))
    else:
        console.print(
            f"\n[yellow]Suppressed unchanged drift report via cooldown state:[/yellow] {state_file}"
        )

    if report.has_drift:
        raise typer.Exit(code=2)



# ---------------------------------------------------------------------------
# contracts subcommand
# ---------------------------------------------------------------------------


@contracts_app.command("list")
def contracts_list() -> None:
    """List the built-in contracts and their spec parameters."""
    for entry in describe_contracts():
        params = ", ".join(entry["parameters"]) or "-"
        console.print(f"- [bold]{entry['name']}[/bold] ({entry['class']}): {entry['summary']}")
        console.print(f"    parameters: {params}")


@contracts_app.command("check")
def contracts_check(
    report: Path = typer.Argument(..., help="Chaos report JSON saved with --save."),
    contract: list[str] = typer.Option(..., "--contract", help=_CONTRACT_HELP),
    baseline: Path | None = typer.Option(None, "--baseline", help=_BASELINE_HELP),
    save: Path | None = typer.Option(
        None, "--save", help="Save contract results as JSON to this file."
    ),
) -> None:
    """Check contracts against a saved chaos report; exits 1 unless all pass."""
    try:
        contracts = _parse_contracts(contract)
        chaos_report = load_report(report)
        if baseline is not None:
            load_report(baseline)
    except (ValueError, OSError, pydantic.ValidationError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    contract_report = _check_contracts(
        chaos_report, contracts, baseline=baseline, save_contracts=save
    )
    if contract_report is not None and not contract_report.passed:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
