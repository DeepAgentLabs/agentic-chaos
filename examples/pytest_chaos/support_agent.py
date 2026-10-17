"""A tiny offline support agent instrumented with chaos_call() / wrap_node().

Outside a chaos session every chaos_call() is a plain call, so this module is
production code as far as the tests that import it are concerned.
"""

from agentic_chaos import TopologyTracker, chaos_call, wrap_node
from agentic_chaos.chaos.faults import RateLimitStormError


def call_llm(prompt: str) -> str:
    return f"Your order ships tomorrow. ({prompt})"


def answer(question: str, *, attempts: int = 4) -> str:
    """Retry rate-limited LLM calls with a bounded budget."""
    for _ in range(attempts):
        try:
            return chaos_call(call_llm, question, step_name="llm", faults=["rate_limit_storm"])
        except RateLimitStormError:
            continue
    return "Sorry, please try again in a minute."  # graceful fallback


def reviewed_answer(question: str, tracker: TopologyTracker) -> str:
    """Router -> Drafter -> Reviewer; every node is expected to run."""
    draft = wrap_node(answer, node_name="Drafter", tracker=tracker, caller_node="Router", faults=[])
    review = wrap_node(
        lambda text: text.strip(),
        node_name="Reviewer",
        tracker=tracker,
        caller_node="Drafter",
        faults=[],
    )
    return review(draft(question))
