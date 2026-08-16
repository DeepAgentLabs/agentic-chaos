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
