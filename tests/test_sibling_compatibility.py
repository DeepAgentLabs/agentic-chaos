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


def contract_report():
    """A v0.6 report: call log, an escaped fault and topology, as the plugin saves it."""
    from agentic_chaos import TokenTimeoutFault, chaos_call
    from agentic_chaos.chaos.faults import TokenTimeoutError

    with chaos_session([TokenTimeoutFault(hang_seconds=0)]) as session:
        try:
            chaos_call(lambda: "ok", step_name="provider")
        except TokenTimeoutError as exc:
            error = exc
    return session.to_report("v0.6", error=error).model_dump(mode="json")


def test_lens_reads_v06_report_fields_as_additive():
    pytest.importorskip("agenticlens")
    from agenticlens.models import Workflow

    data = contract_report()
    assert data["calls"] and data["unhandled_error"]
    workflow = Workflow.model_validate(data)
    assert [event["fault_type"] for event in workflow.chaos_events] == ["token_timeout"]


def test_tower_reads_v06_report(monkeypatch):
    source = Path(__file__).resolve().parents[2] / "agenticops-control-tower" / "src"
    if not source.exists():
        pytest.skip("Control Tower sibling checkout unavailable")
    monkeypatch.syspath_prepend(str(source))
    from agenticops_control_tower.adapters.evidence import summarize_evidence
    from agenticops_control_tower.models.evidence import EvidenceLink

    link = EvidenceLink(
        agent_id="test",
        source="agentic-chaos",
        source_version="0.6.0",
        artifact_type="chaos_report",
        artifact_ref="report.json",
        observed_at=datetime.now(timezone.utc),
    )
    result = summarize_evidence(link, contract_report())
    assert result.availability == "available"
    assert result.details["event_count"] == 1


def test_mcp_exports_v06_report(monkeypatch):
    source = Path(__file__).resolve().parents[2] / "mcp-server" / "src"
    if not source.exists():
        pytest.skip("MCP sibling checkout unavailable")
    monkeypatch.syspath_prepend(str(source))
    from deep_agentic_core_mcp.adapters.agentic_chaos import export_aios_run

    artifact = export_aios_run(contract_report())
    extension = artifact["extensions"]["io.deepagentlabs.agentic-chaos"]
    assert extension["calls"] == {"recorded": 1, "dropped": 0}
    assert extension["unhandled_error"]["fault_type"] == "token_timeout"


def advanced_report():
    from agentic_chaos import PoisonedResponseFault, RateLimitStormFault, cascade, chaos_call
    from agentic_chaos.chaos.faults import RateLimitStormError

    with chaos_session(
        [
            cascade(
                first=RateLimitStormFault(burst_count=1),
                then=PoisonedResponseFault("policy_bypass", seed=7),
            )
        ]
    ) as session:
        with pytest.raises(RateLimitStormError):
            chaos_call(lambda: "ok")
        chaos_call(lambda: "ok")
    return session.to_report("v0.7").model_dump(mode="json")


def test_lens_reads_v07_provenance():
    pytest.importorskip("agenticlens")
    from agenticlens.models import Workflow

    workflow = Workflow.model_validate(advanced_report())
    assert len(workflow.chaos_events) == 2
    assert workflow.chaos_events[1]["detail"]["strategy"] == "policy_bypass"


def test_mcp_discovers_poisoning_and_exports_v07(monkeypatch):
    source = Path(__file__).resolve().parents[2] / "mcp-server" / "src"
    if not source.exists():
        pytest.skip("MCP sibling checkout unavailable")
    monkeypatch.syspath_prepend(str(source))
    from deep_agentic_core_mcp.adapters.agentic_chaos import export_aios_run, list_faults

    assert "poisoned_response" in {entry["name"] for entry in list_faults()["faults"]}
    artifact = export_aios_run(advanced_report())
    from agentic_chaos import __version__

    extension = artifact["extensions"]["io.deepagentlabs.agentic-chaos"]
    assert extension["producer_version"] == __version__
    assert len(artifact["evidence"]) == 2


def test_tower_counts_v07_native_events(monkeypatch):
    source = Path(__file__).resolve().parents[2] / "agenticops-control-tower" / "src"
    if not source.exists():
        pytest.skip("Control Tower sibling checkout unavailable")
    monkeypatch.syspath_prepend(str(source))
    from agenticops_control_tower.adapters.evidence import summarize_evidence
    from agenticops_control_tower.models.evidence import EvidenceLink

    link = EvidenceLink(
        agent_id="test",
        source="agentic-chaos",
        source_version="0.7.0",
        artifact_type="chaos_report",
        artifact_ref="report.json",
        observed_at=datetime.now(timezone.utc),
    )
    result = summarize_evidence(link, advanced_report())
    assert result.availability == "available"
    assert result.details["event_count"] == 2


def workflow_report():
    """A v0.8 workflow: two scoped stages and a gate, as `experiment run` saves it."""
    from agentic_chaos import RateLimitStormFault, Scope, chaos_call
    from agentic_chaos.chaos.faults import RateLimitStormError
    from agentic_chaos.workflows import ChaosWorkflow, HealthCheck, Step

    def app():
        chaos_call(lambda: "ok", step_name="safety_check")
        for _ in range(4):
            try:
                return chaos_call(lambda: "ok", step_name="llm")
            except RateLimitStormError:
                continue
        return None

    workflow = ChaosWorkflow(
        "v0.8",
        [
            Step("warm-up", faults=[RateLimitStormFault(burst_count=1)]),
            HealthCheck(fn=lambda: "ok"),
            Step("escalate", faults=[RateLimitStormFault(burst_count=2)]),
        ],
        scope=Scope(exclude_steps=["safety_check"]),
    )
    return workflow.run(app)


def test_lens_reads_v08_workflow_and_merged_reports():
    pytest.importorskip("agenticlens")
    from agenticlens.models import Workflow

    report = workflow_report()
    for data in (report.model_dump(mode="json"), report.to_chaos_report().model_dump(mode="json")):
        workflow = Workflow.model_validate(data)
        assert len(workflow.chaos_events) == 3
        assert {e["detail"]["workflow"]["step"] for e in workflow.chaos_events} == {
            "warm-up",
            "escalate",
        }


def test_tower_counts_v08_merged_events(monkeypatch):
    source = Path(__file__).resolve().parents[2] / "agenticops-control-tower" / "src"
    if not source.exists():
        pytest.skip("Control Tower sibling checkout unavailable")
    monkeypatch.syspath_prepend(str(source))
    from agenticops_control_tower.adapters.evidence import summarize_evidence
    from agenticops_control_tower.models.evidence import EvidenceLink

    link = EvidenceLink(
        agent_id="test",
        source="agentic-chaos",
        source_version="0.8.0",
        artifact_type="chaos_report",
        artifact_ref="report.json",
        observed_at=datetime.now(timezone.utc),
    )
    merged = workflow_report().to_chaos_report().model_dump(mode="json")
    result = summarize_evidence(link, merged)
    assert result.availability == "available"
    assert result.details["event_count"] == 3


def test_mcp_exports_v08_workflow_summary(monkeypatch):
    source = Path(__file__).resolve().parents[2] / "mcp-server" / "src"
    if not source.exists():
        pytest.skip("MCP sibling checkout unavailable")
    monkeypatch.syspath_prepend(str(source))
    from deep_agentic_core_mcp.adapters.agentic_chaos import export_aios_run, list_faults

    assert "rate_limit_storm" in {entry["name"] for entry in list_faults()["faults"]}
    artifact = export_aios_run(workflow_report().to_chaos_report().model_dump(mode="json"))
    extension = artifact["extensions"]["io.deepagentlabs.agentic-chaos"]
    assert extension["workflow"]["name"] == "v0.8"
    assert [node["status"] for node in extension["workflow"]["nodes"]] == ["passed"] * 3
    assert len(artifact["evidence"]) == 3
