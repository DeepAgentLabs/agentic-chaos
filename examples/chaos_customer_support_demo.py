"""Standalone demo -- no other library required.

Run under chaos and save a report:

    uv run agentic-chaos chaos run examples/chaos_customer_support_demo.py \\
        --inject rate_limit_storm,token_timeout,silent_degradation --save chaos_run.json

This script never imports agenticlens; `agentic_chaos` works against plain
Python callables. If you *also* have agenticlens installed and want its
step()/profile() instrumentation and cost/latency reporting merged with chaos
events into one file, see `chaos_with_agenticlens_demo.py`.

Can also be run directly (`python examples/chaos_customer_support_demo.py`)
-- when no CLI-managed `chaos_session()` is active, it starts one itself with
fast, demo-friendly fault parameters so `chaos_call()` isn't a no-op.
"""

import time
from collections.abc import Callable
from typing import Any

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


def call_planner(prompt: str) -> str:
    return "Plan: look up the order, then answer."


def call_retriever(query: str) -> list[str]:
    return [
        "Refunds are processed to the original payment method.",
        "Refunds take 5-10 business days.",
    ]


def call_final_answer(prompt: str) -> str:
    return "Refunds are processed to the original payment method within 5-10 business days."


def _call_with_retry(
    fn: Callable[..., str], *args: Any, step_id: str, step_name: str, max_attempts: int
) -> str:
    for attempt in range(1, max_attempts + 1):
        try:
            return chaos_call(
                fn,
                *args,
                step_id=step_id,
                step_name=step_name,
                faults=["rate_limit_storm"],
            )
        except RateLimitStormError as exc:
            print(
                f"Planner call rate-limited (attempt {attempt}/{max_attempts}); "
                f"backing off {exc.retry_after}s"
            )
            time.sleep(exc.retry_after)
    raise RuntimeError("Planner call never recovered from rate limiting")


def run_workflow() -> None:
    # Planner: hit by a rate-limit storm. We retry through it and recover, so
    # the call still succeeds -- but the saved chaos_events show the failed
    # attempts along the way.
    plan = _call_with_retry(
        call_planner,
        "What does the user need?",
        step_id="planner",
        step_name="Planner",
        max_attempts=5,
    )
    print(f"Plan: {plan}")

    # Retriever: hit by a token timeout. Nothing here retries it, so it fails
    # outright -- an unhandled failure a resilience report should flag.
    try:
        chunks = chaos_call(
            call_retriever,
            "refund policy",
            step_id="retriever",
            step_name="Retriever",
            faults=["token_timeout"],
        )
    except TokenTimeoutError:
        print("Retriever timed out under chaos -- degrading to 0 chunks, no fallback.")
        chunks = []

    # Final Response: hit by silent degradation. The call "succeeds" -- but
    # its content is corrupted, the class of failure cost/latency monitoring
    # alone can't see.
    answer = chaos_call(
        call_final_answer,
        "Answer the user's question using: " + " ".join(chunks),
        step_id="final_response",
        step_name="Final Response",
        faults=["silent_degradation"],
    )
    print(f"Final answer returned to user: {answer!r}")


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
