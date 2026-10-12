"""Lazy sync/async stream faults; events are emitted when delivery is affected."""

import asyncio
import math
import time
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

from agentic_chaos.chaos.context import ChaosSession, get_active_session
from agentic_chaos.chaos.faults import BaseFault, ChaosFaultError, FaultOutcome
from agentic_chaos.models.chaos_event import ChaosEvent


class StreamHangError(ChaosFaultError):
    """The simulated connection froze and reached its configured timeout."""


class StreamFault(BaseFault):
    """A delivery fault, applied using chaos_stream() or chaos_astream()."""

    def __init__(
        self,
        *,
        after_chunks: int = 0,
        delay_seconds: float = 1.0,
        probability: float = 1.0,
        seed: int | None = None,
    ) -> None:
        super().__init__(probability, seed)
        if isinstance(after_chunks, bool) or not isinstance(after_chunks, int) or after_chunks < 0:
            raise ValueError("after_chunks must be a non-negative integer")
        if not math.isfinite(delay_seconds) or delay_seconds < 0:
            raise ValueError("delay_seconds must be finite and non-negative")
        self.after_chunks = after_chunks
        self.delay_seconds = delay_seconds

    def trigger(self, call: Callable[..., Any], **kwargs: Any) -> FaultOutcome:
        raise TypeError("Streaming faults require chaos_stream() / chaos_astream()")


class StreamCutFault(StreamFault):
    """End delivery after after_chunks chunks (default: one), without reading ahead."""

    name = "stream_cut"

    def __init__(
        self, after_chunks: int = 1, *, probability: float = 1.0, seed: int | None = None
    ) -> None:
        super().__init__(after_chunks=after_chunks, probability=probability, seed=seed)


class StreamHangFault(StreamFault):
    """Freeze after after_chunks, then raise StreamHangError after a bounded delay."""

    name = "stream_hang"


class SlowTTFTFault(StreamFault):
    """Delay the first delivered chunk."""

    name = "slow_ttft"


class SlowChunksFault(StreamFault):
    """Delay delivery between chunks, leaving the first chunk unchanged."""

    name = "slow_chunks"


def _select(names: list[str] | None) -> tuple[ChaosSession | None, StreamFault | None]:
    session = get_active_session()
    if session is None:
        return None, None
    candidates = session.select_faults(names)
    if len(candidates) > 1:
        raise ValueError("Select one fault with faults=[...] for each stream")
    if not candidates:
        return session, None
    fault = candidates[0]
    if not isinstance(fault, StreamFault):
        raise TypeError("chaos_stream() requires a streaming fault")
    return session, fault if fault.should_trigger() else None


def _event(
    session: ChaosSession,
    fault: StreamFault,
    count: int,
    step_id: str | None,
    step_name: str | None,
) -> ChaosEvent:
    event = ChaosEvent(
        fault_type=fault.name,
        step_id=step_id,
        step_name=step_name,
        outcome="errored"
        if isinstance(fault, StreamHangFault)
        else ("degraded" if isinstance(fault, StreamCutFault) else "delayed"),
        message=f"{fault.name} affected stream after {count} delivered chunks",
        detail={
            "chunks_delivered": count,
            "delay_seconds": fault.delay_seconds,
            "after_chunks": fault.after_chunks,
        },
    )
    session.events.append(event)
    return event


def chaos_stream(
    source: Iterator[Any],
    *,
    faults: list[str] | None = None,
    step_id: str | None = None,
    step_name: str | None = None,
) -> Iterator[Any]:
    """Wrap a synchronous iterator. Consume and close it inside the active session.

    The returned generator owns source and closes it on exhaustion, fault, or close().
    Probability is sampled once per stream, not once per chunk.
    """
    session, fault = _select(faults)

    def deliver() -> Iterator[Any]:
        count = 0
        emitted = False
        try:
            while True:
                if (
                    fault is not None
                    and session is not None
                    and (
                        isinstance(fault, (StreamCutFault, StreamHangFault))
                        and count >= fault.after_chunks
                    )
                ):
                    event = _event(session, fault, count, step_id, step_name)
                    if isinstance(fault, StreamHangFault):
                        time.sleep(fault.delay_seconds)
                        raise StreamHangError(event.message, event)
                    return
                try:
                    chunk = next(source)
                except StopIteration:
                    return
                if (
                    fault is not None
                    and session is not None
                    and (
                        (isinstance(fault, SlowTTFTFault) and count == 0)
                        or (isinstance(fault, SlowChunksFault) and count > 0)
                    )
                ):
                    if not emitted:
                        _event(session, fault, count, step_id, step_name)
                        emitted = True
                    time.sleep(fault.delay_seconds)
                count += 1
                yield chunk
        finally:
            close = getattr(source, "close", None)
            if close is not None:
                close()

    return deliver()


def chaos_astream(
    source: AsyncIterator[Any],
    *,
    faults: list[str] | None = None,
    step_id: str | None = None,
    step_name: str | None = None,
) -> AsyncIterator[Any]:
    """Async equivalent of chaos_stream(); delays are cancellable asyncio sleeps."""
    session, fault = _select(faults)

    async def deliver() -> AsyncIterator[Any]:
        count = 0
        emitted = False
        try:
            while True:
                if (
                    fault is not None
                    and session is not None
                    and (
                        isinstance(fault, (StreamCutFault, StreamHangFault))
                        and count >= fault.after_chunks
                    )
                ):
                    event = _event(session, fault, count, step_id, step_name)
                    if isinstance(fault, StreamHangFault):
                        await asyncio.sleep(fault.delay_seconds)
                        raise StreamHangError(event.message, event)
                    return
                try:
                    chunk = await source.__anext__()
                except StopAsyncIteration:
                    return
                if (
                    fault is not None
                    and session is not None
                    and (
                        (isinstance(fault, SlowTTFTFault) and count == 0)
                        or (isinstance(fault, SlowChunksFault) and count > 0)
                    )
                ):
                    if not emitted:
                        _event(session, fault, count, step_id, step_name)
                        emitted = True
                    await asyncio.sleep(fault.delay_seconds)
                count += 1
                yield chunk
        finally:
            close = getattr(source, "aclose", None) or getattr(source, "close", None)
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result

    return deliver()
