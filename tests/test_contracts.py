import json
from datetime import datetime, timedelta, timezone

import pytest

from agentic_chaos import (
    RateLimitStormFault,
    TokenTimeoutFault,
    TopologyTracker,
    chaos_call,
    chaos_session,
    wrap_node,
)
from agentic_chaos.chaos.faults import RateLimitStormError
from agentic_chaos.contracts import (
    CompletesWithin,
    ContractViolationError,
    FullTopologyTraversal,
    MaxCostImpact,
    MaxRetries,
    NoRetryStorm,
    NoUnhandledError,
    RecoveredAfterFailure,
    assert_contracts,
    check_contracts,
    load_report,
)
from agentic_chaos.models import ChaosReport

T0 = datetime(2026, 10, 17, tzinfo=timezone.utc)


def retrying_agent(attempts: int = 5) -> str:
    for _ in range(attempts):
        try:
            return chaos_call(lambda: "sunny", step_name="llm")
        except RateLimitStormError:
            continue
    raise RuntimeError("gave up")


def run(faults, fn, *, dry_run=False):
    error = None
    with chaos_session(faults, dry_run=dry_run) as session:
        try:
            fn()
        except Exception as exc:
            error = exc
    return session.to_report("agent", error=error)


def call(seq, step, status="ok", *, at=0.0, fault=None, kind="call"):
    return {
        "sequence": seq,
        "kind": kind,
        "step_id": None,
        "step_name": step,
        "started_at": (T0 + timedelta(seconds=at)).isoformat(),
        "duration_s": 0.0,
        "status": status,
        "error_type": "Boom" if status == "error" else None,
        "fault_type": fault,
        "event_id": None,
    }


def synthetic(calls=(), **fields):
    return ChaosReport(name="synthetic", start_time=T0, end_time=T0, calls=list(calls), **fields)


# -- CompletesWithin ---------------------------------------------------------


def test_completes_within_passes_and_fails_on_elapsed_time():
    report = ChaosReport(name="r", start_time=T0, end_time=T0 + timedelta(seconds=2))
    assert CompletesWithin(5).check(report).status == "passed"
    failed = CompletesWithin(1).check(report)
    assert failed.status == "failed"
    assert failed.observed["elapsed_s"] == 2.0


def test_completes_within_without_end_time_is_inconclusive():
    report = ChaosReport(name="r", start_time=T0)
    assert CompletesWithin(1).check(report).status == "inconclusive"


@pytest.mark.parametrize("value", [0, -1, float("inf"), True])
def test_completes_within_rejects_invalid_budget(value):
    with pytest.raises(ValueError):
        CompletesWithin(value)


# -- NoUnhandledError --------------------------------------------------------


def test_no_unhandled_error_reports_escaped_fault():
    report = run([TokenTimeoutFault(hang_seconds=0)], lambda: chaos_call(lambda: 1))
    result = NoUnhandledError().check(report)
    assert result.status == "failed"
    assert "TokenTimeoutError" in result.message
    assert "injected by token_timeout" in result.message


def test_no_unhandled_error_passes_when_handled():
    report = run([RateLimitStormFault(burst_count=2)], retrying_agent)
    assert NoUnhandledError().check(report).passed


# -- MaxRetries --------------------------------------------------------------


def test_max_retries_counts_consecutive_retries_per_step():
    report = run([RateLimitStormFault(burst_count=3)], retrying_agent)
    assert MaxRetries(3).check(report).passed
    result = MaxRetries(2).check(report)
    assert result.status == "failed"
    assert result.observed["step"] == "llm"
    assert result.observed["max_retries"] == 3


def test_success_resets_streak_and_other_steps_are_independent():
    calls = [
        call(1, "a", "error"),
        call(2, "a"),
        call(3, "a", "error"),
        call(4, "b", "error"),
        call(5, "a"),
        call(6, "b"),
    ]
    result = MaxRetries(1).check(synthetic(calls))
    assert result.passed
    assert result.observed["retries_by_step"] == {"a": 1, "b": 1}


def test_unnamed_calls_are_never_retries():
    calls = [call(1, None, "error"), call(2, None, "error"), call(3, None)]
    result = MaxRetries(0).check(synthetic(calls))
    assert result.passed
    assert result.observed["unnamed_calls"] == 3


def test_max_retries_single_step_filter():
    calls = [call(1, "a", "error"), call(2, "a", "error"), call(3, "a"), call(4, "b")]
    assert MaxRetries(0, step="b").check(synthetic(calls)).passed
    assert not MaxRetries(0, step="a").check(synthetic(calls)).passed


def test_max_retries_inconclusive_when_log_truncated():
    assert MaxRetries(1).check(synthetic(calls_dropped=1)).status == "inconclusive"


# -- RecoveredAfterFailure ---------------------------------------------------


def test_recovered_after_failure_passes_after_retry():
    report = run([RateLimitStormFault(burst_count=2)], retrying_agent)
    result = RecoveredAfterFailure(require_step_success=True).check(report)
    assert result.passed
    assert result.observed["injected_failures"] == 2


def test_not_recovered_when_error_escapes():
    report = run([RateLimitStormFault(burst_count=9)], lambda: retrying_agent(attempts=2))
    result = RecoveredAfterFailure().check(report)
    assert result.status == "failed"
    assert result.observed["unhandled_error"]["type"] == "RuntimeError"


def test_recovery_without_injected_failure_is_inconclusive():
    report = run([RateLimitStormFault(burst_count=0)], retrying_agent)
    assert RecoveredAfterFailure().check(report).status == "inconclusive"


def test_fallback_recovery_passes_unless_step_success_is_required():
    def fallback_agent():
        try:
            chaos_call(lambda: "x", step_name="primary")
        except RateLimitStormError:
            return "cached answer"

    report = run([RateLimitStormFault(burst_count=1)], fallback_agent)
    assert RecoveredAfterFailure().check(report).passed
    strict = RecoveredAfterFailure(require_step_success=True).check(report)
    assert strict.status == "failed"
    assert strict.observed["unrecovered_steps"] == ["primary"]


def test_aborted_session_did_not_recover():
    report = synthetic(
        chaos_events=[{"fault_type": "rate_limit_storm", "outcome": "errored"}],
        aborted=True,
        abort_reason={"threshold": "max_injections"},
    )
    result = RecoveredAfterFailure().check(report)
    assert result.status == "failed"
    assert "aborted" in result.message


# -- MaxCostImpact -----------------------------------------------------------


def test_max_cost_impact_on_call_counts_against_baseline_run():
    baseline = run([RateLimitStormFault(burst_count=3)], retrying_agent, dry_run=True)
    chaos = run([RateLimitStormFault(burst_count=3)], retrying_agent)
    assert len(baseline.calls) == 1
    assert len(chaos.calls) == 4
    assert MaxCostImpact(4, metric="calls").check(chaos, baseline=baseline).passed
    failed = MaxCostImpact(2, metric="calls").check(chaos, baseline=baseline)
    assert failed.status == "failed"
    assert failed.observed["ratio"] == 4.0


def test_max_cost_impact_on_recorded_cost():
    report = synthetic(cost_usd=0.3)
    assert MaxCostImpact(2, baseline_value=0.2).check(report).passed
    assert not MaxCostImpact(1.2, baseline_value=0.2).check(report).passed


def test_max_cost_impact_zero_cases():
    assert MaxCostImpact(2, baseline_value=0).check(synthetic()).status == "inconclusive"
    assert MaxCostImpact(2, baseline_value=0).check(synthetic(cost_usd=1)).status == "failed"
    assert MaxCostImpact(2).check(synthetic()).status == "inconclusive"  # no baseline


def test_max_cost_impact_counts_dropped_calls():
    report = synthetic([call(1, "a")], calls_dropped=5)
    result = MaxCostImpact(10, metric="calls", baseline_value=1).check(report)
    assert result.observed["chaos"] == 6


@pytest.mark.parametrize(
    "kwargs",
    [{"factor": 0}, {"factor": 2, "metric": "tokens"}, {"factor": 2, "baseline_value": -1}],
)
def test_max_cost_impact_validation(kwargs):
    with pytest.raises(ValueError):
        MaxCostImpact(**kwargs)


# -- NoRetryStorm ------------------------------------------------------------


def test_retry_storm_is_counted_across_steps():
    calls = [
        call(1, "planner", "error", at=0),
        call(2, "planner", at=1),
        call(3, "search", "error", at=1.5),
        call(4, "search", "error", at=2),
        call(5, "search", at=2.5),
        call(6, "writer", "error", at=3),
        call(7, "writer", at=3.5),
    ]
    report = synthetic(calls)
    # Each step stays within MaxRetries(2) ...
    assert MaxRetries(2).check(report).passed
    # ... but four retries land within four seconds, topology-wide.
    storm = NoRetryStorm(3, window_seconds=5).check(report)
    assert storm.status == "failed"
    assert storm.observed["peak_in_window"] == 4
    assert storm.observed["steps"] == ["planner", "search", "writer"]
    assert NoRetryStorm(4, window_seconds=5).check(report).passed
    assert NoRetryStorm(2, window_seconds=1).check(report).passed


def test_retry_storm_inconclusive_cases():
    assert NoRetryStorm(1).check(synthetic(calls_dropped=2)).status == "inconclusive"
    calls = [call(1, "a", "error"), {**call(2, "a"), "started_at": None}]
    assert NoRetryStorm(1).check(synthetic(calls)).status == "inconclusive"


def test_retry_storm_with_real_session():
    report = run([RateLimitStormFault(burst_count=3)], retrying_agent)
    assert NoRetryStorm(3).check(report).passed
    assert not NoRetryStorm(2).check(report).passed


# -- FullTopologyTraversal ---------------------------------------------------


def pipeline(skip_reviewer: bool):
    tracker = TopologyTracker(auto_activate=False)
    planner = wrap_node(lambda q: q, node_name="Planner", tracker=tracker, caller_node="Router")
    reviewer = wrap_node(lambda q: q, node_name="Reviewer", tracker=tracker, caller_node="Planner")
    tracker.register_node("Reviewer")  # registration alone is not a visit

    with chaos_session([]) as session:
        draft = planner("q")
        if not skip_reviewer:
            reviewer(draft)
    return session.to_report("pipeline", agent_topology=tracker.topology.as_json())


def test_full_traversal_detects_skipped_node_against_baseline():
    baseline = pipeline(skip_reviewer=False)
    assert FullTopologyTraversal().check(pipeline(False), baseline=baseline).passed
    result = FullTopologyTraversal().check(pipeline(True), baseline=baseline)
    assert result.status == "failed"
    assert result.observed["missing"] == ["Reviewer"]
    assert (
        FullTopologyTraversal(ignore=["Reviewer"]).check(pipeline(True), baseline=baseline).passed
    )


def test_full_traversal_with_explicit_expected_nodes():
    report = pipeline(skip_reviewer=True)
    assert FullTopologyTraversal(expected_nodes=["Router", "Planner"]).check(report).passed
    assert not FullTopologyTraversal(expected_nodes=["Reviewer"]).check(report).passed


def test_full_traversal_inconclusive_cases():
    report = synthetic()
    assert FullTopologyTraversal().check(report).status == "inconclusive"
    assert FullTopologyTraversal(expected_nodes=[]).check(report).status == "inconclusive"
    truncated = synthetic(calls_dropped=1)
    result = FullTopologyTraversal(expected_nodes=["A"]).check(truncated)
    assert result.status == "inconclusive"


def test_full_traversal_tolerates_malformed_topology():
    report = synthetic(agent_topology={"nodes": [None, {"id": 1}], "edges": [None, {}]})
    assert not FullTopologyTraversal(expected_nodes=["A"]).check(report).passed


# -- check_contracts / reports ----------------------------------------------


def test_check_contracts_aggregates_and_serializes(tmp_path):
    report = run([RateLimitStormFault(burst_count=2)], retrying_agent)
    path = tmp_path / "report.json"
    path.write_text(report.model_dump_json())
    contract_report = check_contracts(
        path, [NoUnhandledError(), MaxRetries(1), RecoveredAfterFailure()]
    )
    assert not contract_report.passed
    assert [r.contract for r in contract_report.failures] == ["max_retries"]
    data = json.loads(json.dumps(contract_report.as_json()))
    assert data["passed"] is False
    assert data["results"][1]["parameters"] == {"n": 1}
    assert "2/3 chaos contracts passed" in contract_report.summary()


def test_inconclusive_does_not_pass():
    contract_report = check_contracts(synthetic(), [RecoveredAfterFailure()])
    assert not contract_report.passed
    assert contract_report.failures[0].status == "inconclusive"


def test_assert_contracts_raises_assertion_error_with_summary():
    report = run([TokenTimeoutFault(hang_seconds=0)], lambda: chaos_call(lambda: 1))
    with pytest.raises(AssertionError, match="no_unhandled_error") as info:
        assert_contracts(report.model_dump(mode="json"), [NoUnhandledError()])
    assert isinstance(info.value, ContractViolationError)
    assert info.value.contract_report.failures[0].contract == "no_unhandled_error"


def test_assert_contracts_returns_report_when_all_pass():
    baseline = synthetic([call(1, "a")])
    result = assert_contracts(
        synthetic([call(1, "a")]), [MaxCostImpact(1, metric="calls")], baseline=baseline
    )
    assert result.baseline_report_id == baseline.id


def test_load_report_passthrough_and_repr():
    report = synthetic()
    assert load_report(report) is report
    assert repr(MaxRetries(2, step="x")) == "MaxRetries(n=2, step='x')"


# -- pre-v0.6 reports fail closed --------------------------------------------


def pre_v06_report(**fields):
    """JSON as agentic-chaos 0.5.x wrote it: no call log, no unhandled_error."""
    data = {
        "name": "old",
        "start_time": T0.isoformat(),
        "end_time": T0.isoformat(),
        "chaos_events": [{"fault_type": "rate_limit_storm", "outcome": "errored"}],
        **fields,
    }
    return load_report(data)


@pytest.mark.parametrize(
    "contract",
    [
        NoUnhandledError(),
        RecoveredAfterFailure(),
        RecoveredAfterFailure(require_step_success=True),
        MaxRetries(3),
        NoRetryStorm(3),
        MaxCostImpact(2, metric="calls", baseline_value=1),
        FullTopologyTraversal(expected_nodes=["llm"]),
    ],
    ids=repr,
)
def test_missing_v06_evidence_is_inconclusive(contract):
    result = contract.check(pre_v06_report())
    assert result.status == "inconclusive"
    assert "before agentic-chaos 0.6" in result.message or "absent" in result.message


def test_pre_v06_baseline_is_inconclusive_for_call_counts():
    chaos = synthetic([call(1, "a")])
    result = MaxCostImpact(2, metric="calls").check(chaos, baseline=pre_v06_report())
    assert result.status == "inconclusive"
    assert result.message.startswith("baseline:")


def test_pre_v06_reports_still_evaluate_what_they_do_record():
    report = pre_v06_report(unhandled_error={"type": "KeyError", "message": "x"})
    assert NoUnhandledError().check(report).status == "failed"
    assert MaxCostImpact(2, baseline_value=0.1).check(pre_v06_report(cost_usd=0.1)).passed
    assert CompletesWithin(1).check(report).passed


def test_explicit_null_unhandled_error_counts_as_evidence():
    report = load_report({"name": "new", "start_time": T0.isoformat(), "unhandled_error": None})
    assert NoUnhandledError().check(report).passed


@pytest.mark.parametrize("value", ["0.2", [1]])
def test_max_cost_impact_rejects_non_numeric_baseline(value):
    with pytest.raises(ValueError):
        MaxCostImpact(2, baseline_value=value)
