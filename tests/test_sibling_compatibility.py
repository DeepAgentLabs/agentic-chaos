"""Optional checkout compatibility checks; no runtime sibling dependencies."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentic_chaos import StreamCutFault, chaos_session, chaos_stream
from agentic_chaos.models import ChaosReport


def report():
    with chaos_session([StreamCutFault()]) as session:
        list(chaos_stream(iter(["a", "b"]), step_name="provider"))
    return ChaosReport(
        name="v0.5",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        chaos_events=session.events_as_json(),
    )


def test_lens_consumes_stream_events():
    pytest.importorskip("agenticlens")
    from agenticlens.config.settings import RecommenderConfig
    from agenticlens.models import Workflow
    from agenticlens.recommenders.chaos_impact import ChaosImpactRecommender

    workflow = Workflow.model_validate(report().model_dump(mode="json"))
    recommendations = ChaosImpactRecommender().evaluate(workflow, RecommenderConfig())
    assert len(recommendations) == 1
    assert recommendations[0].metadata["fault_type"] == "stream_cut"


def test_tower_reads_native_report(monkeypatch):
    source = Path(__file__).resolve().parents[2] / "agenticops-control-tower" / "src"
    if not source.exists():
        pytest.skip("Control Tower sibling checkout unavailable")
    monkeypatch.syspath_prepend(str(source))
    from agenticops_control_tower.adapters.evidence import summarize_evidence
    from agenticops_control_tower.models.evidence import EvidenceLink

    link = EvidenceLink(
        agent_id="test",
        source="agentic-chaos",
        source_version="0.5.0",
        artifact_type="chaos_report",
        artifact_ref="report.json",
        observed_at=datetime.now(timezone.utc),
    )
    result = summarize_evidence(link, report().model_dump(mode="json"))
    assert result.availability == "available"
    assert result.details["event_count"] == 1


def test_mcp_discovers_new_faults(monkeypatch):
    source = Path(__file__).resolve().parents[2] / "mcp-server" / "src"
    if not source.exists():
        pytest.skip("MCP sibling checkout unavailable")
    monkeypatch.syspath_prepend(str(source))
    from deep_agentic_core_mcp.adapters.agentic_chaos import list_faults

    names = {entry["name"] for entry in list_faults()["faults"]}
    assert {
        "stream_cut",
        "stream_hang",
        "slow_ttft",
        "slow_chunks",
        "auth_error",
        "context_length",
    } <= names


def safety_report(*, preview=False):
    from agentic_chaos import ChaosAbortedError, CircuitBreaker, RateLimitStormFault, chaos_call

    with chaos_session(
        [RateLimitStormFault()], dry_run=preview, breaker=CircuitBreaker(max_cost_usd=1)
    ) as session:
        if preview:
            chaos_call(lambda: "ok", step_name="provider")
        else:
            with pytest.raises(ChaosAbortedError):
                session.record_cost(1)
    return ChaosReport(
        name="safety",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        **session.report_fields(),
    )


@pytest.mark.parametrize("preview", [False, True])
def test_lens_accepts_additive_safety_report_without_false_faults(preview):
    pytest.importorskip("agenticlens")
    from agenticlens.models import Workflow

    workflow = Workflow.model_validate(safety_report(preview=preview).model_dump(mode="json"))
    assert not workflow.chaos_events


@pytest.mark.parametrize("preview", [False, True])
def test_tower_accepts_safety_reports_without_invented_events(monkeypatch, preview):
    source = Path(__file__).resolve().parents[2] / "agenticops-control-tower" / "src"
    if not source.exists():
        pytest.skip("Control Tower sibling checkout unavailable")
    monkeypatch.syspath_prepend(str(source))
    from agenticops_control_tower.adapters.evidence import summarize_evidence
    from agenticops_control_tower.models.evidence import EvidenceLink

    link = EvidenceLink(
        agent_id="test",
        source="agentic-chaos",
        source_version="0.5.2",
        artifact_type="chaos_report",
        artifact_ref="report.json",
        observed_at=datetime.now(timezone.utc),
    )
    result = summarize_evidence(link, safety_report(preview=preview).model_dump(mode="json"))
    assert result.availability == "available"
    assert result.details["event_count"] == 0


def test_mcp_exports_abort_and_preview_metadata(monkeypatch):
    source = Path(__file__).resolve().parents[2] / "mcp-server" / "src"
    if not source.exists():
        pytest.skip("MCP sibling checkout unavailable")
    monkeypatch.syspath_prepend(str(source))
    from deep_agentic_core_mcp.adapters.agentic_chaos import export_aios_run

    for preview in (False, True):
        artifact = export_aios_run(safety_report(preview=preview).model_dump(mode="json"))
        assert artifact["status"] == ("completed" if preview else "cancelled")
        assert not artifact["evidence"]
