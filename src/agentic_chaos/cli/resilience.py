"""CLI helpers for v0.9 probes and resilience scores, shared by the run commands."""

from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.markup import escape

from agentic_chaos.cli.render import render_probe_results, render_resilience
from agentic_chaos.models.report import ChaosReport
from agentic_chaos.probes import FunctionProbe, HttpProbe, Probe, check_probes
from agentic_chaos.resilience import ResilienceHistory, ResilienceScore, compute_resilience
from agentic_chaos.workflows.targets import resolve_target

PROBE_HELP = (
    "Steady-state probe run before and after the chaos (repeatable). An http(s) URL "
    "must answer 200; 'file.py:function' or 'package.module:function' must return "
    "without raising."
)
MIN_SCORE_HELP = "Exit 1 unless the resilience score is at least this (0-100)."
HISTORY_HELP = "Record the score in this run-history file and show the trend."
MAX_RUNS_HELP = "History retention: keep the newest N runs per name."
MAX_AGE_HELP = "History retention: drop runs older than this many days."


def parse_probe(spec: str, base_dir: Path | None = None) -> Probe:
    """Build a probe from a CLI spec: a URL, or a target spec naming a function."""
    text = spec.strip()
    if text.startswith(("http://", "https://")):
        return HttpProbe(text)
    if "://" in text:
        raise ValueError(f"probe URL {text!r} must use http:// or https://")
    fn = resolve_target(text, base_dir)
    return FunctionProbe(fn, name=text)


def parse_probes(specs: list[str] | None) -> list[Probe]:
    return check_probes([parse_probe(spec) for spec in specs or []])


def check_min_score(min_score: float | None) -> None:
    if min_score is not None and not 0 <= min_score <= 100:
        raise ValueError("--min-score must be between 0 and 100")


def history_store(
    path: Path | None, max_runs: int | None, max_age_days: float | None
) -> ResilienceHistory | None:
    if path is None:
        if max_runs is not None or max_age_days is not None:
            raise ValueError("--history-max-runs/--history-max-age-days need --history")
        return None
    return ResilienceHistory(path, max_runs=max_runs, max_age_days=max_age_days)


def score_report(
    console: Console,
    report: ChaosReport,
    *,
    baseline: Any = None,
    history: ResilienceHistory | None = None,
    weights: dict[str, float] | None = None,
    record: bool = True,
) -> ResilienceScore:
    """Score `report`, record it in `history`, store it on the report and render it."""
    score = compute_resilience(report, baseline=baseline, weights=weights)
    if history is not None and record:
        history.record(score)
    report.resilience = score.as_json()
    render_probe_results(console, report.probes)
    render_resilience(console, score)
    if history is not None and record and score.trend is None:
        console.print("  Trend: first recorded run")
    return score


def gate(
    console: Console, score: ResilienceScore | dict[str, Any] | None, min_score: float | None
) -> None:
    """Exit 1 when `min_score` is set and the score is missing or below it."""
    if min_score is None:
        return
    if isinstance(score, dict):
        score = ResilienceScore.from_json(score)
    if score is None or not score.meets(min_score):
        shown = "inconclusive" if score is None or score.score is None else str(score.score)
        console.print(
            f"[red]Resilience score {escape(shown)} is below --min-score {min_score:g}[/red]"
        )
        raise typer.Exit(code=1)
    console.print(f"[green]Resilience score {score.score} meets --min-score {min_score:g}[/green]")
