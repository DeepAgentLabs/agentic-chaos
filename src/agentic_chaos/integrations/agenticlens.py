"""Optional AgenticLens integration.

Only useful if you have *both* `agentic-chaos` and `agenticlens` installed
(`pip install agentic-chaos[agenticlens]`) and want chaos events merged
directly onto an AgenticLens `Workflow` you built with `profile()`/`step()`,
so a single `agenticlens analyze` sees cost/latency data and chaos impact
together. Neither function here imports `agenticlens` at runtime -- both are
duck-typed against the shapes AgenticLens's `Workflow`/`StepHandle` happen to
have, so this module only actually needs agenticlens installed if *you* pass
it real AgenticLens objects (which requires you to have imported it anyway).

If you don't have AgenticLens, ignore this module -- `agentic_chaos.chaos_call()`,
the drift helpers, and the CLI's own `ChaosReport` output work with zero
dependency on it.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from agentic_chaos.chaos.context import ChaosSession
from agentic_chaos.models.chaos_event import ChaosEvent

if TYPE_CHECKING:
    from agenticlens.models import Workflow
    from agenticlens.profiler.step import StepHandle

#: Span attribute keys AgenticLens (>= 0.7.0) reads on structured-trace spans.
#: A span carrying them is diagnosed as an `injected_fault` and serves as
#: ground truth when measuring faulty-step attribution accuracy
#: (`agenticlens attribution-accuracy`).
CHAOS_INJECTED_KEY = "chaos.injected"
CHAOS_FAULT_TYPE_KEY = "chaos.fault_type"
CHAOS_EVENT_ID_KEY = "chaos.event_id"
CHAOS_OUTCOME_KEY = "chaos.outcome"


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


def attach_drift_report(report: dict[str, Any], workflow: "Workflow") -> None:
    """Attach a drift report (schema v1.4) onto an AgenticLens workflow-like object.

    This mirrors `attach_events()` for drift use cases, so a future
    AgenticLens-side `DriftRecommender` can inspect the same exported field
    without a hard package dependency from this repo.
    """
    # AgenticLens's Workflow model is strict about undeclared fields, so use
    # a low-level setattr to attach the additive v1.4 drift extension.
    object.__setattr__(workflow, "drift_report", report)


def span_attributes(event: ChaosEvent | Mapping[str, Any]) -> dict[str, Any]:
    """Attributes that mark an AgenticLens trace `Span` as hit by `event`.

    Accepts a `ChaosEvent` or one entry of `session.events_as_json()`.
    Merge the result into the span's `attributes`, or call `mark_span()`::

        with chaos_session(["silent_degradation"]) as session:
            with trace("support-agent") as recording:
                with recording.span("kb_search", SpanType.RETRIEVAL) as handle:
                    docs = chaos_call(search, query)
                mark_span(handle.span, session.events[-1])

    `agenticlens diagnose` then reports the span as an injected fault, and
    `agenticlens attribution-accuracy` uses it as the known faulty step.
    """
    data = event.model_dump(mode="json") if isinstance(event, ChaosEvent) else dict(event)
    fault_type = data.get("fault_type")
    if not isinstance(fault_type, str) or not fault_type:
        raise ValueError("chaos event must have a non-empty fault_type")
    attributes: dict[str, Any] = {
        CHAOS_INJECTED_KEY: True,
        CHAOS_FAULT_TYPE_KEY: fault_type,
    }
    if data.get("id"):
        attributes[CHAOS_EVENT_ID_KEY] = str(data["id"])
    if data.get("outcome"):
        attributes[CHAOS_OUTCOME_KEY] = str(data["outcome"])
    return attributes


def mark_span(span: Any, event: ChaosEvent | Mapping[str, Any]) -> None:
    """Merge `span_attributes(event)` into `span.attributes` in place.

    Duck-typed against AgenticLens's `Span` (anything with an `attributes`
    dict works), so this module still never imports AgenticLens at runtime.
    """
    span.attributes.update(span_attributes(event))
