"""Optional AgenticLens integration.

Only useful if you have *both* `agentic-chaos` and `agenticlens` installed
(`pip install agentic-chaos[agenticlens]`) and want chaos events merged
directly onto an AgenticLens `Workflow` you built with `profile()`/`step()`,
so a single `agenticlens analyze` sees cost/latency data and chaos impact
together. Neither function here imports `agenticlens` at runtime -- both are
duck-typed against the shapes AgenticLens's `Workflow`/`StepHandle` happen to
have, so this module only actually needs agenticlens installed if *you* pass
it real AgenticLens objects (which requires you to have imported it anyway).

If you don't have AgenticLens, ignore this module -- `agentic_chaos.chaos_call()`
and the CLI's own `ChaosReport` output work with zero dependency on it.
"""

from typing import TYPE_CHECKING, Any

from agentic_chaos.chaos.context import ChaosSession

if TYPE_CHECKING:
    from agenticlens.models import Workflow
    from agenticlens.profiler.step import StepHandle


def attach_events(session: "ChaosSession", workflow: "Workflow") -> None:
    """Append `session`'s recorded chaos events onto `workflow.chaos_events`
    (schema v1.1), so `agenticlens analyze` sees them alongside whatever
    `profile()`/`step()` already recorded on that same `Workflow`."""
    workflow.chaos_events.extend(session.events_as_json())


def step_kwargs(step: "StepHandle") -> dict[str, Any]:
    """Build the `step_id`/`step_name` kwargs `chaos_call()` expects from an
    AgenticLens `StepHandle`, so callers don't need to reach into
    `step.step.id`/`step.step.name` themselves.

    ```python
    chaos_call(fn, arg, **step_kwargs(s), faults=["token_timeout"])
    ```
    """
    return {"step_id": step.step.id, "step_name": step.step.name}
