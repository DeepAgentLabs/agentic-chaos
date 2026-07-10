from datetime import datetime, timezone

import pytest
from agenticlens import step
from agenticlens.models import Metrics, Step, StepType, Workflow
from agenticlens.profiler.context import current_workflow

from agentic_chaos.chaos.faults import RateLimitStormError, TokenTimeoutFault
from agentic_chaos.chaos.inject import chaos_call
from agentic_chaos.chaos.session import chaos_session


def test_chaos_call_passes_through_with_no_active_session() -> None:
    assert chaos_call(lambda x: x * 2, 21) == 42


def test_chaos_call_applies_configured_fault() -> None:
    with chaos_session([TokenTimeoutFault(hang_seconds=0.0)]) as session:
        with pytest.raises(Exception):  # noqa: B017 -- TokenTimeoutError from chaos_call
            chaos_call(lambda: "unreachable", faults=["token_timeout"])
        assert len(session.events) == 1
        assert session.events[0].fault_type == "token_timeout"


def test_chaos_call_requires_faults_when_session_has_multiple() -> None:
    with (
        chaos_session(["token_timeout", "rate_limit_storm"]),
        pytest.raises(ValueError, match="Multiple faults"),
    ):
        chaos_call(lambda: "x")


def test_chaos_call_uses_sole_configured_fault_when_faults_omitted() -> None:
    with chaos_session([TokenTimeoutFault(hang_seconds=0.0)]) as session:
        with pytest.raises(Exception):  # noqa: B017
            chaos_call(lambda: "x")
        assert len(session.events) == 1


def test_chaos_call_unknown_fault_name_raises() -> None:
    with chaos_session(["token_timeout"]), pytest.raises(ValueError, match="not configured"):
        chaos_call(lambda: "x", faults=["rate_limit_storm"])


def test_nested_chaos_session_raises() -> None:
    with (
        chaos_session(["token_timeout"]),
        pytest.raises(RuntimeError, match="Nested"),
        chaos_session(["rate_limit_storm"]),
    ):
        pass


def test_chaos_call_correlates_step_id_via_step_handle() -> None:
    workflow = Workflow(name="Test", start_time=datetime.now(timezone.utc))
    token = current_workflow.set(workflow)
    try:
        with (
            chaos_session([TokenTimeoutFault(hang_seconds=0.0)]) as session,
            step("Planner", type="planner") as s,
            pytest.raises(Exception),  # noqa: B017
        ):
            chaos_call(lambda: "x", step=s)
    finally:
        current_workflow.reset(token)

    assert session.events[0].step_id == workflow.steps[0].id
    assert session.events[0].step_name == "Planner"


def test_rate_limit_storm_retry_loop_recovers_within_session() -> None:
    attempts = 0

    def flaky_call() -> str:
        nonlocal attempts
        attempts += 1
        return "success"

    with chaos_session(["rate_limit_storm"]) as session:
        result = None
        for _ in range(5):
            try:
                result = chaos_call(flaky_call, faults=["rate_limit_storm"])
                break
            except RateLimitStormError:
                continue

    assert result == "success"
    assert attempts == 1  # the real call only ever runs once chaos stops firing
    assert len(session.events) == 3  # default burst_count


def test_session_apply_to_extends_workflow_chaos_events() -> None:
    workflow = Workflow(name="Test", start_time=datetime.now(timezone.utc))
    workflow.steps.append(Step(id="s1", name="Planner", type=StepType.PLANNER, metrics=Metrics()))

    with chaos_session([TokenTimeoutFault(hang_seconds=0.0)]) as session:
        with pytest.raises(Exception):  # noqa: B017
            chaos_call(lambda: "x", faults=["token_timeout"])
        session.apply_to(workflow)

    assert len(workflow.chaos_events) == 1
    assert workflow.chaos_events[0]["fault_type"] == "token_timeout"
    assert isinstance(workflow.chaos_events[0]["timestamp"], str)  # JSON-mode serialized
