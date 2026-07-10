from agentic_chaos.models import ChaosEvent


def test_chaos_event_defaults() -> None:
    event = ChaosEvent(fault_type="token_timeout", outcome="errored", message="boom")

    assert event.id
    assert event.step_id is None
    assert event.step_name is None
    assert event.detail == {}
    assert event.timestamp is not None


def test_chaos_event_json_round_trip() -> None:
    event = ChaosEvent(
        fault_type="silent_degradation",
        step_id="s1",
        step_name="Final Response",
        outcome="degraded",
        message="corrupted",
        detail={"seed": 7},
    )

    dumped = event.model_dump(mode="json")

    assert dumped["fault_type"] == "silent_degradation"
    assert isinstance(dumped["timestamp"], str)
    assert dumped["detail"] == {"seed": 7}
