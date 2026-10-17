"""The seven built-in chaos contracts."""

import math
from collections.abc import Iterable
from typing import Any, Literal

from agentic_chaos.contracts.analysis import (
    find_retries,
    injected_failures,
    max_retries_by_step,
    ordered_calls,
    unnamed_call_count,
    visited_nodes,
)
from agentic_chaos.contracts.base import Contract, ContractResult
from agentic_chaos.models.report import ChaosReport

CostMetric = Literal["cost_usd", "calls"]

_TRUNCATED = "the call log was truncated ({dropped} records dropped); retries cannot be counted"
_PRE_V06 = "the report has no {field} field (written before agentic-chaos 0.6)"


def _missing(report: ChaosReport, field: str) -> bool:
    """True when `field` was never recorded, only defaulted on load.

    Reports written before 0.6 have no call log or unhandled_error; an empty
    default there is absence of evidence, not evidence of a clean run.
    """
    return field not in report.model_fields_set


def _positive(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return float(value)


def _count(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


class CompletesWithin(Contract):
    """The run finished within `timeout_s` seconds (report start to end time)."""

    name = "completes_within"

    def __init__(self, timeout_s: float) -> None:
        self.timeout_s = _positive("timeout_s", timeout_s)

    def parameters(self) -> dict[str, Any]:
        return {"timeout_s": self.timeout_s}

    def check(self, report: ChaosReport, *, baseline: ChaosReport | None = None) -> ContractResult:
        if report.end_time is None:
            return self.result("inconclusive", "the report has no end_time; the run never ended")
        elapsed = (report.end_time - report.start_time).total_seconds()
        if elapsed <= self.timeout_s:
            return self.result(
                "passed",
                f"finished in {elapsed:.3f}s (budget {self.timeout_s:g}s)",
                elapsed_s=elapsed,
            )
        return self.result(
            "failed",
            f"took {elapsed:.3f}s, over the {self.timeout_s:g}s budget",
            elapsed_s=elapsed,
        )


class NoUnhandledError(Contract):
    """No exception escaped the code under test."""

    name = "no_unhandled_error"

    def check(self, report: ChaosReport, *, baseline: ChaosReport | None = None) -> ContractResult:
        if _missing(report, "unhandled_error"):
            return self.result("inconclusive", _PRE_V06.format(field="unhandled_error"))
        error = report.unhandled_error
        if error is None:
            return self.result("passed", "no exception escaped the code under test")
        detail = f"{error.get('type', 'Exception')}: {error.get('message', '')}".rstrip(": ")
        if error.get("fault_type"):
            detail += f" (injected by {error['fault_type']})"
        return self.result("failed", f"unhandled {detail}", unhandled_error=error)


class MaxRetries(Contract):
    """No step was retried more than `n` times in a row after failing.

    Pass `step` to check a single step name; otherwise every named step counts.
    """

    name = "max_retries"

    def __init__(self, n: int, *, step: str | None = None) -> None:
        self.n = _count("n", n)
        self.step = step

    def parameters(self) -> dict[str, Any]:
        params: dict[str, Any] = {"n": self.n}
        if self.step is not None:
            params["step"] = self.step
        return params

    def check(self, report: ChaosReport, *, baseline: ChaosReport | None = None) -> ContractResult:
        if _missing(report, "calls"):
            return self.result("inconclusive", _PRE_V06.format(field="calls"))
        if report.calls_dropped:
            return self.result("inconclusive", _TRUNCATED.format(dropped=report.calls_dropped))
        by_step = max_retries_by_step(report)
        if self.step is not None:
            by_step = {self.step: by_step.get(self.step, 0)}
        worst_step, worst = max(by_step.items(), key=lambda item: item[1], default=(None, 0))
        observed = {
            "max_retries": worst,
            "step": worst_step,
            "retries_by_step": by_step,
            "unnamed_calls": unnamed_call_count(report),
        }
        if worst <= self.n:
            return self.result(
                "passed", f"at most {worst} consecutive retries (limit {self.n})", **observed
            )
        return self.result(
            "failed",
            f"step '{worst_step}' was retried {worst} times in a row (limit {self.n})",
            **observed,
        )


class RecoveredAfterFailure(Contract):
    """The run completed despite at least one injected failure.

    "Recovered" means an ``errored`` fault event was recorded, no exception
    escaped, and the session was not aborted. With
    ``require_step_success=True`` every step hit by an injected failure must
    also have a later successful call (recovery by retry, not only fallback).
    A run in which no failure was injected is inconclusive, not a pass.
    """

    name = "recovered_after_failure"

    def __init__(self, *, require_step_success: bool = False) -> None:
        self.require_step_success = require_step_success

    def parameters(self) -> dict[str, Any]:
        return {"require_step_success": self.require_step_success}

    def check(self, report: ChaosReport, *, baseline: ChaosReport | None = None) -> ContractResult:
        failures = injected_failures(report)
        observed: dict[str, Any] = {"injected_failures": len(failures)}
        if not failures:
            return self.result(
                "inconclusive",
                "no injected failure was observed, so recovery was not demonstrated",
                **observed,
            )
        if report.unhandled_error is not None:
            kind = report.unhandled_error.get("type", "an exception")
            return self.result(
                "failed",
                f"{kind} escaped after {len(failures)} injected failure(s)",
                **observed,
                unhandled_error=report.unhandled_error,
            )
        if report.aborted:
            return self.result(
                "failed",
                "the session was aborted by its circuit breaker",
                **observed,
                abort_reason=report.abort_reason,
            )
        if _missing(report, "unhandled_error"):
            return self.result("inconclusive", _PRE_V06.format(field="unhandled_error"), **observed)
        if self.require_step_success:
            if _missing(report, "calls"):
                return self.result("inconclusive", _PRE_V06.format(field="calls"), **observed)
            unrecovered = _unrecovered_steps(report)
            observed["unrecovered_steps"] = unrecovered
            if report.calls_dropped and unrecovered:
                return self.result(
                    "inconclusive", _TRUNCATED.format(dropped=report.calls_dropped), **observed
                )
            if unrecovered:
                names = ", ".join(unrecovered)
                return self.result(
                    "failed",
                    f"no successful call after the injected failure on: {names}",
                    **observed,
                )
        return self.result(
            "passed", f"completed despite {len(failures)} injected failure(s)", **observed
        )


def _unrecovered_steps(report: ChaosReport) -> list[str]:
    pending: dict[str, bool] = {}
    for call in ordered_calls(report):
        name = call.get("step_name") or call.get("step_id")
        if not isinstance(name, str) or not name:
            continue
        if call.get("status") == "error" and call.get("fault_type"):
            pending[name] = True
        elif call.get("status") == "ok":
            pending.pop(name, None)
    return sorted(pending)


class MaxCostImpact(Contract):
    """Cost under chaos stayed within `factor` times the baseline.

    `metric="cost_usd"` compares explicitly recorded cost
    (`session.record_cost()` / `record_usage()`); `metric="calls"` compares the
    number of instrumented calls, an offline proxy for LLM spend. The baseline
    comes from a baseline report or an explicit `baseline_value`.
    """

    name = "max_cost_impact"

    def __init__(
        self,
        factor: float,
        *,
        metric: CostMetric = "cost_usd",
        baseline_value: float | None = None,
    ) -> None:
        self.factor = _positive("factor", factor)
        if metric not in ("cost_usd", "calls"):
            raise ValueError("metric must be 'cost_usd' or 'calls'")
        self.metric: CostMetric = metric
        if baseline_value is not None and (
            isinstance(baseline_value, bool)
            or not isinstance(baseline_value, (int, float))
            or not math.isfinite(baseline_value)
            or baseline_value < 0
        ):
            raise ValueError("baseline_value must be finite and non-negative")
        self.baseline_value = baseline_value

    def parameters(self) -> dict[str, Any]:
        params: dict[str, Any] = {"factor": self.factor, "metric": self.metric}
        if self.baseline_value is not None:
            params["baseline_value"] = self.baseline_value
        return params

    def _measure(self, report: ChaosReport) -> float:
        if self.metric == "calls":
            return float(len(report.calls) + report.calls_dropped)
        return report.cost_usd

    def check(self, report: ChaosReport, *, baseline: ChaosReport | None = None) -> ContractResult:
        if self.metric == "calls":
            for label, candidate in (("report", report), ("baseline", baseline)):
                if candidate is not None and _missing(candidate, "calls"):
                    return self.result(
                        "inconclusive", f"{label}: " + _PRE_V06.format(field="calls")
                    )
        if self.baseline_value is not None:
            reference: float = self.baseline_value
        elif baseline is not None:
            reference = self._measure(baseline)
        else:
            return self.result(
                "inconclusive", "no baseline report or baseline_value to compare against"
            )
        observed_value = self._measure(report)
        observed = {"metric": self.metric, "baseline": reference, "chaos": observed_value}
        if reference == 0:
            if observed_value == 0:
                return self.result(
                    "inconclusive",
                    f"neither run recorded any {self.metric}; record cost or use metric='calls'",
                    **observed,
                )
            return self.result(
                "failed",
                f"baseline {self.metric} was 0 but chaos run used {observed_value:g}",
                **observed,
            )
        ratio = observed_value / reference
        observed["ratio"] = ratio
        if ratio <= self.factor:
            return self.result(
                "passed",
                f"{self.metric} was {ratio:.2f}x baseline (limit {self.factor:g}x)",
                **observed,
            )
        return self.result(
            "failed", f"{self.metric} was {ratio:.2f}x baseline, over {self.factor:g}x", **observed
        )


class NoRetryStorm(Contract):
    """At most `max_retries_per_window` retries, across all steps, in any window.

    Counts retries topology-wide, so a fault on one agent that sets off
    retries in its callers is caught even when each step stays under its own
    `MaxRetries` limit.
    """

    name = "no_retry_storm"

    def __init__(self, max_retries_per_window: int, *, window_seconds: float = 60.0) -> None:
        self.max_retries_per_window = _count("max_retries_per_window", max_retries_per_window)
        self.window_seconds = _positive("window_seconds", window_seconds)

    def parameters(self) -> dict[str, Any]:
        return {
            "max_retries_per_window": self.max_retries_per_window,
            "window_seconds": self.window_seconds,
        }

    def check(self, report: ChaosReport, *, baseline: ChaosReport | None = None) -> ContractResult:
        if _missing(report, "calls"):
            return self.result("inconclusive", _PRE_V06.format(field="calls"))
        if report.calls_dropped:
            return self.result("inconclusive", _TRUNCATED.format(dropped=report.calls_dropped))
        retries = find_retries(report)
        if any(retry.started_at is None for retry in retries):
            return self.result("inconclusive", "some retried calls have no start timestamp")
        timed = sorted(
            (retry.started_at, retry.step) for retry in retries if retry.started_at is not None
        )
        peak, peak_steps, start = 0, [], 0
        for end, (at, _) in enumerate(timed):
            while (at - timed[start][0]).total_seconds() > self.window_seconds:
                start += 1
            if end - start + 1 > peak:
                peak = end - start + 1
                peak_steps = sorted({step for _, step in timed[start : end + 1]})
        observed = {"total_retries": len(timed), "peak_in_window": peak, "steps": peak_steps}
        if peak <= self.max_retries_per_window:
            return self.result(
                "passed",
                f"peak of {peak} retries in a {self.window_seconds:g}s window "
                f"(limit {self.max_retries_per_window})",
                **observed,
            )
        return self.result(
            "failed",
            f"retry storm: {peak} retries within {self.window_seconds:g}s across "
            f"{', '.join(peak_steps)} (limit {self.max_retries_per_window})",
            **observed,
        )


class FullTopologyTraversal(Contract):
    """Every node the baseline run visited was also visited under chaos.

    Catches an agent silently short-circuiting a planned step (the reviewer
    never ran) rather than only checking that nothing errored. Pass
    `expected_nodes` to state the plan explicitly instead of using a baseline,
    and `ignore` for nodes allowed to be skipped.
    """

    name = "full_topology_traversal"

    def __init__(
        self,
        *,
        expected_nodes: Iterable[str] | None = None,
        ignore: Iterable[str] = (),
    ) -> None:
        self.expected_nodes = sorted(set(expected_nodes)) if expected_nodes is not None else None
        self.ignore = sorted(set(ignore))

    def parameters(self) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if self.expected_nodes is not None:
            params["expected_nodes"] = self.expected_nodes
        if self.ignore:
            params["ignore"] = self.ignore
        return params

    def check(self, report: ChaosReport, *, baseline: ChaosReport | None = None) -> ContractResult:
        if self.expected_nodes is not None:
            expected = set(self.expected_nodes)
        elif baseline is not None:
            expected = visited_nodes(baseline)
        else:
            return self.result(
                "inconclusive", "no baseline report or expected_nodes to compare against"
            )
        expected -= set(self.ignore)
        if not expected:
            return self.result("inconclusive", "no expected nodes to check")
        visited = visited_nodes(report)
        missing = sorted(expected - visited)
        observed = {"expected": sorted(expected), "visited": sorted(visited), "missing": missing}
        if not missing:
            return self.result(
                "passed", f"all {len(expected)} expected nodes were visited", **observed
            )
        if report.calls_dropped or _missing(report, "calls"):
            return self.result(
                "inconclusive",
                f"{', '.join(missing)} not seen, but the call log is truncated or absent",
                **observed,
            )
        return self.result(
            "failed", f"expected nodes never visited under chaos: {', '.join(missing)}", **observed
        )


BUILTIN_CONTRACTS: tuple[type[Contract], ...] = (
    CompletesWithin,
    NoUnhandledError,
    MaxRetries,
    RecoveredAfterFailure,
    MaxCostImpact,
    NoRetryStorm,
    FullTopologyTraversal,
)
