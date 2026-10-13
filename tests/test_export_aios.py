"""AIOS v0.4-draft Run export of native chaos reports."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from agentic_chaos import (
    StreamCutFault,
    ToolCallFailureFault,
    __version__,
    chaos_call,
    chaos_session,
    chaos_stream,
)
from agentic_chaos.export import to_aios_run
from agentic_chaos.models import ChaosReport

SPEC_ROOT = Path(__file__).resolve().parents[2] / "ai-operations-spec"
SPEC_SCHEMAS = SPEC_ROOT / "specification" / "v0.4" / "schemas"
START = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


def _report(events: list[dict[str, Any]], **kwargs: Any) -> ChaosReport:
    return ChaosReport(
        id="report-1",
        name="demo",
        start_time=START,
        end_time=START + timedelta(seconds=2),
        chaos_events=events,
        **kwargs,
    )


def _event(index: int, **fields: Any) -> dict[str, Any]:
    return {
        "id": f"event-{index}",
        "fault_type": "rate_limit_storm",
        "outcome": "errored",
        "message": "429",
        "timestamp": (START + timedelta(milliseconds=index)).isoformat(),
        **fields,
    }


def graph_errors(artifact: dict[str, Any]) -> list[str]:
    """The v0.4 conformance graph rules this exporter must satisfy (P02, P05-P07, P10)."""
    objects = {artifact["id"]: "run"}
    for key, kind in (("requests", "request"), ("steps", "step")):
        objects.update({item["id"]: kind for item in artifact[key]})
    for key in ("occurrences", "evidence"):
        objects.update({item["id"]: item["type"] for item in artifact[key]})
    errors = []
    counted = (
        len(artifact["requests"])
        + len(artifact["steps"])
        + len(artifact["occurrences"])
        + len(artifact["evidence"])
        + 1
    )
    if len(objects) != counted:
        errors.append("object ids not unique")
    rels = artifact["relationships"]
    for rel in rels:
        for end in (rel["source"], rel["target"]):
            if not end.get("external") and objects.get(end["id"]) != end["type"]:
                errors.append(f"{rel['id']} endpoint {end['id']} unresolved")
    for step in artifact["steps"]:
        contains = [r for r in rels if r["type"] == "contains" and r["target"]["id"] == step["id"]]
        if len(contains) != 1:
            errors.append(f"step {step['id']} contained {len(contains)} times")
    for occurrence in artifact["occurrences"]:
        observed = [
            r for r in rels if r["type"] == "observed-in" and r["source"]["id"] == occurrence["id"]
        ]
        if len(observed) != 1:
            errors.append(f"occurrence {occurrence['id']} observed {len(observed)} times")
    for event in artifact["events"]:
        if objects.get(event["object_id"]) != event["object_type"]:
            errors.append(f"event {event['event_id']} target unresolved")
    return errors


def test_maps_report_events_onto_run_steps_occurrences_and_evidence() -> None:
    artifact = to_aios_run(
        _report(
            [
                _event(1, step_id="planner", step_name="Planner"),
                _event(2, step_id="planner", step_name="Planner"),
                _event(3, fault_type="tool_failure", step_name="Search Tool"),
            ]
        )
    )

    assert artifact["spec_version"] == "0.4-draft"
    assert artifact["artifact_type"] == "run"
    assert artifact["id"] == "report-1"
    assert artifact["started_at"] == "2026-10-13T12:00:00Z"
    assert artifact["ended_at"] == "2026-10-13T12:00:02Z"
    assert [step["id"] for step in artifact["steps"]] == ["report-1:step:1", "report-1:step:2"]
    assert artifact["steps"][0]["attributes"] == {
        "native_step_id": "planner",
        "native_step_name": "Planner",
    }
    assert artifact["steps"][1]["attributes"] == {"native_step_name": "Search Tool"}
    assert [step["category"] for step in artifact["steps"]] == ["model", "tool"]
    assert [o["type"] for o in artifact["occurrences"]] == [
        "model_interaction",
        "model_interaction",
        "tool_invocation",
    ]
    assert all(o["status"] == "failed" for o in artifact["occurrences"])
    assert [e["attributes"]["source_event_id"] for e in artifact["evidence"]] == [
        "event-1",
        "event-2",
        "event-3",
    ]
    assert {e["status"] for e in artifact["evidence"]} == {"detected"}
    assert graph_errors(artifact) == []


def test_does_not_invent_recovery_or_retry_chains() -> None:
    artifact = to_aios_run(_report([_event(1, step_id="s"), _event(2, step_id="s")]))

    assert all("status" not in step for step in artifact["steps"])
    assert not {"follows", "caused"} & {rel["type"] for rel in artifact["relationships"]}
    assert "aiops.reliability.recovered" not in {e["event_name"] for e in artifact["events"]}


def test_lifecycle_events_follow_run_status() -> None:
    artifact = to_aios_run(_report([_event(1, step_id="s")]), status="failed")
    names = [event["event_name"] for event in artifact["events"]]

    assert names == [
        "aiops.run.started",
        "aiops.model.failed",
        "aiops.reliability.detected",
        "aiops.run.failed",
    ]
    assert artifact["status"] == artifact["requests"][0]["status"] == "failed"


def test_non_errored_outcomes_keep_their_outcome_and_skip_failure_events() -> None:
    artifact = to_aios_run(_report([_event(1, step_id="s", outcome="degraded")]))

    assert artifact["occurrences"][0]["status"] == "degraded"
    assert "aiops.model.failed" not in {e["event_name"] for e in artifact["events"]}


def test_unattributed_events_land_on_an_explicit_placeholder_step() -> None:
    artifact = to_aios_run(_report([_event(1)]))

    assert artifact["steps"][0]["id"] == "report-1:step:1"
    assert artifact["steps"][0]["name"] == "unattributed"
    assert "reason" in artifact["steps"][0]["attributes"]
    assert graph_errors(artifact) == []


def test_workflow_link_is_external() -> None:
    artifact = to_aios_run(_report([]), workflow_id="support-workflow")

    assert artifact["workflow_id"] == "support-workflow"
    run_of = artifact["relationships"][0]
    assert run_of["type"] == "run-of"
    assert run_of["target"] == {"id": "support-workflow", "type": "workflow", "external": True}


def test_package_fields_ride_in_the_namespaced_extension() -> None:
    artifact = to_aios_run(_report([], agent_topology={"nodes": []}))
    extension = artifact["extensions"]["io.deepagentlabs.agentic-chaos"]

    assert extension["producer_version"] == __version__
    assert extension["report_name"] == "demo"
    assert extension["agent_topology"] == {"nodes": []}
    assert "drift_report" not in extension


def test_open_report_without_end_time_has_no_end_event_or_duration() -> None:
    report = ChaosReport(name="open", start_time=START)
    artifact = to_aios_run(report, status="running")

    assert "ended_at" not in artifact
    assert [e["event_name"] for e in artifact["events"]] == ["aiops.run.started"]
    assert [m["name"] for m in artifact["measurements"]] == ["chaos_event_count"]


def test_accepts_report_json_and_rejects_unknown_status() -> None:
    report = _report([_event(1, step_id="s")])
    from_json = to_aios_run(json.loads(report.model_dump_json()))
    assert from_json == to_aios_run(report)
    with pytest.raises(ValueError, match="status"):
        to_aios_run(report, status="exploded")


def test_bad_event_timestamp_falls_back_to_run_start() -> None:
    artifact = to_aios_run(_report([_event(1, step_id="s", timestamp="yesterday")]))
    detected = [e for e in artifact["events"] if e["event_name"] == "aiops.reliability.detected"]
    assert detected[0]["occurred_at"] == "2026-10-13T12:00:00Z"


def _live_report() -> ChaosReport:
    def search(query: str) -> str:
        return query

    started = datetime.now(timezone.utc)
    with chaos_session([StreamCutFault(), ToolCallFailureFault()]) as session:
        list(chaos_stream(iter(["a", "b"]), step_name="answer", faults=["stream_cut"]))
        with pytest.raises(Exception):  # noqa: B017 - the injected tool failure
            chaos_call(search, "q", step_name="search", faults=["tool_failure"])
    return ChaosReport(
        name="live",
        start_time=started,
        end_time=datetime.now(timezone.utc),
        chaos_events=session.events_as_json(),
    )


def test_live_session_export_satisfies_graph_rules() -> None:
    artifact = to_aios_run(_live_report())

    assert len(artifact["occurrences"]) == 2
    assert graph_errors(artifact) == []


def test_export_validates_against_the_published_v04_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    referencing = pytest.importorskip("referencing")
    if not SPEC_SCHEMAS.exists():
        pytest.skip("ai-operations-spec sibling checkout unavailable")
    documents = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in SPEC_SCHEMAS.glob("*.schema.json")
    }
    registry = referencing.Registry().with_resources(
        (doc["$id"], referencing.Resource.from_contents(doc)) for doc in documents.values()
    )
    validator = jsonschema.Draft202012Validator(
        documents["run.schema.json"],
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    )
    spec_semantics = _spec_semantic_checker()
    for artifact in (
        to_aios_run(_live_report()),
        to_aios_run(
            _report([]).model_copy(
                update={
                    "aborted": True,
                    "abort_reason": {
                        "threshold": "max_cost_usd",
                        "limit": 1,
                        "observed": 1,
                        "in_flight_at_abort": 0,
                    },
                }
            )
        ),
        to_aios_run(
            _report([]).model_copy(
                update={
                    "dry_run": True,
                    "planned_events": [
                        {"fault_type": "rate_limit_storm", "outcome": "would_inject"}
                    ],
                }
            )
        ),
        to_aios_run(_report([_event(1)]), status="failed", workflow_id="wf"),
        to_aios_run(_report([_event(1, step_id="report-1"), _event(2, step_name="A B")])),
    ):
        errors = [error.message for error in validator.iter_errors(artifact)]
        assert errors == []
        assert spec_semantics(artifact) == []


def _spec_semantic_checker():
    """The spec repository's own semantic-conformance checker (tests/test_v04_schema.py)."""
    spec_tests = SPEC_ROOT / "tests" / "test_v04_schema.py"
    if not spec_tests.exists():
        pytest.skip("ai-operations-spec semantic checker unavailable")
    spec = importlib.util.spec_from_file_location("aios_v04_semantics", spec_tests)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.semantic_errors


def test_blank_report_id_is_rejected() -> None:
    report = _report([])
    report.id = "  "
    with pytest.raises(ValueError, match="non-blank"):
        to_aios_run(report)


def test_step_ids_never_collide_or_self_reference() -> None:
    artifact = to_aios_run(
        _report(
            [
                _event(1, step_id="report-1"),  # same as the run id
                _event(2, step_name="A B"),
                _event(3, step_name="A-B"),  # would share a slug with "A B"
                _event(4, step_id="   ", step_name="Named"),  # blank id falls back to name
            ]
        )
    )

    step_ids = [step["id"] for step in artifact["steps"]]
    assert len(step_ids) == len(set(step_ids)) == 4
    assert "report-1" not in step_ids
    assert artifact["steps"][3]["attributes"] == {"native_step_name": "Named"}
    contains = [rel for rel in artifact["relationships"] if rel["type"] == "contains"]
    assert all(rel["source"]["id"] != rel["target"]["id"] for rel in contains)
    assert graph_errors(artifact) == []
