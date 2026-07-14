import random

import pytest

from agentic_chaos.agents.faults import (
    InfiniteLoopFault,
    MemoryCorruptionFault,
    ToolCallFailureError,
    ToolCallFailureFault,
)
from agentic_chaos.chaos.faults import FAULT_REGISTRY, resolve_faults
from agentic_chaos.chaos.inject import chaos_call
from agentic_chaos.chaos.session import chaos_session


# ---------------------------------------------------------------------------
# ToolCallFailureFault
# ---------------------------------------------------------------------------


class TestToolCallFailureFault:
    def test_error_mode_raises_without_calling(self) -> None:
        fault = ToolCallFailureFault(mode="error")
        calls: list[int] = []

        def call() -> str:
            calls.append(1)
            return "result"

        outcome = fault.trigger(call, step_id="t1", step_name="search")

        assert calls == []
        assert isinstance(outcome.raised, ToolCallFailureError)
        assert outcome.event is not None
        assert outcome.event.outcome == "errored"
        assert outcome.event.fault_type == "tool_failure"

    def test_timeout_mode_sleeps_then_raises(self) -> None:
        fault = ToolCallFailureFault(mode="timeout", timeout_seconds=0.0)

        outcome = fault.trigger(lambda: "x", step_id=None, step_name=None)

        assert isinstance(outcome.raised, ToolCallFailureError)
        assert outcome.event is not None
        assert outcome.event.outcome == "errored"
        assert "timed out" in outcome.event.message

    def test_empty_mode_calls_but_discards_result(self) -> None:
        calls: list[int] = []

        def call() -> str:
            calls.append(1)
            return "real result"

        fault = ToolCallFailureFault(mode="empty")
        outcome = fault.trigger(call, step_id=None, step_name=None)

        assert calls == [1]  # real call happened
        assert outcome.result is None  # but result discarded
        assert outcome.raised is None
        assert outcome.event is not None
        assert outcome.event.outcome == "degraded"

    def test_rejects_invalid_mode(self) -> None:
        with pytest.raises(ValueError, match="mode must be"):
            ToolCallFailureFault(mode="explode")

    def test_tool_name_filters_by_step_name(self) -> None:
        fault = ToolCallFailureFault(mode="error", tool_name="search")

        # Matching tool — should fire
        outcome = fault.trigger(lambda: "x", step_id=None, step_name="search")
        assert isinstance(outcome.raised, ToolCallFailureError)

    def test_tool_name_passes_through_non_matching(self) -> None:
        fault = ToolCallFailureFault(mode="error", tool_name="search")

        # Non-matching tool — should pass through
        outcome = fault.trigger(lambda: "real", step_id=None, step_name="calculator")
        assert outcome.result == "real"
        assert outcome.event is None
        assert outcome.raised is None

    def test_tool_name_none_targets_all(self) -> None:
        fault = ToolCallFailureFault(mode="error", tool_name=None)

        outcome = fault.trigger(lambda: "x", step_id=None, step_name="anything")
        assert isinstance(outcome.raised, ToolCallFailureError)

    def test_custom_error_message(self) -> None:
        fault = ToolCallFailureFault(error_message="Service unavailable")
        outcome = fault.trigger(lambda: "x", step_id=None, step_name=None)
        assert "Service unavailable" in outcome.event.message  # type: ignore[union-attr]

    def test_error_carries_event(self) -> None:
        fault = ToolCallFailureFault(mode="error")
        outcome = fault.trigger(lambda: "x", step_id="s1", step_name="my_tool")
        assert isinstance(outcome.raised, ToolCallFailureError)
        assert outcome.raised.event.step_name == "my_tool"


# ---------------------------------------------------------------------------
# MemoryCorruptionFault
# ---------------------------------------------------------------------------


class TestMemoryCorruptionFault:
    def test_garble_mode_corrupts_string(self) -> None:
        fault = MemoryCorruptionFault(mode="garble", seed=1)
        outcome = fault.trigger(lambda: "important data", step_id=None, step_name=None)

        assert outcome.raised is None
        assert isinstance(outcome.result, str)
        assert outcome.result != "important data"
        assert len(outcome.result) == len("important data")
        assert outcome.event is not None
        assert outcome.event.outcome == "degraded"

    def test_truncate_mode_cuts_string(self) -> None:
        fault = MemoryCorruptionFault(mode="truncate")
        outcome = fault.trigger(lambda: "important data here", step_id=None, step_name=None)

        assert isinstance(outcome.result, str)
        assert len(outcome.result) < len("important data here")
        assert outcome.event is not None

    def test_truncate_mode_cuts_list(self) -> None:
        fault = MemoryCorruptionFault(mode="truncate")
        outcome = fault.trigger(lambda: [1, 2, 3, 4, 5, 6], step_id=None, step_name=None)

        assert isinstance(outcome.result, list)
        assert len(outcome.result) < 6
        assert len(outcome.result) >= 1

    def test_truncate_mode_cuts_dict(self) -> None:
        fault = MemoryCorruptionFault(mode="truncate", seed=0)
        data = {"a": 1, "b": 2, "c": 3, "d": 4}
        outcome = fault.trigger(lambda: data, step_id=None, step_name=None)

        assert isinstance(outcome.result, dict)
        assert len(outcome.result) < len(data)

    def test_inject_mode_adds_garbage_to_string(self) -> None:
        fault = MemoryCorruptionFault(mode="inject", seed=1)
        outcome = fault.trigger(lambda: "clean text", step_id=None, step_name=None)

        assert isinstance(outcome.result, str)
        assert len(outcome.result) > len("clean text")
        assert "INJECTED" in outcome.result

    def test_inject_mode_adds_garbage_to_list(self) -> None:
        fault = MemoryCorruptionFault(mode="inject", seed=1)
        outcome = fault.trigger(lambda: ["a", "b"], step_id=None, step_name=None)

        assert isinstance(outcome.result, list)
        assert len(outcome.result) == 3
        assert any("__garbage_" in str(item) for item in outcome.result)

    def test_inject_mode_adds_garbage_to_dict(self) -> None:
        fault = MemoryCorruptionFault(mode="inject", seed=1)
        outcome = fault.trigger(lambda: {"key": "value"}, step_id=None, step_name=None)

        assert isinstance(outcome.result, dict)
        assert len(outcome.result) > 1
        assert any(k.startswith("__injected_") for k in outcome.result)

    def test_rejects_invalid_mode(self) -> None:
        with pytest.raises(ValueError):
            MemoryCorruptionFault(mode="delete_everything")

    def test_garble_corrupts_content_attribute(self) -> None:
        class State:
            def __init__(self) -> None:
                self.content = "genuine content"

        fault = MemoryCorruptionFault(mode="garble", seed=2)
        outcome = fault.trigger(lambda: State(), step_id=None, step_name=None)

        assert outcome.result.content != "genuine content"


# ---------------------------------------------------------------------------
# InfiniteLoopFault
# ---------------------------------------------------------------------------


class TestInfiniteLoopFault:
    def test_forces_extra_turns_then_passes_through(self) -> None:
        fault = InfiniteLoopFault(force_turns=3, continue_value="CONTINUE")

        results = []
        for _ in range(5):
            outcome = fault.trigger(lambda: "DONE", step_id=None, step_name=None)
            results.append(outcome.result)

        assert results[:3] == ["CONTINUE", "CONTINUE", "CONTINUE"]
        assert results[3:] == ["DONE", "DONE"]

    def test_records_events_for_forced_turns_only(self) -> None:
        fault = InfiniteLoopFault(force_turns=2)
        events = []

        for _ in range(4):
            outcome = fault.trigger(lambda: "DONE", step_id=None, step_name=None)
            if outcome.event is not None:
                events.append(outcome.event)

        assert len(events) == 2
        assert all(e.outcome == "looped" for e in events)
        assert events[0].detail["forced_turn"] == 1
        assert events[1].detail["forced_turn"] == 2

    def test_real_call_always_executes(self) -> None:
        calls: list[int] = []

        def call() -> str:
            calls.append(1)
            return "result"

        fault = InfiniteLoopFault(force_turns=2)
        for _ in range(3):
            fault.trigger(call, step_id=None, step_name=None)

        assert len(calls) == 3  # real call runs every time

    def test_custom_continue_value(self) -> None:
        fault = InfiniteLoopFault(force_turns=1, continue_value={"action": "retry"})
        outcome = fault.trigger(lambda: "DONE", step_id=None, step_name=None)
        assert outcome.result == {"action": "retry"}


# ---------------------------------------------------------------------------
# Integration with chaos_session / chaos_call / FAULT_REGISTRY
# ---------------------------------------------------------------------------


class TestAgentFaultsIntegration:
    def test_agent_faults_registered_in_fault_registry(self) -> None:
        assert "tool_failure" in FAULT_REGISTRY
        assert "memory_corruption" in FAULT_REGISTRY
        assert "infinite_loop" in FAULT_REGISTRY

    def test_resolve_faults_finds_agent_faults(self) -> None:
        faults = resolve_faults("tool_failure,memory_corruption,infinite_loop")
        names = [f.name for f in faults]
        assert names == ["tool_failure", "memory_corruption", "infinite_loop"]

    def test_tool_failure_via_chaos_call(self) -> None:
        with chaos_session([ToolCallFailureFault()]) as session:
            with pytest.raises(ToolCallFailureError):
                chaos_call(lambda: "x", faults=["tool_failure"])
            assert len(session.events) == 1
            assert session.events[0].fault_type == "tool_failure"

    def test_memory_corruption_via_chaos_call(self) -> None:
        with chaos_session([MemoryCorruptionFault(seed=0)]) as session:
            result = chaos_call(
                lambda: "clean data", faults=["memory_corruption"], step_name="memory"
            )
            assert result != "clean data"
            assert len(session.events) == 1
            assert session.events[0].fault_type == "memory_corruption"

    def test_infinite_loop_via_chaos_call(self) -> None:
        with chaos_session([InfiniteLoopFault(force_turns=2)]) as session:
            results = []
            for _ in range(4):
                r = chaos_call(lambda: "DONE", faults=["infinite_loop"])
                results.append(r)

            assert results[:2] != ["DONE", "DONE"]
            assert results[2:] == ["DONE", "DONE"]
            assert len(session.events) == 2

    def test_mixed_v01_and_v02_faults_in_session(self) -> None:
        from agentic_chaos.chaos.faults import TokenTimeoutFault

        with chaos_session(
            [TokenTimeoutFault(hang_seconds=0.0), ToolCallFailureFault()]
        ) as session:
            with pytest.raises(Exception):  # noqa: B017
                chaos_call(lambda: "x", faults=["token_timeout"])

            with pytest.raises(ToolCallFailureError):
                chaos_call(lambda: "x", faults=["tool_failure"])

            assert len(session.events) == 2
            assert session.events[0].fault_type == "token_timeout"
            assert session.events[1].fault_type == "tool_failure"
