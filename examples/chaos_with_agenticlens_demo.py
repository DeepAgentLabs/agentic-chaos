"""Optional demo: merging chaos events into an AgenticLens workflow.json.

Requires both packages:

    pip install agentic-chaos[agenticlens]

Unlike `chaos_customer_support_demo.py` (which needs nothing but
agentic-chaos), this script wraps AgenticLens's `profile()`/`step()`
instrumentation, correlates each chaos event to the step it hit via
`agentic_chaos.integrations.agenticlens.step_kwargs()`, and merges everything
into a single `Workflow` via `attach_events()` -- so one `agenticlens analyze`
sees cost/latency data and chaos impact together.

Run directly (this writes its own merged report, independent of whatever
`agentic-chaos chaos run --save` would produce):

    uv run python examples/chaos_with_agenticlens_demo.py
    uv run agenticlens analyze /tmp/chaos_and_cost_report.json
"""

from agenticlens import profile, step
from agenticlens.exporters import JSONExporter
from agenticlens.models import Workflow

from agentic_chaos.chaos import (
    TokenTimeoutError,
    TokenTimeoutFault,
    chaos_call,
    chaos_session,
)
from agentic_chaos.integrations.agenticlens import attach_events, step_kwargs


class Usage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class Response:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.usage = Usage(prompt_tokens, completion_tokens)


def call_planner(prompt: str) -> Response:
    return Response(prompt_tokens=300, completion_tokens=80)


def call_retriever(query: str) -> list[str]:
    return ["Refunds are processed to the original payment method."]


def run_workflow() -> Workflow:
    with profile("Chaos + AgenticLens Demo") as workflow:
        with step("Planner", type="planner", provider="openai", model="gpt-4o-mini") as s:
            # No fault targets this step -- chaos_call() is transparent when
            # `faults=[]` matches nothing, same as calling call_planner directly.
            response = chaos_call(call_planner, "plan the response", faults=[], **step_kwargs(s))
            s.record(response)

        with step("Retriever", type="retriever", chunk_count=1) as s:
            try:
                chaos_call(
                    call_retriever, "refund policy", faults=["token_timeout"], **step_kwargs(s)
                )
            except TokenTimeoutError:
                print("Retriever timed out under chaos.")

    return workflow


def main() -> None:
    with chaos_session([TokenTimeoutFault(hang_seconds=0.2)]) as session:
        workflow = run_workflow()
        attach_events(session, workflow)

    out = "/tmp/chaos_and_cost_report.json"
    JSONExporter().export(workflow, out)
    print(f"Saved merged workflow.json (cost/latency + chaos_events) to {out}")


if __name__ == "__main__":
    main()
