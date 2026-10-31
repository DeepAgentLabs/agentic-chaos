"""`chaos_run()`: one chaos run with the pre/during/post probe lifecycle and a score.

1. ``pre`` probes run with no chaos active. If any fails, the system was not
   in steady state, so (by default) no fault is injected and the score is
   inconclusive -- a failure afterwards could not be blamed on the chaos.
2. The target runs `repeat` times inside a fresh `chaos_session`.
3. ``during`` probes run inside that session after the target, faults active.
4. The session closes; ``post`` probes check the system returned to steady state.
5. The resilience score is computed from the report (and baseline), compared
   with the run history when one is given, and stored on the report.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_chaos.agents.topology import get_active_tracker, reset_active_tracker
from agentic_chaos.chaos.context import get_active_session
from agentic_chaos.chaos.faults import BaseFault
from agentic_chaos.chaos.session import chaos_session
from agentic_chaos.contracts.base import ReportLike
from agentic_chaos.models.report import ChaosReport
from agentic_chaos.probes.base import Phase, Probe, ProbeResult
from agentic_chaos.resilience.history import ResilienceHistory
from agentic_chaos.resilience.score import compute_resilience
from agentic_chaos.safety import CircuitBreaker


def run_probes(
    probes: Iterable[Probe], phase: Phase, *, step: str | None = None
) -> list[ProbeResult]:
    """Run every probe configured for `phase`, in order; never raises for a failing probe."""
    return [probe.run(phase, step=step) for probe in probes if probe.runs_in(phase)]


def check_probes(probes: Sequence[Any]) -> list[Probe]:
    probes = list(probes)
    for probe in probes:
        if not isinstance(probe, Probe):
            raise ValueError(f"probes must be Probe instances, got {type(probe).__name__}")
    names = [probe.name for probe in probes]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"duplicate probe name(s) {duplicates}; pass name= to tell them apart")
    return probes


def _history(
    history: ResilienceHistory | str | Path | None,
) -> ResilienceHistory | None:
    if history is None or isinstance(history, ResilienceHistory):
        return history
    return ResilienceHistory(history)


def chaos_run(
    target: Callable[[], Any],
    faults: "str | Sequence[str | BaseFault]",
    *,
    probes: Sequence[Probe] = (),
    name: str | None = None,
    repeat: int = 1,
    breaker: CircuitBreaker | None = None,
    dry_run: bool = False,
    baseline: ReportLike | None = None,
    weights: Mapping[str, float] | None = None,
    history: ResilienceHistory | str | Path | None = None,
    require_steady_state: bool = True,
) -> ChaosReport:
    """Run `target` under `faults` with probes, and return a scored `ChaosReport`.

    ```python
    report = chaos_run(my_app, [RateLimitStormFault(burst_count=3)], probes=[
        HttpProbe("http://localhost:8080/health"),
        ResponseQualityProbe(my_agent, "What is 2+2?", expect_contains="4"),
        LatencyProbe(my_agent, "Hello", max_ms=3000),
    ])
    assert report.resilience_score is not None and report.resilience_score >= 70
    ```

    Exceptions from the target are recorded (``unhandled_error``), not raised.
    `baseline` (a fault-free report) enables the latency and cost components;
    `history` (a path or `ResilienceHistory`) records the score and adds its
    trend. With ``require_steady_state=False`` chaos runs even after a failed
    pre-chaos probe (the score is then still inconclusive).
    """
    if get_active_session() is not None:
        raise RuntimeError("chaos_run() cannot run inside an active chaos_session()")
    if not callable(target):
        raise ValueError("target must be callable")
    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat < 1:
        raise ValueError("repeat must be a positive integer")
    configured = check_probes(probes)
    store = _history(history)
    run_name = name or getattr(target, "__name__", None) or "chaos-run"

    results = run_probes(configured, "pre")
    steady = all(result.passed for result in results)
    if not steady and require_steady_state:
        now = datetime.now(timezone.utc)
        report = ChaosReport(name=run_name, start_time=now, end_time=now, probes=[])
    else:
        crashed: BaseException | None = None
        reset_active_tracker()
        with chaos_session(faults, breaker=breaker, dry_run=dry_run) as session:
            for _ in range(repeat):
                try:
                    target()
                except Exception as exc:
                    crashed = exc
                    break
            results.extend(run_probes(configured, "during"))
        ended = datetime.now(timezone.utc)
        tracker = get_active_tracker()
        topology = tracker.topology.as_json() if tracker and tracker.topology.nodes else None
        reset_active_tracker()
        report = session.to_report(run_name, end_time=ended, error=crashed, agent_topology=topology)
        results.extend(run_probes(configured, "post"))

    report.probes = [result.as_json() for result in results]
    score = compute_resilience(report, baseline=baseline, weights=weights)
    if not steady and require_steady_state:
        score.reasons.append("chaos was not injected")
    if store is not None:
        store.record(score)
    report.resilience = score.as_json()
    return report
