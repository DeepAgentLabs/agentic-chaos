"""Offline support agent for the v0.8 workflow examples (no provider or network).

The planner retrieves knowledge-base articles, asks a model for a draft, and
lets a safety check approve the draft before answering. Its resilience:

- model 429s and timeouts are retried up to ``MAX_ATTEMPTS`` times
- a failed retriever degrades to answering without articles
- a draft the safety check rejects is replaced by a hand-off to a human

The safety check itself has no fallback, which is why the examples keep it
outside every fault's scope.
"""

from agentic_chaos import TopologyTracker, chaos_call, wrap_node, wrap_tool
from agentic_chaos.agents import ToolCallFailureError
from agentic_chaos.chaos import RateLimitStormError, TokenTimeoutError

MAX_ATTEMPTS = 6
QUESTION = "How do I reset my password?"
HANDOFF = "I could not verify an answer; a human agent will follow up."


def _model(prompt: str) -> str:
    """Deterministic stand-in for an LLM call."""
    return f"Answer: {prompt.rsplit('|', 1)[-1].strip()}"


def ask_model(prompt: str) -> str:
    for _ in range(MAX_ATTEMPTS):
        try:
            return chaos_call(_model, prompt, step_name="llm", chaos_provider="openai")
        except (RateLimitStormError, TokenTimeoutError):
            continue
    raise RuntimeError("model unavailable after retries")


def handle(question: str = QUESTION) -> str:
    tracker = TopologyTracker()
    retrieve = wrap_tool(
        lambda query: ["kb/reset-password"],
        tool_name="retriever",
        tracker=tracker,
        caller_node="planner",
    )
    approve = wrap_tool(
        lambda draft: draft.startswith("Answer:"),
        tool_name="safety_check",
        tracker=tracker,
        caller_node="planner",
    )

    def plan(query: str) -> str:
        try:
            articles = retrieve(query)
        except ToolCallFailureError:
            articles = []
        draft = ask_model(f"{','.join(articles)} | {query}")
        return draft if approve(draft) else HANDOFF

    tracker.record_edge("planner", "llm", target_type="agent")
    return wrap_node(plan, node_name="planner", tracker=tracker)(question)


def ping(query: str = "ping") -> str:
    return f"pong ({query})"


if __name__ == "__main__":
    print(handle())
