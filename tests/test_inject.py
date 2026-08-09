import pytest

from agentic_chaos.chaos.faults import (
    BaseFault,
    FaultOutcome,
    RateLimitStormError,
    TokenTimeoutFault,
)
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


def test_chaos_call_correlates_plain_step_id_and_name() -> None:
    with (
        chaos_session([TokenTimeoutFault(hang_seconds=0.0)]) as session,
        pytest.raises(Exception),  # noqa: B017
    ):
        chaos_call(lambda: "x", step_id="s1", step_name="Planner")

    assert session.events[0].step_id == "s1"
    assert session.events[0].step_name == "Planner"


def test_chaos_call_without_step_id_leaves_correlation_unset() -> None:
    with (
        chaos_session([TokenTimeoutFault(hang_seconds=0.0)]) as session,
        pytest.raises(Exception),  # noqa: B017
    ):
        chaos_call(lambda: "x")

    assert session.events[0].step_id is None
    assert session.events[0].step_name is None


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


def test_session_events_as_json_serializes_recorded_events() -> None:
    with (
        chaos_session([TokenTimeoutFault(hang_seconds=0.0)]) as session,
        pytest.raises(Exception),  # noqa: B017
    ):
        chaos_call(lambda: "x", faults=["token_timeout"], step_id="s1", step_name="Planner")

    events = session.events_as_json()

    assert len(events) == 1
    assert events[0]["fault_type"] == "token_timeout"
    assert events[0]["step_id"] == "s1"
    assert isinstance(events[0]["timestamp"], str)  # JSON-mode serialized


def test_chaos_call_preserves_original_args_for_legacy_faults() -> None:
    class LegacyPassThroughFault(BaseFault):
        name = "legacy"

        def trigger(
            self,
            call,
            *,
            step_id=None,
            step_name=None,
        ) -> FaultOutcome:
            return FaultOutcome(result=call())

    with chaos_session([LegacyPassThroughFault()]):
        assert chaos_call(lambda x: x, 1) == 1
