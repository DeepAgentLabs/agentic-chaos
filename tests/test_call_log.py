import asyncio

import pytest

from agentic_chaos import (
    RateLimitStormFault,
    StreamCutFault,
    StreamHangFault,
    chaos_acall,
    chaos_astream,
    chaos_call,
    chaos_session,
    chaos_stream,
)
from agentic_chaos.chaos.calls import CallLog
from agentic_chaos.chaos.faults import RateLimitStormError
from agentic_chaos.chaos.streaming import StreamHangError


def test_records_ok_and_injected_error_calls_in_order():
    with chaos_session([RateLimitStormFault(burst_count=1)]) as session:
        with pytest.raises(RateLimitStormError):
            chaos_call(lambda: "a", step_name="llm")
        assert chaos_call(lambda: "b", step_name="llm") == "b"

    first, second = session.calls.as_json()
    assert (first["sequence"], second["sequence"]) == (1, 2)
    assert first["status"] == "error"
    assert first["error_type"] == "RateLimitStormError"
    assert first["fault_type"] == "rate_limit_storm"
    assert first["event_id"] == session.events[0].id
    assert second["status"] == "ok"
    assert second["fault_type"] is None
    assert second["duration_s"] >= 0
    assert "_started" not in first


def test_target_exception_is_recorded_without_fault_attribution():
    def boom():
        raise KeyError("x")

    with chaos_session([]) as session, pytest.raises(KeyError):
        chaos_call(boom, step_name="tool")
    (record,) = session.calls.as_json()
    assert record["status"] == "error"
    assert record["error_type"] == "KeyError"
    assert record["fault_type"] is None


def test_no_session_records_nothing():
    assert chaos_call(lambda: 1) == 1


def test_dry_run_records_calls_as_baseline():
    with chaos_session([RateLimitStormFault()], dry_run=True) as session:
        chaos_call(lambda: 1, step_name="llm")
    (record,) = session.calls.as_json()
    assert record["status"] == "ok"
    assert record["fault_type"] is None
    assert session.report_fields()["calls"] == [record]


def test_streams_record_once_with_fault_attribution():
    with chaos_session([StreamCutFault(after_chunks=1)]) as session:
        assert list(chaos_stream(iter("abc"), step_name="provider")) == ["a"]
    (record,) = session.calls.as_json()
    assert record["kind"] == "stream"
    assert record["status"] == "ok"
    assert record["fault_type"] == "stream_cut"


def test_stream_hang_records_error():
    fault = StreamHangFault(after_chunks=0, delay_seconds=0)
    with chaos_session([fault]) as session, pytest.raises(StreamHangError):
        list(chaos_stream(iter("abc")))
    (record,) = session.calls.as_json()
    assert record["status"] == "error"
    assert record["fault_type"] == "stream_hang"


def test_async_call_and_stream_share_the_parent_log():
    async def answer():
        return "ok"

    async def source():
        yield "x"

    async def main():
        with chaos_session([]) as session:
            await chaos_acall(answer, step_name="llm")
            assert [chunk async for chunk in chaos_astream(source(), step_name="s")] == ["x"]
        return session

    session = asyncio.run(main())
    assert [r["kind"] for r in session.calls.as_json()] == ["call", "stream"]


def test_log_is_bounded():
    log = CallLog(max_records=1)
    for _ in range(3):
        log.finish(log.begin(kind="call", step_id=None, step_name=None))
    assert len(log.as_json()) == 1
    assert log.dropped == 2


@pytest.mark.parametrize("value", [-1, True, 1.5])
def test_rejects_invalid_bounds(value):
    with pytest.raises(ValueError):
        CallLog(max_records=value)
