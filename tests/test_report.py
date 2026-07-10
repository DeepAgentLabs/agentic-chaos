import json
from datetime import datetime, timezone

from agentic_chaos.models import ChaosReport


def test_chaos_report_defaults() -> None:
    report = ChaosReport(name="Test Run", start_time=datetime.now(timezone.utc))

    assert report.id
    assert report.end_time is None
    assert report.chaos_events == []


def test_chaos_report_json_round_trip() -> None:
    report = ChaosReport(
        name="Test Run",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        chaos_events=[{"fault_type": "token_timeout", "outcome": "errored", "message": "x"}],
    )

    dumped = json.loads(report.model_dump_json())

    assert dumped["name"] == "Test Run"
    assert dumped["chaos_events"][0]["fault_type"] == "token_timeout"
