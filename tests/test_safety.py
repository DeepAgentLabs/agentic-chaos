"""Safety behavior and dispatch containment, exercised without live providers."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from agentic_chaos import (
    ChaosAbortedError,
    CircuitBreaker,
    RateLimitStormFault,
    SilentDegradationFault,
    SlowChunksFault,
    StreamCutFault,
    StreamHangFault,
    chaos_acall,
    chaos_astream,
    chaos_call,
    chaos_session,
    chaos_stream,
    patch_openai,
)
from agentic_chaos.cli.main import app
from agentic_chaos.export import to_aios_run
from agentic_chaos.models import ChaosReport


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_cost_usd": 0},
        {"max_cost_usd": float("nan")},
        {"max_duration_seconds": float("inf")},
        {"max_failure_rate": -1},
        {"max_failure_rate": float("nan")},
        {"max_failure_rate": True},
        {"min_calls": 0},
        {"window_size": 1.5},
        {"max_injections": True},
        {"window_size": 2, "min_calls": 3},
    ],
)
def test_invalid_limits(kwargs):
    with pytest.raises(ValueError):
        CircuitBreaker(**kwargs)


def test_cost_abort_is_sticky_and_prevents_dispatch():
    calls = []
    with chaos_session([], breaker=CircuitBreaker(max_cost_usd=1)) as session:
        session.record_usage(
            input_tokens=500_000, output_tokens=0, input_usd_per_million=1, output_usd_per_million=0
        )
        assert session.safety.cost == 0.5
        with pytest.raises(ChaosAbortedError):
            session.record_cost(0.5)
        with pytest.raises(ChaosAbortedError):
            chaos_call(lambda: calls.append("forbidden"), faults=[])
    assert calls == []
    assert session.report_fields()["abort_reason"]["threshold"] == "max_cost_usd"
    assert session.safety.in_flight == 0


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan"), True])
def test_invalid_recorded_cost(value):
    with chaos_session([]) as session, pytest.raises(ValueError):
        session.record_cost(value)


def test_rolling_failure_rate_and_fresh_breaker_state():
    breaker = CircuitBreaker(max_failure_rate=0.5, window_size=2, min_calls=2)
    with chaos_session([], breaker=breaker) as session:
        chaos_call(lambda: None)
        with pytest.raises(ValueError):
            chaos_call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert not session.safety.abort  # equality is allowed
        with pytest.raises(ChaosAbortedError):
            chaos_call(lambda: (_ for _ in ()).throw(ValueError("fail")))
    with chaos_session([], breaker=breaker) as fresh:
        chaos_call(lambda: None)
        assert fresh.safety.abort is None


def test_injection_budget_and_dry_run_preserve_target():
    calls = []
    with chaos_session(
        [SilentDegradationFault()], breaker=CircuitBreaker(max_injections=1)
    ) as session:
        chaos_call(lambda: "ok")
        with pytest.raises(ChaosAbortedError):
            chaos_call(lambda: calls.append("forbidden"))
    assert not calls
    assert session.safety.injections == 1
    with chaos_session([RateLimitStormFault()], dry_run=True) as preview:
        assert chaos_call(lambda: "original", step_name="target") == "original"
    assert not preview.events
    assert preview.planned_events[0]["step_name"] == "target"
    assert preview.safety.injections == 0


@pytest.mark.parametrize(
    "fault", [StreamCutFault(), StreamHangFault(delay_seconds=0), SlowChunksFault(delay_seconds=0)]
)
def test_sync_and_async_stream_preview(fault):
    with chaos_session([fault], dry_run=True) as session:
        assert list(chaos_stream(iter(["a", "b", "c"]))) == ["a", "b", "c"]
    assert len(session.planned_events) == 1
    assert not session.events

    async def run():
        async def source():
            for chunk in ["a", "b", "c"]:
                yield chunk

        with chaos_session([fault], dry_run=True) as preview:
            assert [chunk async for chunk in chaos_astream(source())] == ["a", "b", "c"]
        assert len(preview.planned_events) == 1
        assert not preview.events

    asyncio.run(run())


def test_stream_abort_closes_source_and_blocks_next_pull():
    pulled = []
    closed = []

    def source():
        try:
            for chunk in range(3):
                pulled.append(chunk)
                yield chunk
        finally:
            closed.append(True)

    with chaos_session(
        [StreamCutFault(after_chunks=9)], breaker=CircuitBreaker(max_cost_usd=1)
    ) as session:
        stream = chaos_stream(source())
        assert next(stream) == 0
        with pytest.raises(ChaosAbortedError):
            session.record_cost(1)
        with pytest.raises(ChaosAbortedError):
            next(stream)
    assert pulled == [0]
    assert closed == [True]
    assert session.safety.abort["in_flight_at_abort"] == 1
    assert session.safety.in_flight == 0


def test_duration_limit_blocks_next_dispatch(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("agentic_chaos.safety.time.monotonic", lambda: clock[0])
    with chaos_session([], breaker=CircuitBreaker(max_duration_seconds=1)) as session:
        clock[0] = 1.0
        with pytest.raises(ChaosAbortedError):
            chaos_call(lambda: pytest.fail("dispatched"))
    assert session.safety.abort["threshold"] == "max_duration_seconds"


def test_async_in_flight_work_is_reported_and_later_dispatch_blocked():
    async def run():
        started = asyncio.Event()
        release = asyncio.Event()
        calls = []

        async def target():
            calls.append("started")
            started.set()
            await release.wait()
            return "completed"

        with chaos_session([], breaker=CircuitBreaker(max_cost_usd=1)) as session:
            task = asyncio.create_task(chaos_acall(target))
            await started.wait()
            with pytest.raises(ChaosAbortedError):
                session.record_cost(1)
            assert session.safety.abort["in_flight_at_abort"] == 1
            with pytest.raises(ChaosAbortedError):
                await chaos_acall(target)
            release.set()
            assert await task == "completed"
        assert calls == ["started"]
        assert session.safety.in_flight == 0

    asyncio.run(run())


def test_provider_stream_creation_after_abort_never_dispatches():
    calls = []
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: calls.append(kwargs))
        )
    )
    with chaos_session([StreamCutFault()], breaker=CircuitBreaker(max_cost_usd=1)) as session:
        patch_openai(client)
        with pytest.raises(ChaosAbortedError):
            session.record_cost(1)
        with pytest.raises(ChaosAbortedError):
            client.chat.completions.create(stream=True)
    assert calls == []


@pytest.mark.parametrize("command", ["chaos", "agent"])
def test_cli_preview_and_abort_reports(tmp_path, command):
    script = tmp_path / "target.py"
    script.write_text("from agentic_chaos import chaos_call\nchaos_call(lambda: 'ok')\n")
    save = tmp_path / "report.json"
    result = CliRunner().invoke(
        app,
        [
            command,
            "run",
            str(script),
            "--inject",
            "rate_limit_storm",
            "--dry-run",
            "--save",
            str(save),
        ],
    )
    assert result.exit_code == 0, result.output
    report = ChaosReport.model_validate_json(save.read_text())
    assert report.dry_run and report.planned_events and not report.chaos_events
    script.write_text(
        "from agentic_chaos.chaos.context import get_active_session\n"
        "get_active_session().record_cost(1)\n"
    )
    aios = tmp_path / "aios.json"
    result = CliRunner().invoke(
        app,
        [
            command,
            "run",
            str(script),
            "--inject",
            "rate_limit_storm",
            "--max-cost-usd",
            "1",
            "--save",
            str(save),
            "--save-aios",
            str(aios),
        ],
    )
    assert result.exit_code == 1
    report = ChaosReport.model_validate_json(save.read_text())
    assert report.aborted and report.abort_reason["threshold"] == "max_cost_usd"
    import json

    assert json.loads(aios.read_text())["status"] == "cancelled"


def test_aios_abort_and_preview_keep_evidence_honest():
    with chaos_session([RateLimitStormFault()], dry_run=True) as session:
        chaos_call(lambda: "ok")
    report = ChaosReport(
        name="preview", start_time=datetime.now(timezone.utc), **session.report_fields()
    )
    artifact = to_aios_run(report)
    assert artifact["occurrences"] == artifact["evidence"] == []
    extension = artifact["extensions"]["io.deepagentlabs.agentic-chaos"]
    assert extension["safety"]["planned_events"]


def test_async_preview_and_cancellation_share_safety_without_late_dispatch():
    async def run():
        with chaos_session([RateLimitStormFault()], dry_run=True) as preview:

            async def original():
                return "ok"

            assert await chaos_acall(original) == "ok"
        assert len(preview.planned_events) == 1 and not preview.events
        entered = asyncio.Event()

        async def target():
            entered.set()
            await asyncio.Event().wait()

        with chaos_session([]) as session:
            task = asyncio.create_task(chaos_acall(target))
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            # Worker bookkeeping can finish after task cancellation.
            for _ in range(100):
                if session.safety.in_flight == 0:
                    break
                await asyncio.sleep(0.001)
            assert session.safety.in_flight == 0

    asyncio.run(run())


def test_containment_negative_control_detects_direct_bypass():
    dispatched = []

    def target():
        dispatched.append("direct bypass")

    with chaos_session([], breaker=CircuitBreaker(max_cost_usd=1)) as session:
        with pytest.raises(ChaosAbortedError):
            session.record_cost(1)
        with pytest.raises(ChaosAbortedError):
            chaos_call(target)
        assert dispatched == []
        target()  # deliberately bypass instrumentation: containment must detect it
        with pytest.raises(AssertionError):
            assert dispatched == []


def test_async_stream_abort_closes_and_rejects_further_reads():
    async def run():
        closed = []
        pulled = []

        async def source():
            try:
                for item in range(3):
                    pulled.append(item)
                    yield item
            finally:
                closed.append(True)

        with chaos_session(
            [StreamCutFault(after_chunks=9)], breaker=CircuitBreaker(max_cost_usd=1)
        ) as session:
            stream = chaos_astream(source())
            assert await stream.__anext__() == 0
            with pytest.raises(ChaosAbortedError):
                session.record_cost(1)
            with pytest.raises(ChaosAbortedError):
                await stream.__anext__()
        assert pulled == [0] and closed == [True]
        assert session.safety.in_flight == 0

    asyncio.run(run())


def test_inherited_async_context_cannot_dispatch_after_session_exit():
    async def run():
        release = asyncio.Event()
        calls = []

        async def child():
            await release.wait()

            async def target():
                calls.append("forbidden")

            await chaos_acall(target)

        with chaos_session([]):
            task = asyncio.create_task(child())
        release.set()
        with pytest.raises(RuntimeError, match="ended"):
            await task
        assert calls == []

    asyncio.run(run())


def test_breaker_configuration_is_copied_per_session():
    breaker = CircuitBreaker(max_cost_usd=1)
    with chaos_session([], breaker=breaker) as session:
        breaker.max_cost_usd = 100
        with pytest.raises(ChaosAbortedError):
            session.record_cost(1)


def test_abort_during_upstream_read_blocks_delivery():
    async def run():
        entered = asyncio.Event()
        release = asyncio.Event()
        closed = []

        async def source():
            try:
                entered.set()
                await release.wait()
                yield "must not be delivered"
            finally:
                closed.append(True)

        with chaos_session(
            [StreamCutFault(after_chunks=9)], breaker=CircuitBreaker(max_cost_usd=1)
        ) as session:
            stream = chaos_astream(source())
            task = asyncio.create_task(stream.__anext__())
            await entered.wait()
            with pytest.raises(ChaosAbortedError):
                session.record_cost(1)
            release.set()
            with pytest.raises(ChaosAbortedError):
                await task
        assert closed == [True] and session.safety.in_flight == 0

    asyncio.run(run())


def test_stateful_pass_through_does_not_consume_injection_budget():
    from agentic_chaos.chaos.faults import RateLimitStormError

    with chaos_session(
        [RateLimitStormFault(burst_count=1)], breaker=CircuitBreaker(max_injections=1)
    ) as session:
        with pytest.raises(RateLimitStormError):
            chaos_call(lambda: "ok")
        assert chaos_call(lambda: "recovered") == "recovered"
        assert session.safety.injections == 1
        assert session.safety.abort is None


def test_preview_eligibility_and_state_are_separate_from_real_faults():
    from agentic_chaos import HandoffCorruptionFault, InfiniteLoopFault, ToolCallFailureFault

    rate = RateLimitStormFault(burst_count=1)
    loop = InfiniteLoopFault(force_turns=1)
    tool = ToolCallFailureFault(tool_name="search")
    handoff = HandoffCorruptionFault(from_node="a", to_node="b")
    with chaos_session([rate, loop, tool, handoff], dry_run=True) as session:
        for name in (rate.name, loop.name):
            for _ in range(3):
                assert chaos_call(lambda: "original", faults=[name]) == "original"
        chaos_call(lambda: "ok", faults=[tool.name], step_name="unrelated")
        chaos_call(lambda: "ok", faults=[handoff.name])
        chaos_call(
            lambda: "ok",
            faults=[handoff.name],
            _chaos_edge_id="ab",
            _chaos_from_node="wrong",
            _chaos_to_node="b",
        )
        chaos_call(lambda: "ok", faults=[tool.name], step_name="search")
        chaos_call(
            lambda: "ok",
            faults=[handoff.name],
            _chaos_edge_id="ab",
            _chaos_from_node="a",
            _chaos_to_node="b",
        )
    assert [item["fault_type"] for item in session.planned_events] == [
        rate.name,
        loop.name,
        tool.name,
        handoff.name,
    ]
    assert rate._fired == loop._fired == 0
    assert session.safety.injections == 0


def test_custom_eventless_fault_releases_reserved_injection():
    from agentic_chaos.chaos.faults import BaseFault, FaultOutcome

    class PassThrough(BaseFault):
        name = "pass_through"

        def trigger(self, call, **kwargs):
            return FaultOutcome(result=call())

    with chaos_session([PassThrough()], breaker=CircuitBreaker(max_injections=1)) as session:
        for _ in range(3):
            assert chaos_call(lambda: "ok") == "ok"
    assert session.safety.injections == 0


def test_stream_close_failures_count_as_failed_completions():
    class Source:
        def __iter__(self):
            return self

        def __next__(self):
            raise StopIteration

        def close(self):
            raise ValueError("close failed")

    with (
        chaos_session(
            [StreamCutFault(after_chunks=9)], breaker=CircuitBreaker(max_failure_rate=1)
        ) as session,
        pytest.raises(ValueError, match="close failed"),
    ):
        list(chaos_stream(Source()))
    assert list(session.safety.failures) == [True]
    assert session.safety.in_flight == 0

    async def run():
        class AsyncSource:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

            async def aclose(self):
                raise ValueError("async close failed")

        with (
            chaos_session(
                [StreamCutFault(after_chunks=9)], breaker=CircuitBreaker(max_failure_rate=0)
            ) as session,
            pytest.raises(ChaosAbortedError),
        ):
            await chaos_astream(AsyncSource()).__anext__()
        assert list(session.safety.failures) == [True]
        assert session.safety.abort["threshold"] == "max_failure_rate"
        assert session.safety.in_flight == 0

    asyncio.run(run())
