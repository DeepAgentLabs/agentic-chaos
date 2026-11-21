import pytest
from agentic_chaos import TokenTimeoutFault, chaos_call
from agentic_chaos.chaos import TokenTimeoutError


@pytest.mark.chaos(faults=[TokenTimeoutFault(hang_seconds=0)], must_recover=True)
def test_timeout_fallback():
    try:
        result = chaos_call(lambda: "answer", faults=["token_timeout"], step_name="answer")
    except TokenTimeoutError:
        result = "fallback"
    assert result in {"answer", "fallback"}
