"""Run existing synchronous fault implementations without blocking the event loop."""

import asyncio
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from typing import Any, TypeVar

from agentic_chaos.chaos.context import ChaosSession, active_session, get_active_session
from agentic_chaos.chaos.inject import chaos_call

T = TypeVar("T")


async def chaos_acall(
    fn: Callable[..., Coroutine[Any, Any, T]],
    *args: Any,
    faults: list[str] | None = None,
    step_id: str | None = None,
    step_name: str | None = None,
    **kwargs: Any,
) -> T:
    """Async call injection, with legacy blocking faults isolated in a worker.

    The actual provider coroutine runs on the caller's event loop. Cancellation
    cancels pending provider work and discards the worker's isolated event buffer.
    A bounded synchronous fault delay may finish in its worker after cancellation.
    """
    session = get_active_session()
    if session is None:
        return await fn(*args, **kwargs)
    loop = asyncio.get_running_loop()
    pending: list[Future[T]] = []
    isolated = ChaosSession(session.faults, dry_run=session.dry_run, safety=session.safety)
    cancelled = asyncio.Event()

    async def dispatch(call_args: tuple[Any, ...], call_kwargs: dict[str, Any]) -> T:
        session.safety.check()
        if cancelled.is_set():
            raise asyncio.CancelledError
        return await fn(*call_args, **call_kwargs)

    def invoke(*call_args: Any, **call_kwargs: Any) -> T:
        session.safety.check()
        if cancelled.is_set():
            raise asyncio.CancelledError
        future = asyncio.run_coroutine_threadsafe(dispatch(call_args, call_kwargs), loop)
        pending.append(future)
        if cancelled.is_set():
            future.cancel()
        return future.result()

    def run() -> T:
        token = active_session.set(isolated)
        try:
            return chaos_call(
                invoke, *args, faults=faults, step_id=step_id, step_name=step_name, **kwargs
            )
        finally:
            active_session.reset(token)

    try:
        result = await asyncio.to_thread(run)
    except asyncio.CancelledError:
        cancelled.set()
        for future in pending:
            future.cancel()
        raise
    except BaseException:
        session.events.extend(isolated.events)
        session.planned_events.extend(isolated.planned_events)
        raise
    else:
        session.events.extend(isolated.events)
        session.planned_events.extend(isolated.planned_events)
        return result
