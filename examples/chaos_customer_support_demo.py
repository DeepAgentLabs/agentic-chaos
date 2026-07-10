"""End-to-end demo of the agentic-chaos <-> agenticlens interop loop.

Run under chaos and save a report:

    uv run agentic-chaos chaos run examples/chaos_customer_support_demo.py \\
        --inject rate_limit_storm,token_timeout,silent_degradation --save chaos_run.json

Then hand that report to AgenticLens's analysis engine:

    uv run agenticlens analyze chaos_run.json

This script can also be run directly (`python examples/chaos_customer_support_demo.py`)
-- when no CLI-managed `chaos_session()` is active, it starts one itself with
fast, demo-friendly fault parameters so `chaos_call()` isn't a no-op.
"""

import time
from typing import Any

from agenticlens import StepHandle, profile, step

from agentic_chaos.chaos import (
    RateLimitStormError,
    RateLimitStormFault,
    SilentDegradationFault,
    TokenTimeoutError,
    TokenTimeoutFault,
    chaos_call,
    chaos_session,
    get_active_session,
)


class FakeUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class FakeResponse:
    def __init__(self, prompt_tokens: int, completion_tokens: int, content: str) -> None:
        self.usage = FakeUsage(prompt_tokens, completion_tokens)
        self.content = content


def call_planner(prompt: str) -> FakeResponse:
    return FakeResponse(
        prompt_tokens=300, completion_tokens=80, content="Plan: look up the order, then answer."
    )


def call_retriever(query: str) -> list[str]:
    return [
        "Refunds are processed to the original payment method.",
        "Refunds take 5-10 business days.",
    ]


def call_final_answer(prompt: str) -> FakeResponse:
    return FakeResponse(
        prompt_tokens=500,
        completion_tokens=120,
        content="Refunds are processed to the original payment method within 5-10 business days.",
    )


def _call_with_retry(fn: Any, *args: Any, step: StepHandle, max_attempts: int) -> FakeResponse:
    for attempt in range(1, max_attempts + 1):
        try:
            return chaos_call(fn, *args, step=step, faults=["rate_limit_storm"])
        except RateLimitStormError as exc:
            print(
                f"Planner call rate-limited (attempt {attempt}/{max_attempts}); "
                f"backing off {exc.retry_after}s"
            )
            time.sleep(exc.retry_after)
    raise RuntimeError("Planner call never recovered from rate limiting")


def run_workflow() -> None:
    with profile("Chaos Demo -- Customer Support Agent"):
        # Planner: hit by a rate-limit storm. The app retries through it and
        # recovers, so this step still succeeds -- but the saved chaos_events
        # will show the failed attempts along the way.
        with step("Planner", type="planner", provider="openai", model="gpt-4o-mini") as s:
            response = _call_with_retry(
                call_planner, "What does the user need?", step=s, max_attempts=5
            )
            s.record(response)

        # Retriever: hit by a token timeout. Nothing in this demo retries it, so
        # it fails outright -- an unhandled failure ChaosImpactRecommender flags
        # as critical.
        with step("Retriever", type="retriever", chunk_count=2) as s:
            try:
                chunks = chaos_call(
                    call_retriever, "refund policy", step=s, faults=["token_timeout"]
                )
            except TokenTimeoutError:
                print("Retriever timed out under chaos -- degrading to 0 chunks, no fallback.")
                chunks = []

        # Final Response: hit by silent degradation. The call "succeeds" with
        # normal latency and token usage, but its content is corrupted -- the
        # class of failure cost/latency monitoring alone can't see.
        with step(
            "Final Response", type="final_response", provider="openai", model="gpt-4o-mini"
        ) as s:
            response = chaos_call(
                call_final_answer,
                "Answer the user's question using: " + " ".join(chunks),
                step=s,
                faults=["silent_degradation"],
            )
            s.record(response)
            print(f"Final answer returned to user: {response.content!r}")


def main() -> None:
    if get_active_session() is None:
        with chaos_session(
            [
                RateLimitStormFault(burst_count=2, retry_after=0.1),
                TokenTimeoutFault(hang_seconds=0.2),
                SilentDegradationFault(seed=7),
            ]
        ):
            run_workflow()
    else:
        run_workflow()


if __name__ == "__main__":
    main()
