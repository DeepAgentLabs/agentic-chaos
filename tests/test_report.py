import json
from datetime import datetime, timezone

from agentic_chaos.models import ChaosReport


def test_chaos_report_defaults() -> None:
    report = ChaosReport(name="Test Run", start_time=datetime.now(timezone.utc))

    assert report.id
    assert report.end_time is None
    assert report.chaos_events == []
    assert report.drift_report is None


def test_chaos_report_json_round_trip() -> None:
    report = ChaosReport(
        name="Test Run",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        chaos_events=[
            {
                "fault_type": "token_timeout",
                "outcome": "errored",
                "message": "x",
                "fidelity_score": 0.25,
                "edge_id": "edge-1",
            }
        ],
    )

    dumped = json.loads(report.model_dump_json())

    assert dumped["name"] == "Test Run"
    assert dumped["chaos_events"][0]["fault_type"] == "token_timeout"
    assert dumped["chaos_events"][0]["fidelity_score"] == 0.25
    assert dumped["chaos_events"][0]["edge_id"] == "edge-1"


def test_chaos_report_preserves_drift_report_extension() -> None:
    report = ChaosReport(
        name="Drift Run",
        start_time=datetime.now(timezone.utc),
        drift_report={
            "has_drift": True,
            "findings": [{"kind": "model", "changed": True, "message": "Model metadata changed."}],
        },
    )

    dumped = json.loads(report.model_dump_json())

    assert dumped["drift_report"]["has_drift"] is True
    assert dumped["drift_report"]["findings"][0]["kind"] == "model"


def test_session_to_report_records_calls_and_unhandled_error():
    from agentic_chaos.chaos import chaos_call, chaos_session
    from agentic_chaos.chaos.faults import RateLimitStormError, RateLimitStormFault

    with chaos_session([RateLimitStormFault(burst_count=1)]) as session:
        try:
            chaos_call(lambda: "x", step_name="llm")
        except RateLimitStormError as exc:
            error = exc
    report = session.to_report("unit", error=error)

    assert report.start_time == session.started_at
    assert report.end_time is not None and report.end_time >= report.start_time
    assert report.unhandled_error == {
        "type": "RateLimitStormError",
        "message": str(error),
        "fault_type": "rate_limit_storm",
        "event_id": session.events[0].id,
    }
    assert len(report.calls) == 1
    assert report.calls_dropped == 0


def test_session_to_report_without_error_and_plain_exception():
    from agentic_chaos.chaos import chaos_session
    from agentic_chaos.chaos.context import describe_error

    with chaos_session([]) as session:
        pass
    assert session.to_report("clean").unhandled_error is None
    assert describe_error(ValueError("bad")) == {"type": "ValueError", "message": "bad"}


def test_old_reports_without_v06_fields_still_load():
    from datetime import datetime, timezone

    from agentic_chaos.models import ChaosReport

    report = ChaosReport.model_validate(
        {"name": "old", "start_time": datetime.now(timezone.utc).isoformat()}
    )
    assert report.calls == []
    assert report.calls_dropped == 0
    assert report.unhandled_error is None
