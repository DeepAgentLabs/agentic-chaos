import random

import pytest

from agentic_chaos.chaos.faults import (
    FAULT_REGISTRY,
    RateLimitStormError,
    RateLimitStormFault,
    SilentDegradationFault,
    TokenTimeoutError,
    TokenTimeoutFault,
    garble_text,
    resolve_faults,
)


def test_token_timeout_raises_by_default() -> None:
    fault = TokenTimeoutFault(hang_seconds=0.0)
    calls = []

    def call() -> str:
        calls.append(1)
        return "real result"

    outcome = fault.trigger(call, step_id="s1", step_name="Planner")

    assert calls == []  # the real call never happens in "raise" mode
    assert isinstance(outcome.raised, TokenTimeoutError)
    assert outcome.event is not None
    assert outcome.event.outcome == "errored"
    assert outcome.event.fault_type == "token_timeout"
    assert outcome.event.step_id == "s1"


def test_token_timeout_delay_mode_calls_through() -> None:
    fault = TokenTimeoutFault(hang_seconds=0.0, mode="delay")

    outcome = fault.trigger(lambda: "real result", step_id=None, step_name=None)

    assert outcome.result == "real result"
    assert outcome.raised is None
    assert outcome.event is not None
    assert outcome.event.outcome == "delayed"


def test_token_timeout_rejects_invalid_mode() -> None:
    with pytest.raises(ValueError):
        TokenTimeoutFault(mode="explode")


def test_rate_limit_storm_fires_for_burst_then_passes_through() -> None:
    fault = RateLimitStormFault(burst_count=2, retry_after=0.0)
    calls = []

    def call() -> str:
        calls.append(1)
        return "real result"

    for _ in range(2):
        outcome = fault.trigger(call, step_id=None, step_name=None)
        assert isinstance(outcome.raised, RateLimitStormError)
    assert calls == []

    outcome = fault.trigger(call, step_id=None, step_name=None)
    assert outcome.result == "real result"
    assert outcome.event is None
    assert calls == [1]


def test_rate_limit_storm_error_carries_retry_after() -> None:
    fault = RateLimitStormFault(burst_count=1, retry_after=2.5)
    outcome = fault.trigger(lambda: "x", step_id=None, step_name=None)
    assert isinstance(outcome.raised, RateLimitStormError)
    assert outcome.raised.retry_after == 2.5


def test_garble_text_preserves_shape() -> None:
    rng = random.Random(0)
    original = "The quick brown fox, jumps!"
    garbled = garble_text(original, rng)

    assert len(garbled) == len(original)
    assert garbled.split(" ") != original.split(" ")
    # Punctuation itself (not the letters attached to it) passes through untouched.
    assert garbled.endswith("!")
    assert not garbled.split(",")[0].endswith(",")


def test_garble_text_garbles_words_with_attached_punctuation() -> None:
    # Regression: word.isalpha() used to skip "fox," and "jumps!" entirely,
    # since trailing punctuation makes the whole token non-alphabetic.
    rng = random.Random(0)
    garbled = garble_text("fox, jumps!", rng)

    assert not garbled.startswith("fox")
    assert "jumps" not in garbled
    assert garbled.endswith("!")
    assert garbled[3] == ","


def test_garble_text_pure_punctuation_token_untouched() -> None:
    rng = random.Random(0)
    assert garble_text("- ... --", rng) == "- ... --"


def test_silent_degradation_corrupts_string_result() -> None:
    fault = SilentDegradationFault(seed=1)
    outcome = fault.trigger(lambda: "the real answer", step_id="s1", step_name="Final")

    assert outcome.raised is None
    assert outcome.event is not None
    assert outcome.event.outcome == "degraded"
    assert isinstance(outcome.result, str)
    assert outcome.result != "the real answer"
    assert len(outcome.result) == len("the real answer")


def test_silent_degradation_corrupts_content_attribute() -> None:
    class Response:
        def __init__(self) -> None:
            self.content = "genuine content"
            self.other = "untouched"

    fault = SilentDegradationFault(seed=2)
    outcome = fault.trigger(lambda: Response(), step_id=None, step_name=None)

    assert outcome.result.content != "genuine content"
    assert outcome.result.other == "untouched"


def test_silent_degradation_falls_back_to_text_when_content_is_read_only() -> None:
    # Regression: a failed .content write used to abort the fallback chain
    # entirely (via `break`) instead of trying .text next.
    class Response:
        def __init__(self) -> None:
            self.text = "genuine text"

        @property
        def content(self) -> str:
            return "read-only content"

    fault = SilentDegradationFault(seed=3)
    outcome = fault.trigger(lambda: Response(), step_id=None, step_name=None)

    assert outcome.result.text != "genuine text"


def test_silent_degradation_custom_degrade_fn() -> None:
    fault = SilentDegradationFault(degrade_fn=lambda result: "REPLACED")
    outcome = fault.trigger(lambda: "anything", step_id=None, step_name=None)
    assert outcome.result == "REPLACED"


def test_silent_degradation_falls_back_when_result_cannot_be_deepcopied() -> None:
    class Response:
        def __init__(self) -> None:
            self.content = "genuine content"

        def __deepcopy__(self, memo: dict[int, object]) -> "Response":
            raise TypeError("cannot deepcopy response")

    fault = SilentDegradationFault(seed=4)
    outcome = fault.trigger(lambda: Response(), step_id=None, step_name=None)

    assert outcome.baseline == "genuine content"
    assert outcome.result.content != "genuine content"
    assert outcome.event is not None


def test_fault_registry_has_all_three_v01_faults() -> None:
    assert {"token_timeout", "rate_limit_storm", "silent_degradation"}.issubset(FAULT_REGISTRY)


def test_fault_registry_has_v02_agent_faults() -> None:
    assert {"tool_failure", "memory_corruption", "infinite_loop"}.issubset(FAULT_REGISTRY)


def test_resolve_faults_from_comma_string() -> None:
    faults = resolve_faults("token_timeout, rate_limit_storm")
    assert [f.name for f in faults] == ["token_timeout", "rate_limit_storm"]


def test_resolve_faults_passes_through_instances() -> None:
    instance = TokenTimeoutFault(hang_seconds=5.0)
    faults = resolve_faults([instance, "rate_limit_storm"])
    assert faults[0] is instance
    assert faults[1].name == "rate_limit_storm"


def test_resolve_faults_unknown_name_raises() -> None:
    with pytest.raises(ValueError, match="Unknown fault"):
        resolve_faults("not_a_real_fault")
