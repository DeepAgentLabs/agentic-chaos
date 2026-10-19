import json

import pytest
from typer.testing import CliRunner

from agentic_chaos import (
    CircuitBreaker,
    PoisonedResponseFault,
    RateLimitStormFault,
    TokenTimeoutFault,
    cascade,
    chaos_call,
    chaos_session,
    find_breaking_point,
)
from agentic_chaos.chaos.estimate import estimate_failure
from agentic_chaos.chaos.faults import RateLimitStormError, TokenTimeoutError
from agentic_chaos.cli.main import app
from agentic_chaos.export.aios import to_aios_run
from agentic_chaos.safety import ChaosAbortedError


def test_cascade_order_and_provenance():
    fault = cascade(
        first=RateLimitStormFault(burst_count=2), then=TokenTimeoutFault(hang_seconds=0)
    )
    with chaos_session([fault]) as session:
        for error in (RateLimitStormError, RateLimitStormError, TokenTimeoutError):
            with pytest.raises(error):
                chaos_call(lambda: "ok")
        assert chaos_call(lambda: "ok") == "ok"
    assert [e.detail["cascade_stage"] for e in session.events] == [0, 0, 1]
    assert len({e.detail["cascade_id"] for e in session.events}) == 1
    assert len(session.events) == session.to_report("cascade").injections == 3
    assert to_aios_run(session.to_report("cascade"))


def test_cascade_dry_run_does_not_mutate_stages():
    first = RateLimitStormFault(burst_count=2)
    fault = cascade(first=first, then=TokenTimeoutFault(hang_seconds=0))
    with chaos_session([fault], dry_run=True) as session:
        for _ in range(4):
            assert chaos_call(lambda: "ok") == "ok"
    assert len(session.planned_events) == 3
    assert first._fired == fault.index == 0


def test_cascade_obeys_injection_budget():
    with chaos_session(
        [cascade(first=RateLimitStormFault(burst_count=1), then=TokenTimeoutFault(hang_seconds=0))],
        breaker=CircuitBreaker(max_injections=1),
    ) as session:
        with pytest.raises(RateLimitStormError):
            chaos_call(lambda: "ok")
        with pytest.raises(ChaosAbortedError):
            chaos_call(lambda: "ok")
    assert len(session.events) == 1


@pytest.mark.parametrize(
    "strategy",
    [
        "confident_wrong",
        "partial_hallucination",
        "format_violation",
        "prompt_injection",
        "policy_bypass",
    ],
)
def test_poisoning(strategy):
    original = {"content": "original", "usage": 3}
    with chaos_session([PoisonedResponseFault(strategy, seed=42)]) as session:
        result = chaos_call(lambda: original)
    assert result["content"] != original["content"]
    assert result["usage"] == 3
    detail = session.events[0].detail
    assert detail["seed"] == 42 and detail["payload"] and detail["synthetic"]


def test_poisoning_rejects_unknown_and_unsupported():
    with pytest.raises(ValueError):
        PoisonedResponseFault("unknown")
    with chaos_session([PoisonedResponseFault()]), pytest.raises(TypeError):
        chaos_call(lambda: 42)


def test_breaking_point_uses_fresh_trials():
    def target():
        for _ in range(4):
            try:
                return chaos_call(lambda: "ok")
            except RateLimitStormError:
                pass
        raise RuntimeError("retry budget exhausted")

    result = find_breaking_point(
        target, fault=RateLimitStormFault, param="burst_count", range=(1, 10)
    )
    assert result.breaking_point == 4
    assert len(result.trials) <= 4
    assert (
        find_breaking_point(
            lambda: True, fault=RateLimitStormFault, param="burst_count", range=(1, 10)
        ).breaking_point
        is None
    )
    assert (
        find_breaking_point(
            lambda: False,
            recovered=bool,
            fault=RateLimitStormFault,
            param="burst_count",
            range=(1, 10),
        ).breaking_point
        == 1
    )


def test_breaking_point_setup_errors_propagate():
    with pytest.raises(TypeError):
        find_breaking_point(lambda: None, fault=RateLimitStormFault, param="invalid", range=(1, 3))
    with pytest.raises(ValueError):
        find_breaking_point(
            lambda: None, fault=RateLimitStormFault, param="burst_count", range=(3, 1)
        )


def test_estimate_does_not_execute_target(tmp_path):
    script = tmp_path / "danger.py"
    script.write_text('raise RuntimeError("must not execute")')
    result = CliRunner().invoke(
        app,
        [
            "estimate",
            str(script),
            "--fault",
            "rate_limit_storm",
            "--retries",
            "3",
            "--cost-per-call-usd",
            "0.04",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["extra_usd"] == pytest.approx(0.12)
    with pytest.raises(ValueError):
        estimate_failure(fault="rate_limit_storm", retries=-1, cost_per_call_usd=0.04)
    with pytest.raises(ValueError):
        estimate_failure(fault="rate_limit_storm", retries=1, cost_per_call_usd=float("nan"))


def test_cascade_probability_preview_and_live_match():
    for preview in (True, False):
        fault = cascade(
            first=RateLimitStormFault(probability=0), then=TokenTimeoutFault(hang_seconds=0)
        )
        with chaos_session([fault], dry_run=preview) as session:
            assert chaos_call(lambda: "ok") == "ok"
        assert not session.events and not session.planned_events


def test_cascade_delay_checks_abort_before_next_fault(monkeypatch):
    import agentic_chaos.chaos.advanced as advanced

    fault = cascade(
        first=RateLimitStormFault(burst_count=1),
        then=TokenTimeoutFault(hang_seconds=0),
        delay_between=10,
    )
    with chaos_session([fault], breaker=CircuitBreaker(max_cost_usd=1)) as session:
        with pytest.raises(RateLimitStormError):
            chaos_call(lambda: "ok")

        def abort(_):
            session.record_cost(1)

        monkeypatch.setattr(advanced.time, "sleep", abort)
        with pytest.raises(ChaosAbortedError):
            chaos_call(lambda: "ok")
    assert len(session.events) == 1


def test_poisoning_async():
    import asyncio

    from agentic_chaos import chaos_acall

    async def run():
        async def target():
            return "safe"

        with chaos_session([PoisonedResponseFault(payload="synthetic")]) as session:
            assert await chaos_acall(target) == "synthetic"
        assert len(session.events) == 1

    asyncio.run(run())


def test_offline_resilience_example():
    import runpy
    from pathlib import Path

    example = runpy.run_path(str(Path(__file__).parents[1] / "examples/advanced/resilience.py"))
    example["main"]()
