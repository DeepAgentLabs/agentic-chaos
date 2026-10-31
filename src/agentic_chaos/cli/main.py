import json
import runpy
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pydantic
import typer
from rich.console import Console
from rich.markup import escape

import agentic_chaos.agents  # noqa: F401 -- ensures agent faults are registered
from agentic_chaos.agents.topology import get_active_tracker, reset_active_tracker
from agentic_chaos.chaos.faults import FAULT_REGISTRY, BaseFault, resolve_faults
from agentic_chaos.chaos.profiles import load_profile
from agentic_chaos.chaos.session import chaos_session
from agentic_chaos.cli.render import (
    render_chaos_events,
    render_contract_report,
    render_drift_report,
    render_fuzz_report,
    render_probe_results,
    render_resilience,
    render_topology,
    render_validation,
    render_workflow_report,
)
from agentic_chaos.cli.resilience import (
    HISTORY_HELP,
    MAX_AGE_HELP,
    MAX_RUNS_HELP,
    MIN_SCORE_HELP,
    PROBE_HELP,
    check_min_score,
    gate,
    history_store,
    parse_probes,
    score_report,
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
from agentic_chaos.probes import Probe, ProbeResult, run_probes
from agentic_chaos.resilience import ResilienceScore
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
experiment_app = typer.Typer(
    help="Declarative chaos experiments (YAML, JSON or TOML): validate, run and schedule.",
    no_args_is_help=True,
)
app.add_typer(experiment_app, name="experiment")
workflow_app = typer.Typer(
    help="Chaos workflows: multi-stage campaigns with health-check and approval gates.",
    no_args_is_help=True,
)
chaos_app.add_typer(workflow_app, name="workflow")
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
    probes: list[Probe] | None = None,
    probe_results: list[ProbeResult] | None = None,
) -> tuple[Any, datetime, BaseException | None]:
    """Run a script within a chaos_session and return (session, end, crash).

    Shared by `chaos run` and `agent run` to avoid code duplication. `during`
    probes run inside the session after the script, into `probe_results`.
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
        ended_at = datetime.now(timezone.utc)  # probe time is not part of the run
        if probes and probe_results is not None:
            probe_results.extend(run_probes(probes, "during"))
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
    session: Any,
    crashed: BaseException | None,
    contract_report: ContractReport | None,
    *,
    score: ResilienceScore | None = None,
    min_score: float | None = None,
) -> None:
    """Exit with the script's crash code, then abort, contract failure, low score."""
    if crashed is not None:
        raise typer.Exit(code=_exit_code(crashed))
    if session.safety.abort is not None:
        raise typer.Exit(code=1)
    if contract_report is not None and not contract_report.passed:
        raise typer.Exit(code=1)
    gate(console, score, min_score)


def _pre_probes(
    name: str,
    probes: list[Probe],
    *,
    save: Path | None,
    save_aios: Path | None,
) -> list[ProbeResult]:
    """Run pre-chaos probes; without steady state, save why and exit 1 before any chaos."""
    results = run_probes(probes, "pre")
    if all(result.passed for result in results):
        return results
    now = datetime.now(timezone.utc)
    report = ChaosReport(
        name=name, start_time=now, end_time=now, probes=[r.as_json() for r in results]
    )
    score_report(console, report, record=False)
    console.print(
        "[red]Pre-chaos probes failed: the system is not in steady state, "
        "so no fault was injected.[/red]"
    )
    unsteady = RuntimeError("pre-chaos probes failed")
    _save_reports(report, save=save, save_aios=save_aios, crashed=unsteady)
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
    probe: list[str] | None = typer.Option(None, "--probe", help=PROBE_HELP),
    min_score: float | None = typer.Option(None, "--min-score", help=MIN_SCORE_HELP),
    history: Path | None = typer.Option(None, "--history", help=HISTORY_HELP),
    history_max_runs: int | None = typer.Option(None, "--history-max-runs", help=MAX_RUNS_HELP),
    history_max_age_days: float | None = typer.Option(
        None, "--history-max-age-days", help=MAX_AGE_HELP
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
        probes = parse_probes(probe)
        check_min_score(min_score)
        store = history_store(history, history_max_runs, history_max_age_days)
    except (ValueError, OSError, ImportError, pydantic.ValidationError) as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(code=1) from exc

    probe_results = _pre_probes(script.stem, probes, save=save, save_aios=save_aios)
    session, ended_at, crashed = _run_script_with_chaos(
        script,
        configured,
        dry_run=dry_run,
        breaker=breaker,
        probes=probes,
        probe_results=probe_results,
    )
    probe_results.extend(run_probes(probes, "post"))

    if crashed is not None:
        console.print(f"[red]Script raised under chaos:[/red] {crashed!r}")

    render_chaos_events(console, session.events)
    if session.dry_run:
        console.print({"planned_events": session.planned_events})
    if session.safety.abort is not None:
        console.print({"abort_reason": session.safety.abort})

    report = session.to_report(script.stem, end_time=ended_at, error=crashed)
    report.probes = [result.as_json() for result in probe_results]
    score = score_report(console, report, baseline=baseline, history=store)
    _save_reports(report, save=save, save_aios=save_aios, crashed=crashed)
    contract_report = _check_contracts(
        report, contracts, baseline=baseline, save_contracts=save_contracts
    )
    _finish_run(session, crashed, contract_report, score=score, min_score=min_score)


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
    probe: list[str] | None = typer.Option(None, "--probe", help=PROBE_HELP),
    min_score: float | None = typer.Option(None, "--min-score", help=MIN_SCORE_HELP),
    history: Path | None = typer.Option(None, "--history", help=HISTORY_HELP),
    history_max_runs: int | None = typer.Option(None, "--history-max-runs", help=MAX_RUNS_HELP),
    history_max_age_days: float | None = typer.Option(
        None, "--history-max-age-days", help=MAX_AGE_HELP
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
        probes = parse_probes(probe)
        check_min_score(min_score)
        store = history_store(history, history_max_runs, history_max_age_days)
    except (ValueError, OSError, ImportError, pydantic.ValidationError) as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(code=1) from exc

    if framework not in ("generic", "langgraph", "crewai", "autogen"):
        console.print(f"[yellow]Unknown framework '{framework}', using generic.[/yellow]")

    probe_results = _pre_probes(script.stem, probes, save=save, save_aios=save_aios)
    session, ended_at, crashed = _run_script_with_chaos(
        script,
        configured,
        dry_run=dry_run,
        breaker=breaker,
        probes=probes,
        probe_results=probe_results,
    )
    probe_results.extend(run_probes(probes, "post"))

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
    report.probes = [result.as_json() for result in probe_results]
    score = score_report(console, report, baseline=baseline, history=store)
    _save_reports(report, save=save, save_aios=save_aios, crashed=crashed)
    contract_report = _check_contracts(
        report, contracts, baseline=baseline, save_contracts=save_contracts
    )
    _finish_run(session, crashed, contract_report, score=score, min_score=min_score)


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


@app.command("estimate")
def estimate(
    script: Path = typer.Argument(..., help="Scenario label/path; never imported or executed."),
    fault: str = typer.Option(..., "--fault", help="Registered fault name."),
    retries: int = typer.Option(3, "--retries", min=0),
    calls: int = typer.Option(1, "--calls", min=1),
    cost_per_call_usd: float = typer.Option(..., "--cost-per-call-usd", min=0),
) -> None:
    """Estimate retry cost as JSON from explicit inputs, without executing the target."""
    from agentic_chaos.chaos.estimate import estimate_failure

    try:
        result = estimate_failure(
            fault=fault, retries=retries, calls=calls, cost_per_call_usd=cost_per_call_usd
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps({"scenario": str(script), **result.as_json()}))


# ---------------------------------------------------------------------------
# experiment / chaos workflow subcommands (v0.8)
# ---------------------------------------------------------------------------

# Exit code for a workflow stopped at a Suspend gate awaiting approval.
EXIT_SUSPENDED = 3
_AIOS_STATUS = {"passed": "completed", "suspended": "running"}


def _validate_files(
    files: list[Path],
    *,
    check_targets: bool,
    strict: bool,
    json_output: bool,
    base_dir: Path | None,
) -> None:
    from agentic_chaos.experiments import validate_experiment

    results = [
        validate_experiment(path, base_dir=base_dir, check_targets=check_targets) for path in files
    ]
    if json_output:
        typer.echo(json.dumps([result.as_json() for result in results], indent=2))
    else:
        for result in results:
            render_validation(console, result)
    failed = [r for r in results if not r.ok or (strict and r.warnings)]
    if failed:
        raise typer.Exit(code=1)


def _interactive() -> bool:
    return sys.stdin.isatty()


def _approver(approve: list[str] | None, approve_all: bool, no_input: bool) -> Any:
    names = set(approve or [])
    if approve_all:
        return True
    if no_input or not _interactive():
        return names

    def ask(gate: Any, report: Any) -> bool | None:
        if gate.name in names:
            return True
        reason = f" ({gate.reason})" if gate.reason else ""
        return typer.confirm(f"Approve gate '{gate.name}'{reason}?", default=False)

    return ask


def _run_experiment_file(
    file: Path,
    *,
    save: Path | None,
    save_report: Path | None,
    save_aios: Path | None,
    dry_run: bool,
    approve: list[str] | None,
    approve_all: bool,
    resume_from: str | None,
    no_input: bool,
    check_targets: bool,
    base_dir: Path | None,
    min_score: float | None = None,
    baseline: Path | None = None,
    history: Any = None,
) -> None:
    from agentic_chaos.experiments import validate_experiment

    result = validate_experiment(file, base_dir=base_dir, check_targets=check_targets)
    if result.experiment is None:
        render_validation(console, result)
        raise typer.Exit(code=1)
    for warning in result.warnings:
        console.print(
            f"[yellow]warning[/yellow] {escape(str(warning.location))}: {escape(warning.message)}"
        )
    try:
        report = result.experiment.run(
            dry_run=True if dry_run else None,
            approve=_approver(approve, approve_all, no_input),
            resume_from=resume_from,
            baseline=baseline,
            history=history,
        )
    except ValueError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(code=1) from exc
    render_workflow_report(console, report)
    render_probe_results(console, report.probes)
    if report.resilience is not None:
        render_resilience(console, ResilienceScore.from_json(report.resilience))
        recorded = history is not None or result.experiment.history is not None
        if recorded and report.status != "suspended" and report.resilience.get("trend") is None:
            console.print("  Trend: first recorded run")
    if save is not None:
        report.save(save)
        console.print(f"\nSaved workflow report to {save}")
    merged = report.to_chaos_report() if save_report or save_aios else None
    if save_report is not None and merged is not None:
        save_report.write_text(merged.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"Saved merged chaos report to {save_report}")
    if save_aios is not None and merged is not None:
        status = _AIOS_STATUS.get(report.status, "failed")
        save_aios.write_text(json.dumps(to_aios_run(merged, status=status), indent=2), "utf-8")
        console.print(f"Saved AIOS v0.4-draft run artifact to {save_aios}")
    if report.status == "suspended":
        raise typer.Exit(code=EXIT_SUSPENDED)
    if report.status != "passed":
        raise typer.Exit(code=1)
    gate(
        console,
        report.resilience,
        min_score if min_score is not None else result.experiment.min_score,
    )


_FILES_HELP = "Experiment files (.yaml, .yml, .json or .toml)."
_NO_TARGET_CHECK_HELP = "Skip checking that targets exist and define the named function."
_BASE_DIR_HELP = "Resolve relative targets here instead of the experiment file's directory."


@experiment_app.command("validate")
def experiment_validate(
    files: list[Path] = typer.Argument(..., help=_FILES_HELP),
    no_target_check: bool = typer.Option(False, "--no-target-check", help=_NO_TARGET_CHECK_HELP),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as failures."),
    json_output: bool = typer.Option(False, "--json", help="Print results as JSON."),
    base_dir: Path | None = typer.Option(None, "--base-dir", help=_BASE_DIR_HELP),
) -> None:
    """Lint experiments without running them; exits 1 when any file is invalid.

    Checks schema shape, unknown fault/assertion names (with suggestions),
    out-of-range parameters, scopes, cron schedules, templates and that each
    target exists and defines its function. Targets are parsed, never executed,
    so this is safe as a pre-commit hook or CI step.
    """
    _validate_files(
        files,
        check_targets=not no_target_check,
        strict=strict,
        json_output=json_output,
        base_dir=base_dir,
    )


def _run_command(
    file: Path = typer.Argument(..., help="Experiment or workflow file."),
    save: Path | None = typer.Option(None, "--save", help="Save the workflow report JSON."),
    save_report: Path | None = typer.Option(
        None, "--save-report", help="Save every step merged into one native chaos report."
    ),
    save_aios: Path | None = typer.Option(
        None, "--save-aios", help="Save the merged run as an AIOS v0.4-draft Run artifact."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview faults; targets and health checks still execute."
    ),
    approve: list[str] | None = typer.Option(
        None, "--approve", help="Approve this Suspend gate (repeatable)."
    ),
    approve_all: bool = typer.Option(False, "--approve-all", help="Approve every gate."),
    resume_from: str | None = typer.Option(
        None, "--resume-from", help="Skip to just after this approved Suspend gate."
    ),
    no_input: bool = typer.Option(
        False, "--no-input", help="Never prompt; unapproved gates suspend the run."
    ),
    no_target_check: bool = typer.Option(False, "--no-target-check", help=_NO_TARGET_CHECK_HELP),
    base_dir: Path | None = typer.Option(None, "--base-dir", help=_BASE_DIR_HELP),
    min_score: float | None = typer.Option(
        None, "--min-score", help=MIN_SCORE_HELP + " Overrides resilience.min_score."
    ),
    baseline: Path | None = typer.Option(
        None, "--baseline", help="Fault-free report for the score's latency and cost parts."
    ),
    history: Path | None = typer.Option(
        None, "--history", help=HISTORY_HELP + " Overrides resilience.history."
    ),
    history_max_runs: int | None = typer.Option(None, "--history-max-runs", help=MAX_RUNS_HELP),
    history_max_age_days: float | None = typer.Option(
        None, "--history-max-age-days", help=MAX_AGE_HELP
    ),
) -> None:
    """Validate, then run an experiment or workflow and report every stage.

    Exits 0 when the workflow passed, 3 when it stopped at an unapproved
    Suspend gate (re-run with --resume-from), and 1 otherwise -- including
    when the resilience score is below --min-score (or resilience.min_score).
    """
    try:
        check_min_score(min_score)
        store = history_store(history, history_max_runs, history_max_age_days)
        if baseline is not None:
            load_report(baseline)
    except (ValueError, OSError, pydantic.ValidationError) as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(code=1) from exc
    _run_experiment_file(
        file,
        save=save,
        save_report=save_report,
        save_aios=save_aios,
        dry_run=dry_run,
        approve=approve,
        approve_all=approve_all,
        resume_from=resume_from,
        no_input=no_input,
        check_targets=not no_target_check,
        base_dir=base_dir,
        min_score=min_score,
        baseline=baseline,
        history=store,
    )


experiment_app.command("run")(_run_command)
workflow_app.command("run")(_run_command)


@workflow_app.command("validate")
def workflow_validate(
    files: list[Path] = typer.Argument(..., help=_FILES_HELP),
    no_target_check: bool = typer.Option(False, "--no-target-check", help=_NO_TARGET_CHECK_HELP),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as failures."),
    json_output: bool = typer.Option(False, "--json", help="Print results as JSON."),
    base_dir: Path | None = typer.Option(None, "--base-dir", help=_BASE_DIR_HELP),
) -> None:
    """Lint workflow files without running them (same as `experiment validate`)."""
    _validate_files(
        files,
        check_targets=not no_target_check,
        strict=strict,
        json_output=json_output,
        base_dir=base_dir,
    )


@experiment_app.command("schedule")
def experiment_schedule(
    file: Path = typer.Argument(..., help="Experiment file with a `schedule:` section."),
    output_format: str = typer.Option(
        "crontab", "--format", help="Snippet to print: crontab or github-actions."
    ),
    next_runs: int = typer.Option(5, "--next", min=1, help="How many upcoming runs to list."),
    command: str | None = typer.Option(
        None, "--command", help="Command the schedule runs (default: experiment run)."
    ),
) -> None:
    """Show upcoming runs and print a crontab or GitHub Actions schedule snippet.

    agentic-chaos embeds no scheduler: install the snippet in cron, a CI
    scheduler or a systemd timer so the experiment runs unattended.
    """
    from zoneinfo import ZoneInfo

    from agentic_chaos.experiments import load_experiment

    if output_format not in ("crontab", "github-actions"):
        raise typer.BadParameter("--format must be crontab or github-actions")
    try:
        experiment = load_experiment(file, check_targets=False)
    except ValueError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(code=1) from exc
    if experiment.schedule is None:
        console.print(f"[red]{escape(str(file))} has no schedule section[/red]")
        raise typer.Exit(code=1)
    cron = experiment.schedule.expression
    zone = experiment.timezone
    run = command or f"agentic-chaos experiment run {file} --no-input --save chaos-workflow.json"
    typer.echo(f"# {experiment.name}: '{cron}' ({zone})")
    for moment in experiment.schedule.next_runs(next_runs, tz=ZoneInfo(zone)):
        typer.echo(f"#   next: {moment.isoformat()}")
    if output_format == "crontab":
        if zone != "UTC":
            typer.echo(f"CRON_TZ={zone}")
        typer.echo(f"{cron} {run}")
        return
    if zone != "UTC":
        typer.echo(f"# note: GitHub Actions evaluates this cron in UTC, not {zone}")
    typer.echo(
        "on:\n"
        "  schedule:\n"
        f'    - cron: "{cron}"\n'
        "jobs:\n"
        "  chaos:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - run: pip install 'agentic-chaos[yaml]'\n"
        f"      - run: {run}"
    )


# ---------------------------------------------------------------------------
# agent fuzz (v0.8)
# ---------------------------------------------------------------------------


@agent_app.command("fuzz")
def agent_fuzz(
    script: Path = typer.Argument(..., help="Agent script to run once per trial (as __main__)."),
    trials: int = typer.Option(20, "--n", min=1, help="Number of single-fault trials."),
    seed: int = typer.Option(0, "--seed", help="Seed for reproducible placements."),
    step: list[str] | None = typer.Option(None, "--step", help="Only fuzz this node (repeatable)."),
    exclude_step: list[str] | None = typer.Option(
        None, "--exclude-step", help="Never fuzz this node (repeatable)."
    ),
    fault: list[str] | None = typer.Option(
        None, "--fault", help="Fault to place on every node type (repeatable)."
    ),
    save: Path | None = typer.Option(None, "--save", help="Save the fuzz report JSON."),
) -> None:
    """Fuzz the agent graph: place one fault per trial, weighted by node fan-out.

    A fault-free baseline run discovers the topology (from a TopologyTracker
    the script creates, else from the step names it calls). Exits 1 when any
    reached trial failed to recover.
    """
    from agentic_chaos.chaos.scope import Scope
    from agentic_chaos.workflows import fuzz_topology
    from agentic_chaos.workflows.targets import script_target

    if not script.exists():
        console.print(f"[red]Script not found:[/red] {script}")
        raise typer.Exit(code=1)
    try:
        scope = Scope(steps=step or None, exclude_steps=exclude_step or None)
        report = fuzz_topology(
            script_target(script), n=trials, seed=seed, scope=scope, faults=fault or None
        )
    except ValueError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(code=1) from exc
    render_fuzz_report(console, report)
    if save is not None:
        report.save(save)
        console.print(f"Saved fuzz report to {save}")
    if report.failing_nodes:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()


# ---------------------------------------------------------------------------
# score subcommands (v0.9)
# ---------------------------------------------------------------------------

score_app = typer.Typer(
    help="Resilience scores: recompute from saved reports, inspect and prune run history.",
    no_args_is_help=True,
)
app.add_typer(score_app, name="score")


def _load_scorable(path: Path) -> ChaosReport:
    """A native chaos report, merging the steps of a saved workflow report."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and data.get("kind") == "chaos_workflow":
        from agentic_chaos.workflows import WorkflowReport

        return WorkflowReport.model_validate(data).to_chaos_report()
    return ChaosReport.model_validate(data)


@score_app.command("show")
def score_show(
    report_file: Path = typer.Argument(..., help="Saved chaos, merged or workflow report JSON."),
    baseline: Path | None = typer.Option(
        None, "--baseline", help="Fault-free report for the latency and cost components."
    ),
    weight: list[str] | None = typer.Option(
        None, "--weight", help="Component weight override, e.g. 'recovery=0.5' (repeatable)."
    ),
    min_score: float | None = typer.Option(None, "--min-score", help=MIN_SCORE_HELP),
    history: Path | None = typer.Option(None, "--history", help=HISTORY_HELP),
    history_max_runs: int | None = typer.Option(None, "--history-max-runs", help=MAX_RUNS_HELP),
    history_max_age_days: float | None = typer.Option(
        None, "--history-max-age-days", help=MAX_AGE_HELP
    ),
    json_output: bool = typer.Option(False, "--json", help="Print the score as JSON."),
    save: Path | None = typer.Option(None, "--save", help="Save the score JSON to this file."),
) -> None:
    """Recompute the resilience score of a saved report, offline.

    Reads only the JSON, so it works on reports from CI artifacts. Exits 1 when
    --min-score is set and the score is inconclusive or lower.
    """
    from agentic_chaos.resilience import compute_resilience

    try:
        check_min_score(min_score)
        weights: dict[str, float] = {}
        for spec in weight or []:
            key, sep, value = spec.partition("=")
            if not sep:
                raise ValueError(f"--weight must look like 'name=value', got {spec!r}")
            weights[key.strip()] = float(value)
        store = history_store(history, history_max_runs, history_max_age_days)
        report = _load_scorable(report_file)
        reference = _load_scorable(baseline) if baseline is not None else None
        score = compute_resilience(report, baseline=reference, weights=weights or None)
        if store is not None:
            store.record(score)
    except (ValueError, OSError, pydantic.ValidationError) as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(code=1) from exc
    if save is not None:
        save.write_text(json.dumps(score.as_json(), indent=2), encoding="utf-8")
    if json_output:
        typer.echo(json.dumps(score.as_json(), indent=2))
    else:
        render_probe_results(console, report.probes)
        render_resilience(console, score)
        if save is not None:
            console.print(f"Saved resilience score to {save}")
    gate(console if not json_output else Console(stderr=True), score, min_score)


@score_app.command("history")
def score_history(
    history: Path = typer.Option(
        Path(".agentic-chaos/resilience-history.json"), "--history", help="Run-history file."
    ),
    name: str | None = typer.Option(None, "--name", help="Only runs with this name."),
    json_output: bool = typer.Option(False, "--json", help="Print entries as JSON."),
) -> None:
    """List recorded resilience scores, oldest first, with run-over-run deltas."""
    from rich.table import Table

    from agentic_chaos.resilience import ResilienceHistory

    try:
        entries = ResilienceHistory(history).entries(name)
    except ValueError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(code=1) from exc
    if json_output:
        typer.echo(json.dumps(entries, indent=2))
        return
    if not entries:
        console.print(f"No resilience history in {history}.")
        return
    table = Table(title=f"Resilience History — {history}")
    for column in ("Recorded", "Name", "Score", "Grade", "Δ"):
        table.add_column(column)
    last: dict[str, int] = {}
    for entry in entries:
        key, value = str(entry.get("name")), entry.get("score")
        delta = ""
        if isinstance(value, int) and key in last:
            delta = f"{value - last[key]:+d}"
        if isinstance(value, int):
            last[key] = value
        table.add_row(
            escape(str(entry.get("recorded_at", ""))[:19]),
            escape(key),
            "inconclusive" if value is None else str(value),
            str(entry.get("grade") or "-"),
            delta,
        )
    console.print(table)


@score_app.command("prune")
def score_prune(
    history: Path = typer.Option(
        Path(".agentic-chaos/resilience-history.json"), "--history", help="Run-history file."
    ),
    max_runs: int | None = typer.Option(None, "--max-runs", help=MAX_RUNS_HELP),
    max_age_days: float | None = typer.Option(None, "--max-age-days", help=MAX_AGE_HELP),
) -> None:
    """Apply retention to a run-history file now."""
    from agentic_chaos.resilience import ResilienceHistory

    try:
        if max_runs is None and max_age_days is None:
            raise ValueError("pass --max-runs and/or --max-age-days")
        removed = ResilienceHistory(history, max_runs=max_runs, max_age_days=max_age_days).prune()
    except ValueError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"Removed {removed} entr{'y' if removed == 1 else 'ies'} from {history}.")
