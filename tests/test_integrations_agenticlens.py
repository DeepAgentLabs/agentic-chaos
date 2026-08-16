from datetime import datetime, timezone

import pytest

pytest.importorskip("agenticlens")

from agenticlens import step  # noqa: E402
from agenticlens.models import Metrics, Step, StepType, Workflow  # noqa: E402
from agenticlens.profiler.context import current_workflow  # noqa: E402

from agentic_chaos.chaos.faults import TokenTimeoutFault  # noqa: E402
from agentic_chaos.chaos.inject import chaos_call  # noqa: E402
from agentic_chaos.chaos.session import chaos_session  # noqa: E402
from agentic_chaos.integrations.agenticlens import (  # noqa: E402
    attach_drift_report,
    attach_events,
    step_kwargs,
)
from agentic_chaos.models import ChaosReport  # noqa: E402


def test_step_kwargs_extracts_id_and_name_from_step_handle() -> None:
    workflow = Workflow(name="Test", start_time=datetime.now(timezone.utc))
    token = current_workflow.set(workflow)
    try:
        with step("Planner", type="planner") as s:
            kwargs = step_kwargs(s)
    finally:
        current_workflow.reset(token)

    assert kwargs == {"step_id": workflow.steps[0].id, "step_name": "Planner"}


def test_attach_events_extends_workflow_chaos_events() -> None:
    workflow = Workflow(name="Test", start_time=datetime.now(timezone.utc))
    workflow.steps.append(Step(id="s1", name="Planner", type=StepType.PLANNER, metrics=Metrics()))

    with chaos_session([TokenTimeoutFault(hang_seconds=0.0)]) as session:
        with pytest.raises(Exception):  # noqa: B017
            chaos_call(lambda: "x", faults=["token_timeout"], step_id="s1", step_name="Planner")
        attach_events(session, workflow)

    assert len(workflow.chaos_events) == 1
    assert workflow.chaos_events[0]["fault_type"] == "token_timeout"
    assert workflow.chaos_events[0]["step_id"] == "s1"


def test_step_kwargs_and_chaos_call_round_trip() -> None:
    """End-to-end: step() -> step_kwargs() -> chaos_call() -> attach_events()."""
    workflow = Workflow(name="Test", start_time=datetime.now(timezone.utc))
    token = current_workflow.set(workflow)
    try:
        with (
            chaos_session([TokenTimeoutFault(hang_seconds=0.0)]) as session,
            step("Retriever", type="retriever") as s,
            pytest.raises(Exception),  # noqa: B017
        ):
            chaos_call(lambda: "x", **step_kwargs(s))
        attach_events(session, workflow)
    finally:
        current_workflow.reset(token)

    assert workflow.chaos_events[0]["step_name"] == "Retriever"
    assert workflow.chaos_events[0]["step_id"] == workflow.steps[0].id


def test_chaos_report_is_valid_agenticlens_workflow_json() -> None:
    """A ChaosReport's JSON should load directly as an AgenticLens Workflow
    (schema v1.1) -- interop through a shared JSON shape, no code dependency
    from agentic_chaos's side."""
    report = ChaosReport(
        name="Standalone Run",
        start_time=datetime.now(timezone.utc),
        chaos_events=[{"fault_type": "token_timeout", "outcome": "errored", "message": "x"}],
    )

    workflow = Workflow.model_validate_json(report.model_dump_json())

    assert workflow.name == "Standalone Run"
    assert workflow.steps == []
    assert workflow.chaos_events[0]["fault_type"] == "token_timeout"


def test_attach_drift_report_sets_workflow_field() -> None:
    workflow = Workflow(name="Test", start_time=datetime.now(timezone.utc))
    report = {"has_drift": True, "findings": [{"kind": "prompt", "changed": True}]}

    attach_drift_report(report, workflow)

    assert workflow.drift_report == report
