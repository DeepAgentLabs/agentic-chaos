import pytest

from agentic_chaos import chaos_call, chaos_session
from agentic_chaos.chaos.faults import FAULT_REGISTRY


@pytest.mark.parametrize("fault_cls", list(FAULT_REGISTRY.values()))
def test_probability_zero_passes_through(fault_cls):
    fault = fault_cls(probability=0)
    with chaos_session([fault]) as session:
        assert chaos_call(lambda: "original") == "original"
    assert session.events == []


@pytest.mark.parametrize("fault_cls", list(FAULT_REGISTRY.values()))
@pytest.mark.parametrize("probability", [-0.1, 1.1, float("nan")])
def test_invalid_probability(fault_cls, probability):
    with pytest.raises(ValueError, match="probability"):
        fault_cls(probability=probability)


def test_probability_reproducible():
    from agentic_chaos import SilentDegradationFault

    def run():
        with chaos_session([SilentDegradationFault(probability=0.5, seed=42)]) as session:
            for _ in range(100):
                chaos_call(lambda: "hello")
        return len(session.events)

    assert run() == run()
    assert 0 < run() < 100
