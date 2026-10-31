"""v0.9 resilience score: verdicts, components, weights and recomputation from JSON."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from agentic_chaos import RateLimitStormFault, chaos_call, chaos_session
from agentic_chaos.chaos.faults import RateLimitStormError
from agentic_chaos.models import ChaosReport
from agentic_chaos.resilience import (
    DEFAULT_WEIGHTS,
    ResilienceScore,
    compute_resilience,
    event_verdicts,
    validate_weights,
)

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


def event(n: int, fault: str = "rate_limit_storm", outcome: str = "errored", **extra):
    return {"id": f"e{n}", "fault_type": fault, "outcome": outcome, "message": "", **extra}


def call(n: int, step: str, status: str = "ok", event_id: str | None = None, **extra):
    return {
        "sequence": n,
        "kind": "call",
        "step_name": step,
        "status": status,
        "event_id": event_id,
        **extra,
    }


def report(events=(), calls=(), seconds: float = 1.0, **fields) -> ChaosReport:
    return ChaosReport(
        name=fields.pop("name", "agent"),
        start_time=T0,
        end_time=T0 + timedelta(seconds=seconds),
        chaos_events=list(events),
        calls=list(calls),
        **fields,
    )


def verdicts(chaos_report: ChaosReport) -> list[str]:
    return [verdict for _, verdict, _ in event_verdicts(chaos_report)]


# -- verdicts -------------------------------------------------------------------


def test_retried_when_a_later_call_to_the_step_succeeds() -> None:
    r = report(
        [event(1), event(2)],
        [call(1, "llm", "error", "e1"), call(2, "llm", "error", "e2"), call(3, "llm")],
    )
    assert verdicts(r) == ["retried", "retried"]
    score = compute_resilience(r)
    assert score.component("recovery").score == 1.0
    assert score.faults[0].verdicts == {"retried": 2} and score.faults[0].score == 100


def test_unrecovered_when_every_later_call_failed() -> None:
    r = report([event(1)], [call(1, "llm", "error", "e1"), call(2, "llm", "error")])
    assert verdicts(r) == ["unrecovered"]


def test_fallback_when_the_step_is_never_called_again() -> None:
    r = report([event(1, "tool_failure")], [call(1, "retriever", "error", "e1"), call(2, "llm")])
    assert verdicts(r) == ["fallback"]


def test_escaped_by_event_id_or_attributed_to_the_last_fault() -> None:
    by_id = report(
        [event(1), event(2)],
        [call(1, "llm", "error", "e1"), call(2, "llm", "error", "e2")],
        unhandled_error={"type": "RateLimitStormError", "message": "", "event_id": "e2"},
    )
    assert verdicts(by_id) == ["unrecovered", "escaped"]
    wrapped = report(
        [event(1), event(2), event(3, "silent_degradation", "degraded")],
        [call(1, "llm", "error", "e1"), call(2, "llm", "error", "e2")],
        unhandled_error={"type": "RuntimeError", "message": "gave up"},
    )
    assert verdicts(wrapped) == ["unrecovered", "escaped", "unverified"]


def test_delays_and_loops_are_tolerated_unless_they_escape() -> None:
    r = report([event(1, "token_timeout", "delayed"), event(2, "infinite_loop", "looped")])
    assert verdicts(r) == ["tolerated", "tolerated"]
    crashed = report(
        [event(1, "token_timeout", "delayed")],
        unhandled_error={"type": "TimeoutError", "message": "", "fault_type": "token_timeout"},
    )
    assert verdicts(crashed) == ["escaped"]


def test_degradation_needs_a_judge() -> None:
    r = report(
        [
            event(1, "silent_degradation", "degraded"),
            event(2, "silent_degradation", "degraded", fidelity_score=0.4),
        ]
    )
    assert verdicts(r) == ["unverified", "judged"]
    score = compute_resilience(r)
    assert score.component("recovery").score == pytest.approx(0.4)
    assert score.faults[0].score == 40
    assert "attach a fidelity judge" in score.faults[0].note
    only_unverified = compute_resilience(report([event(1, "silent_degradation", "degraded")]))
    assert only_unverified.score is None
    assert "attach a fidelity judge" in only_unverified.component("recovery").detail


def test_workflow_stages_do_not_recover_each_other() -> None:
    r = report(
        [event(1)],
        [
            call(1, "llm", "error", "e1", workflow_step="warm-up"),
            call(2, "llm", workflow_step="escalate"),
        ],
    )
    assert verdicts(r) == ["fallback"]
    same_stage = report(
        [event(1)],
        [
            call(1, "llm", "error", "e1", workflow_step="warm-up"),
            call(2, "llm", workflow_step="warm-up"),
        ],
    )
    assert verdicts(same_stage) == ["retried"]


# -- components -----------------------------------------------------------------


def test_latency_against_a_baseline() -> None:
    chaos = report([event(1, "token_timeout", "delayed")], seconds=2.0)
    score = compute_resilience(chaos, baseline=report(seconds=1.0))
    latency = score.component("latency")
    assert latency.score == pytest.approx(0.5)  # 2x slower, tolerance 2.0
    assert latency.detail == "2.00x the baseline duration"
    strict = compute_resilience(chaos, baseline=report(seconds=1.0), latency_tolerance=1.0)
    assert strict.component("latency").score == 0.0
    faster = compute_resilience(report(seconds=0.5), baseline=report(seconds=1.0))
    assert faster.component("latency").score == 1.0
    assert compute_resilience(chaos).component("latency").score is None


def test_cost_overhead_against_a_baseline() -> None:
    score = compute_resilience(
        report([event(1, "token_timeout", "delayed")], cost_usd=0.15),
        baseline=report(cost_usd=0.10),
    )
    assert score.component("cost").score == pytest.approx(0.5)
    zero_cost_baseline = compute_resilience(report(cost_usd=1.0), baseline=report())
    assert zero_cost_baseline.component("cost").score is None


def test_retry_efficiency_penalizes_retry_storms() -> None:
    events = [event(1), event(2)]
    calls = [
        call(1, "llm", "error", "e1"),
        call(2, "llm", "error", "e2"),
        *[call(n, "llm", "error") for n in range(3, 9)],
        call(9, "llm"),
    ]
    score = compute_resilience(report(events, calls))
    efficiency = score.component("retry_efficiency")
    assert efficiency.observed == {"retries": 8, "failures": 2}
    assert efficiency.score == pytest.approx(0.25)


def test_retry_efficiency_needs_a_complete_call_log_and_a_retry() -> None:
    assert compute_resilience(report([event(1)])).component("retry_efficiency").detail == (
        "no call log"
    )
    truncated = report([event(1)], [call(1, "llm", "error", "e1")], calls_dropped=3)
    assert compute_resilience(truncated).component("retry_efficiency").score is None
    fallback = report([event(1)], [call(1, "llm", "error", "e1")])
    assert compute_resilience(fallback).component("retry_efficiency").detail == "no retry observed"


def test_probe_component_weights_post_over_during() -> None:
    probes = [
        {"probe": "p", "phase": "pre", "status": "passed", "weight": 1.0},
        {"probe": "p", "phase": "during", "status": "failed", "weight": 1.0},
        {"probe": "p", "phase": "post", "status": "passed", "weight": 1.0},
    ]
    fired = [event(1, "silent_degradation", "degraded")]  # unverified: recovery n/a
    score = compute_resilience(report(fired, probes=probes))
    assert score.component("probes").score == pytest.approx(1 / 1.5)
    assert score.score == 67  # probes are the only computable component


def test_failed_pre_probe_and_dry_run_are_inconclusive() -> None:
    probes = [{"probe": "health", "phase": "pre", "status": "failed"}]
    unsteady = compute_resilience(report([event(1, "token_timeout", "delayed")], probes=probes))
    assert unsteady.score is None and unsteady.status == "inconclusive"
    assert "no steady state" in unsteady.reasons[0]
    dry = compute_resilience(report([event(1, "token_timeout", "delayed")], dry_run=True))
    assert dry.score is None and dry.reasons == ["dry run: no fault was injected"]
    empty = compute_resilience(report(probes=[{"phase": "post", "status": "passed"}]))
    assert empty.score is None and empty.reasons == [
        "no fault fired, so there was nothing to be resilient to"
    ]
    assert not empty.meets(0) and empty.grade is None
    crashed = compute_resilience(report(unhandled_error={"type": "ValueError", "message": ""}))
    assert crashed.reasons[0].endswith("the run raised ValueError first")
    unverified = compute_resilience(report([event(1, "silent_degradation", "degraded")]))
    assert unverified.reasons == ["no component could be computed: add probes or a fidelity judge"]


def test_aborted_runs_are_scored_with_a_reason() -> None:
    score = compute_resilience(report([event(1, "token_timeout", "delayed")], aborted=True))
    assert score.score == 100 and "circuit breaker aborted" in score.reasons[0]


def test_weighted_mean_renormalizes_missing_components() -> None:
    r = report(
        [event(1), event(2, "token_timeout", "delayed")],
        [call(1, "llm", "error", "e1"), call(2, "llm", "error")],
        probes=[{"probe": "p", "phase": "post", "status": "passed"}],
    )
    # recovery 0.5 (w .35), probes 1.0 (w .25), retry efficiency 1.0 (w .15)
    score = compute_resilience(r)
    assert score.score == round(100 * (0.35 * 0.5 + 0.25 + 0.15) / 0.75)
    assert (
        compute_resilience(r, weights={"recovery": 1, "probes": 0, "retry_efficiency": 0}).score
        == 50
    )


def test_grades_and_summary() -> None:
    graded = {
        score: ResilienceScore(score, "scored", "id", "n", [], []).grade
        for score in (95, 80, 60, 45, 10)
    }
    assert graded == {95: "A", 80: "B", 60: "C", 45: "D", 10: "F"}
    trending = ResilienceScore(72, "scored", "id", "agent", [], [], trend={"delta": 8})
    assert trending.summary() == "resilience score for 'agent': 72/100 (C), +8 from last run"
    assert (
        "inconclusive (dry run"
        in ResilienceScore(
            None, "inconclusive", "id", "agent", [], [], reasons=["dry run"]
        ).summary()
    )


def test_weights_and_tolerances_are_validated() -> None:
    assert validate_weights(None) == DEFAULT_WEIGHTS
    with pytest.raises(ValueError, match="unknown resilience component 'speed'"):
        validate_weights({"speed": 1})
    with pytest.raises(ValueError, match="finite number"):
        validate_weights({"recovery": -1})
    with pytest.raises(ValueError, match="greater than 0"):
        validate_weights(dict.fromkeys(DEFAULT_WEIGHTS, 0))
    with pytest.raises(ValueError, match="latency_tolerance"):
        compute_resilience(report(), latency_tolerance=0)


def test_json_round_trip_and_saved_reports(tmp_path) -> None:
    r = report([event(1)], [call(1, "llm", "error", "e1"), call(2, "llm")])
    path = tmp_path / "run.json"
    path.write_text(r.model_dump_json())
    score = compute_resilience(path, baseline=json.loads(report().model_dump_json()))
    data = score.as_json()
    assert data["version"] == "1.0" and data["grade"] == "A"
    again = ResilienceScore.from_json(json.loads(json.dumps(data)))
    assert again.as_json() == data


def test_report_resilience_score_property() -> None:
    assert report().resilience_score is None
    assert report(resilience={"score": 81}).resilience_score == 81
    assert report(resilience={"score": None}).resilience_score is None
    assert report(resilience={"score": True}).resilience_score is None


def test_live_session_scores_a_retrying_app() -> None:
    def app() -> str:
        for _ in range(5):
            try:
                return chaos_call(lambda: "ok", step_name="llm")
            except RateLimitStormError:
                continue
        raise RuntimeError("gave up")

    with chaos_session([RateLimitStormFault(burst_count=2, retry_after=0)]) as session:
        app()
    score = compute_resilience(session.to_report("live"))
    assert score.score == 100
    assert score.component("retry_efficiency").observed == {"retries": 2, "failures": 2}


def test_a_different_call_kind_is_not_a_retry_of_the_step() -> None:
    r = report([event(1)], [call(1, "llm", "error", "e1"), {**call(2, "llm"), "kind": "stream"}])
    assert verdicts(r) == ["fallback"]
