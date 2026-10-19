"""Offline chaos contracts demo (agentic-chaos 0.6).

Runs a small support agent under a rate-limit storm three ways and checks the
same contracts each time:

1. a resilient agent that retries with a bounded budget -- passes
2. a fragile agent with too small a retry budget -- fails
3. a pipeline that silently skips its reviewer under chaos -- caught by
   FullTopologyTraversal against a dry-run baseline

Run: uv run python examples/chaos_contracts_demo.py
"""

from agentic_chaos import (
    RateLimitStormFault,
    TopologyTracker,
    chaos_call,
    chaos_session,
    wrap_node,
)
from agentic_chaos.chaos.faults import RateLimitStormError
from agentic_chaos.contracts import (
    CompletesWithin,
    FullTopologyTraversal,
    MaxCostImpact,
    MaxRetries,
    NoRetryStorm,
    NoUnhandledError,
    RecoveredAfterFailure,
    check_contracts,
)


def call_llm(question: str) -> str:
    return f"answer to {question!r}"


def support_agent(question: str, *, attempts: int) -> str:
    for _ in range(attempts):
        try:
            return chaos_call(call_llm, question, step_name="llm")
        except RateLimitStormError:
            continue
    raise RuntimeError(f"gave up after {attempts} attempts")


def run(agent, *, dry_run=False):
    """Run `agent` under a 3x rate-limit storm and return its ChaosReport."""
    error = None
    with chaos_session([RateLimitStormFault(burst_count=3)], dry_run=dry_run) as session:
        try:
            agent()
        except Exception as exc:  # recorded as unhandled_error, checked by contracts
            error = exc
    return session.to_report(getattr(agent, "__name__", "agent"), error=error)


CONTRACTS = [
    NoUnhandledError(),
    RecoveredAfterFailure(),
    MaxRetries(3),
    NoRetryStorm(5, window_seconds=60),
    CompletesWithin(5),
]


def resilient():
    support_agent("Where is my order?", attempts=5)


def fragile():
    support_agent("Where is my order?", attempts=2)


def review_pipeline(*, skip_review_on_error: bool):
    tracker = TopologyTracker(auto_activate=False)
    draft = wrap_node(
        lambda q: support_agent(q, attempts=5),
        node_name="Drafter",
        tracker=tracker,
        caller_node="Router",
        faults=[],
    )
    review = wrap_node(
        lambda text: text.upper(),
        node_name="Reviewer",
        tracker=tracker,
        caller_node="Drafter",
        faults=[],
    )

    def pipeline():
        session_events_before = len(_current_events())
        answer = draft("refund status")
        if not (skip_review_on_error and len(_current_events()) > session_events_before):
            review(answer)

    return tracker, pipeline


def _current_events():
    from agentic_chaos.chaos.context import get_active_session

    session = get_active_session()
    return session.events if session is not None else []


def run_pipeline(*, dry_run: bool):
    tracker, pipeline = review_pipeline(skip_review_on_error=True)
    report = run(pipeline, dry_run=dry_run)
    return report.model_copy(update={"agent_topology": tracker.topology.as_json()})


def main() -> None:
    for agent in (resilient, fragile):
        print(check_contracts(run(agent), CONTRACTS).summary())
        print()

    baseline = run_pipeline(dry_run=True)  # same selection, nothing injected
    chaos = run_pipeline(dry_run=False)
    traversal = check_contracts(
        chaos,
        [FullTopologyTraversal(), MaxCostImpact(4, metric="calls")],
        baseline=baseline,
    )
    print(traversal.summary())


if __name__ == "__main__":
    main()
