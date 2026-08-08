from collections.abc import Callable
from typing import Any, TypeVar

from agentic_chaos.chaos.context import get_active_session
from agentic_chaos.judges import score_outcome

T = TypeVar("T")


def chaos_call(
    fn: Callable[..., T],
    *args: Any,
    step_id: str | None = None,
    step_name: str | None = None,
    edge_id: str | None = None,
    from_node: str | None = None,
    to_node: str | None = None,
    faults: list[str] | None = None,
    **kwargs: Any,
) -> T:
    """Call `fn(*args, **kwargs)`, subject to whatever `chaos_session()` is
    active in the current context.

    Outside a `chaos_session(...)` block this is transparent -- `fn` is called
    directly and no fault ever fires, so instrumented application code behaves
    identically whether or not chaos is enabled. No other library is required
    to use this function; `step_id`/`step_name` are plain strings you choose
    yourself (e.g. if you're also using AgenticLens's `step()`, pass
    `step_id=s.step.id, step_name=s.step.name` to correlate the two).

    Pass `faults` to pick which of the session's configured faults applies at
    this call site; it's only optional when exactly one fault is configured
    for the active session -- with more than one configured, omitting it
    raises, since silently picking one for you would be surprising.
    """
    session = get_active_session()
    if session is None:
        return fn(*args, **kwargs)

    candidates = session.select_faults(faults)
    if not candidates:
        return fn(*args, **kwargs)
    if len(candidates) > 1:
        names = ", ".join(f.name for f in candidates)
        raise ValueError(
            f"Multiple faults are configured for this chaos_session() ({names}). "
            "Pass faults=[...] to chaos_call() to pick which one applies at this call site."
        )

    outcome = candidates[0].trigger(
        lambda *call_args, **call_kwargs: fn(*call_args, **call_kwargs),
        step_id=step_id,
        step_name=step_name,
        call_args=args,
        call_kwargs=kwargs,
        edge_id=edge_id,
        from_node=from_node,
        to_node=to_node,
    )
    if outcome.event is not None:
        score_outcome(
            outcome.event,
            baseline=outcome.baseline,
            observed=outcome.result,
            step_id=step_id,
            step_name=step_name,
        )
        session.events.append(outcome.event)
    if outcome.raised is not None:
        raise outcome.raised
    return outcome.result  # type: ignore[no-any-return]
