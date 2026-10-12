import asyncio

import pytest

from agentic_chaos import (
    SlowChunksFault,
    SlowTTFTFault,
    StreamCutFault,
    StreamHangFault,
    chaos_astream,
    chaos_session,
    chaos_stream,
)
from agentic_chaos.chaos.streaming import StreamHangError


def test_cut_does_not_read_ahead_and_closes():
    seen = []
    closed = []

    def source():
        try:
            for chunk in range(5):
                seen.append(chunk)
                yield chunk
        finally:
            closed.append(True)

    with chaos_session([StreamCutFault(after_chunks=2)]) as session:
        assert list(chaos_stream(source())) == [0, 1]
    assert seen == [0, 1]
    assert closed == [True]
    assert session.events[0].detail["chunks_delivered"] == 2


@pytest.mark.parametrize(
    "fault", [SlowTTFTFault(delay_seconds=0.2), SlowChunksFault(delay_seconds=0.2)]
)
def test_delay_schedule(monkeypatch, fault):
    sleeps = []
    monkeypatch.setattr("agentic_chaos.chaos.streaming.time.sleep", sleeps.append)
    with chaos_session([fault]) as session:
        assert list(chaos_stream(iter([1, 2, 3]))) == [1, 2, 3]
    assert sleeps == [0.2] * (1 if isinstance(fault, SlowTTFTFault) else 2)
    assert len(session.events) == 1


def test_hang_is_bounded_and_records_error():
    with (
        chaos_session([StreamHangFault(delay_seconds=0)]) as session,
        pytest.raises(StreamHangError) as exc,
    ):
        list(chaos_stream(iter([1, 2])))
    assert exc.value.event is session.events[0]


def test_empty_slow_stream_has_no_event():
    with chaos_session([SlowTTFTFault(delay_seconds=0)]) as session:
        assert list(chaos_stream(iter([]))) == []
    assert session.events == []


def test_probability_zero_stream():
    with chaos_session([StreamCutFault(probability=0)]) as session:
        assert list(chaos_stream(iter([1, 2, 3]))) == [1, 2, 3]
    assert session.events == []


def test_async_cut_and_cancel_cleanup():
    async def run():
        closed = []

        async def source():
            try:
                for chunk in range(3):
                    yield chunk
            finally:
                closed.append(True)

        with chaos_session([StreamCutFault(after_chunks=2)]) as session:
            assert [x async for x in chaos_astream(source())] == [0, 1]
        assert len(session.events) == 1
        with chaos_session([SlowTTFTFault(delay_seconds=10)]):
            stream = chaos_astream(source())
            task = asyncio.create_task(stream.__anext__())
            await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert closed == [True, True]

    asyncio.run(run())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"after_chunks": -1},
        {"after_chunks": 0.5},
        {"delay_seconds": -1},
        {"delay_seconds": float("inf")},
    ],
)
def test_stream_validation(kwargs):
    with pytest.raises(ValueError):
        StreamHangFault(**kwargs)
