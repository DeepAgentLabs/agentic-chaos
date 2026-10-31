"""The 0-100 resilience score, computed from a finished `ChaosReport`.

The score is a weighted mean of five components. Each one is computed only
when the report (and, for latency and cost, a baseline report) can show it; a
component that cannot be computed is left out and the remaining weights are
renormalized. With no computable component the score is ``None`` and the
status is ``inconclusive`` -- never a made-up number.

- ``recovery`` -- did the application survive each injected fault? An errored
  fault counts as recovered when a later call to the same step succeeded
  (``retried``) or the step was not called again and nothing escaped
  (``fallback``); it is unrecovered when every later call to that step failed,
  and ``escaped`` when the run's unhandled error came from it. Delays and loops
  count as ``tolerated`` unless they escaped. Degraded output counts with its
  fidelity score when a v0.3 judge scored it, and is otherwise ``unverified``
  and left out: silent degradation cannot be called recovered without a judge.
- ``probes`` -- weighted pass rate of ``during`` and ``post`` probe results.
  ``during`` results count half as much as ``post`` ones: probes are allowed to
  struggle while faults are active, but must pass once chaos stopped. A failed
  ``pre`` probe makes the whole score inconclusive (no steady state to recover to).
- ``latency`` -- wall-clock slowdown against a baseline report: no slowdown
  scores 1, and ``latency_tolerance`` (default 2.0, i.e. three times slower)
  or worse scores 0.
- ``retry_efficiency`` -- injected failures per retry: one retry per failure
  (or fewer) scores 1, a retry storm scores lower. Runs that never retried
  (fallbacks, or failures that escaped) leave it out.
- ``cost`` -- cost overhead against a baseline with a recorded cost: no
  overhead scores 1, ``cost_tolerance`` (default 1.0, double the cost) or more
  scores 0.

A run in which no fault fired is not scored either: there was nothing to be
resilient to. The score reads the report only, so it can be recomputed from
saved JSON.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from agentic_chaos.contracts.analysis import find_retries, injected_failures, ordered_calls
from agentic_chaos.models.report import ChaosReport, ReportLike, load_report

ScoreStatus = Literal["scored", "inconclusive"]
EventVerdict = Literal[
    "retried", "fallback", "tolerated", "judged", "unrecovered", "escaped", "unverified"
]

RESILIENCE_VERSION = "1.0"
DEFAULT_WEIGHTS: dict[str, float] = {
    "recovery": 0.35,
    "probes": 0.25,
    "latency": 0.15,
    "retry_efficiency": 0.15,
    "cost": 0.10,
}
_DURING_WEIGHT = 0.5
_GRADES = ((90, "A"), (75, "B"), (60, "C"), (40, "D"), (0, "F"))
_RECOVERED = {"retried", "fallback", "tolerated"}


@dataclass(frozen=True)
class Component:
    """One input to the score: a 0-1 value (None when not computable) and its weight."""

    name: str
    score: float | None
    weight: float
    detail: str
    observed: dict[str, Any] = field(default_factory=dict)

    def as_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": None if self.score is None else round(self.score, 4),
            "weight": self.weight,
            "detail": self.detail,
            "observed": self.observed,
        }


@dataclass(frozen=True)
class FaultScore:
    """Per-fault-type breakdown: how many injections were recovered."""

    fault_type: str
    events: int
    score: int | None
    verdicts: dict[str, int]
    note: str

    def as_json(self) -> dict[str, Any]:
        return {
            "fault_type": self.fault_type,
            "events": self.events,
            "score": self.score,
            "verdicts": self.verdicts,
            "note": self.note,
        }


@dataclass
class ResilienceScore:
    """A computed resilience score with its components and per-fault breakdown."""

    score: int | None
    status: ScoreStatus
    report_id: str
    report_name: str
    components: list[Component]
    faults: list[FaultScore]
    reasons: list[str] = field(default_factory=list)
    baseline_report_id: str | None = None
    trend: dict[str, Any] | None = None

    @property
    def grade(self) -> str | None:
        if self.score is None:
            return None
        return next(letter for floor, letter in _GRADES if self.score >= floor)

    def component(self, name: str) -> Component:
        for component in self.components:
            if component.name == name:
                return component
        raise KeyError(name)

    def meets(self, min_score: float) -> bool:
        """True only when the score was computed and is at least `min_score`."""
        return self.score is not None and self.score >= min_score

    def summary(self) -> str:
        if self.score is None:
            reason = "; ".join(self.reasons) or "no component could be computed"
            return f"resilience score for '{self.report_name}': inconclusive ({reason})"
        line = f"resilience score for '{self.report_name}': {self.score}/100 ({self.grade})"
        if self.trend and self.trend.get("delta") is not None:
            line += f", {self.trend['delta']:+d} from last run"
        return line

    def as_json(self) -> dict[str, Any]:
        return {
            "version": RESILIENCE_VERSION,
            "score": self.score,
            "status": self.status,
            "grade": self.grade,
            "report_id": self.report_id,
            "report_name": self.report_name,
            "baseline_report_id": self.baseline_report_id,
            "components": [component.as_json() for component in self.components],
            "faults": [fault.as_json() for fault in self.faults],
            "reasons": list(self.reasons),
            "trend": self.trend,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "ResilienceScore":
        return cls(
            score=data.get("score"),
            status=data.get("status", "inconclusive"),
            report_id=str(data.get("report_id", "")),
            report_name=str(data.get("report_name", "")),
            components=[
                Component(
                    name=item["name"],
                    score=item.get("score"),
                    weight=float(item.get("weight", 0.0)),
                    detail=str(item.get("detail", "")),
                    observed=dict(item.get("observed") or {}),
                )
                for item in data.get("components", [])
            ],
            faults=[
                FaultScore(
                    fault_type=item["fault_type"],
                    events=int(item.get("events", 0)),
                    score=item.get("score"),
                    verdicts=dict(item.get("verdicts") or {}),
                    note=str(item.get("note", "")),
                )
                for item in data.get("faults", [])
            ],
            reasons=list(data.get("reasons") or []),
            baseline_report_id=data.get("baseline_report_id"),
            trend=data.get("trend"),
        )


def validate_weights(weights: Mapping[str, float] | None) -> dict[str, float]:
    """Merge `weights` over the defaults; unknown names or invalid values raise."""
    merged = dict(DEFAULT_WEIGHTS)
    for name, value in (weights or {}).items():
        if name not in DEFAULT_WEIGHTS:
            known = ", ".join(DEFAULT_WEIGHTS)
            raise ValueError(f"unknown resilience component '{name}' (known: {known})")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"weight for '{name}' must be a finite number >= 0")
        merged[name] = float(value)
    if not any(merged.values()):
        raise ValueError("at least one resilience weight must be greater than 0")
    return merged


def compute_resilience(
    report: ReportLike,
    *,
    baseline: ReportLike | None = None,
    weights: Mapping[str, float] | None = None,
    latency_tolerance: float = 2.0,
    cost_tolerance: float = 1.0,
) -> ResilienceScore:
    """Score `report` from 0 to 100 (see the module docstring for the method)."""
    for name, tolerance in (
        ("latency_tolerance", latency_tolerance),
        ("cost_tolerance", cost_tolerance),
    ):
        if isinstance(tolerance, bool) or not math.isfinite(tolerance) or tolerance <= 0:
            raise ValueError(f"{name} must be a finite number > 0")
    resolved = validate_weights(weights)
    chaos_report = load_report(report)
    baseline_report = load_report(baseline) if baseline is not None else None
    reasons: list[str] = []

    verdicts = event_verdicts(chaos_report)
    components = [
        _recovery(verdicts, resolved["recovery"]),
        _probes(chaos_report, resolved["probes"]),
        _latency(chaos_report, baseline_report, resolved["latency"], latency_tolerance),
        _retry_efficiency(chaos_report, resolved["retry_efficiency"]),
        _cost(chaos_report, baseline_report, resolved["cost"], cost_tolerance),
    ]

    failed_pre = [
        r for r in chaos_report.probes if r.get("phase") == "pre" and r.get("status") != "passed"
    ]
    if chaos_report.dry_run:
        reasons.append("dry run: no fault was injected")
    if failed_pre:
        names = ", ".join(sorted({str(r.get("probe")) for r in failed_pre}))
        reasons.append(f"pre-chaos probes failed ({names}): no steady state to recover to")
    fired = bool(chaos_report.chaos_events)
    if not chaos_report.dry_run and not failed_pre and not fired:
        reason = "no fault fired, so there was nothing to be resilient to"
        if chaos_report.unhandled_error:
            reason += f"; the run raised {chaos_report.unhandled_error.get('type')} first"
        reasons.append(reason)
    if chaos_report.aborted:
        reasons.append("the circuit breaker aborted the run; the score covers what ran")

    scored = [c for c in components if c.score is not None and c.weight > 0]
    score: int | None = None
    if fired and not chaos_report.dry_run and not failed_pre and scored:
        total = sum(c.weight for c in scored)
        score = int(round(100 * math.fsum(c.weight * (c.score or 0.0) for c in scored) / total))
    elif not scored and not reasons:
        reasons.append("no component could be computed: add probes or a fidelity judge")

    return ResilienceScore(
        score=score,
        status="scored" if score is not None else "inconclusive",
        report_id=chaos_report.id,
        report_name=chaos_report.name,
        components=components,
        faults=_fault_scores(verdicts),
        reasons=reasons,
        baseline_report_id=baseline_report.id if baseline_report is not None else None,
    )


def event_verdicts(report: ChaosReport) -> list[tuple[dict[str, Any], EventVerdict, float | None]]:
    """(event, verdict, 0-1 score or None) for every injected fault event."""
    calls = ordered_calls(report)
    by_event = {c.get("event_id"): c for c in calls if c.get("event_id")}
    escaped = _escaped_event_id(report)
    results: list[tuple[dict[str, Any], EventVerdict, float | None]] = []
    for event in report.chaos_events:
        outcome = event.get("outcome")
        verdict: EventVerdict
        value: float | None
        if event.get("id") is not None and event.get("id") == escaped:
            verdict, value = "escaped", 0.0
        elif outcome == "degraded":
            fidelity = event.get("fidelity_score")
            if isinstance(fidelity, (int, float)) and not isinstance(fidelity, bool):
                verdict, value = "judged", min(1.0, max(0.0, float(fidelity)))
            else:
                verdict, value = "unverified", None
        elif outcome == "errored":
            verdict = _after_failure(by_event.get(event.get("id")), calls)
            value = 1.0 if verdict in _RECOVERED else 0.0
        else:
            verdict, value = "tolerated", 1.0
        results.append((event, verdict, value))
    return results


def _escaped_event_id(report: ChaosReport) -> str | None:
    """The fault event the run's unhandled error came from, if there was one.

    When the error does not carry an event (the app wrapped or replaced it),
    it is attributed to the last fault injected before the run ended.
    """
    error = report.unhandled_error
    if not error:
        return None
    event_id = error.get("event_id")
    if isinstance(event_id, str) and event_id:
        return event_id
    fault_type = error.get("fault_type")
    candidates = [
        e
        for e in report.chaos_events
        if e.get("outcome") != "degraded"
        and (fault_type is None or e.get("fault_type") == fault_type)
    ]
    last = candidates[-1].get("id") if candidates else None
    return last if isinstance(last, str) else None


def _step(call: Mapping[str, Any]) -> tuple[Any, Any, str] | None:
    """A call's step as the contracts define it, ``(kind, name)``, scoped to its
    workflow stage so stages never recover each other."""
    name = call.get("step_name") or call.get("step_id")
    if not isinstance(name, str) or not name:
        return None
    kind = call.get("kind")
    return (call.get("workflow_step"), kind if isinstance(kind, str) else "call", name)


def _after_failure(call: dict[str, Any] | None, calls: list[dict[str, Any]]) -> EventVerdict:
    step = _step(call) if call is not None else None
    if call is None or step is None:
        return "fallback"
    sequence = call.get("sequence", 0)
    later = [c for c in calls if c.get("sequence", 0) > sequence and _step(c) == step]
    if not later:
        return "fallback"
    return "retried" if any(c.get("status") == "ok" for c in later) else "unrecovered"


def _recovery(
    verdicts: list[tuple[dict[str, Any], EventVerdict, float | None]], weight: float
) -> Component:
    values = [value for _, _, value in verdicts if value is not None]
    counts = _count(verdict for _, verdict, _ in verdicts)
    if not values:
        detail = (
            "only unverified degradations: attach a fidelity judge"
            if verdicts
            else "no fault was injected"
        )
        return Component("recovery", None, weight, detail, counts)
    value = math.fsum(values) / len(values)
    recovered = sum(counts.get(v, 0) for v in _RECOVERED)
    return Component(
        "recovery",
        value,
        weight,
        f"{recovered}/{len(verdicts)} injections recovered",
        counts,
    )


def _probes(report: ChaosReport, weight: float) -> Component:
    scored = [r for r in report.probes if r.get("phase") in ("during", "post")]
    if not scored:
        return Component("probes", None, weight, "no during/post probe ran")
    total = passed = 0.0
    for result in scored:
        share = float(result.get("weight", 1.0)) * (
            _DURING_WEIGHT if result.get("phase") == "during" else 1.0
        )
        total += share
        if result.get("status") == "passed":
            passed += share
    count = sum(1 for r in scored if r.get("status") == "passed")
    return Component(
        "probes",
        passed / total if total else None,
        weight,
        f"{count}/{len(scored)} during/post probe checks passed",
        {"passed": count, "checks": len(scored)},
    )


def _duration(report: ChaosReport) -> float | None:
    if report.end_time is None:
        return None
    return (report.end_time - report.start_time).total_seconds()


def _latency(
    report: ChaosReport, baseline: ChaosReport | None, weight: float, tolerance: float
) -> Component:
    if baseline is None:
        return Component("latency", None, weight, "no baseline report")
    chaos, base = _duration(report), _duration(baseline)
    if chaos is None or base is None or base <= 0:
        return Component("latency", None, weight, "baseline has no usable duration")
    slowdown = max(0.0, chaos / base - 1.0)
    return Component(
        "latency",
        max(0.0, 1.0 - slowdown / tolerance),
        weight,
        f"{chaos / base:.2f}x the baseline duration",
        {"duration_s": chaos, "baseline_duration_s": base},
    )


def _retry_efficiency(report: ChaosReport, weight: float) -> Component:
    failures = len(injected_failures(report))
    if failures == 0:
        return Component("retry_efficiency", None, weight, "no injected failure to retry")
    if not report.calls:
        return Component("retry_efficiency", None, weight, "no call log")
    if report.calls_dropped:
        return Component("retry_efficiency", None, weight, "call log was truncated")
    retries = len(find_retries(report))
    if retries == 0:
        return Component(
            "retry_efficiency", None, weight, "no retry observed", {"failures": failures}
        )
    value = 1.0 if retries <= failures else failures / retries
    return Component(
        "retry_efficiency",
        value,
        weight,
        f"{retries} retr{'y' if retries == 1 else 'ies'} for {failures} injected failure(s)",
        {"retries": retries, "failures": failures},
    )


def _cost(
    report: ChaosReport, baseline: ChaosReport | None, weight: float, tolerance: float
) -> Component:
    if baseline is None or baseline.cost_usd <= 0:
        return Component("cost", None, weight, "no baseline with a recorded cost")
    overhead = max(0.0, report.cost_usd / baseline.cost_usd - 1.0)
    return Component(
        "cost",
        max(0.0, 1.0 - overhead / tolerance),
        weight,
        f"{overhead:+.0%} cost overhead",
        {"cost_usd": report.cost_usd, "baseline_cost_usd": baseline.cost_usd},
    )


def _count(items: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts


def _fault_scores(
    verdicts: list[tuple[dict[str, Any], EventVerdict, float | None]],
) -> list[FaultScore]:
    grouped: dict[str, list[tuple[EventVerdict, float | None]]] = {}
    for event, verdict, value in verdicts:
        grouped.setdefault(str(event.get("fault_type", "unknown")), []).append((verdict, value))
    scores: list[FaultScore] = []
    for fault_type, items in grouped.items():
        values = [value for _, value in items if value is not None]
        counts = _count(verdict for verdict, _ in items)
        note = ", ".join(f"{n} {verdict}" for verdict, n in sorted(counts.items()))
        if "unverified" in counts:
            note += " (attach a fidelity judge)"
        scores.append(
            FaultScore(
                fault_type=fault_type,
                events=len(items),
                score=int(round(100 * math.fsum(values) / len(values))) if values else None,
                verdicts=counts,
                note=note,
            )
        )
    return scores
