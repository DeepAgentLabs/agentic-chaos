"""Advanced fault options not shown in the other examples.

`chaos_customer_support_demo.py` covers the default behavior of all three
faults. This one covers two knobs that only otherwise show up in the tests:

- `TokenTimeoutFault(mode="delay")` -- the call still succeeds, just late,
  instead of raising. Useful for testing whether a slow-but-successful call
  degrades UX (e.g. blows past a UI spinner timeout) even when nothing
  actually errors.
- `SilentDegradationFault(degrade_fn=...)` -- swap in your own corruption
  logic instead of the built-in text garbler. Here it simulates a narrower,
  more realistic bug: a PII-redaction step that over-redacts and eats real
  content, rather than wholesale noise.

Run directly:

    uv run python examples/chaos_advanced_faults_demo.py
"""

import re
import time
from typing import Any

from agentic_chaos.chaos import SilentDegradationFault, TokenTimeoutFault, chaos_call, chaos_session


def call_llm(prompt: str) -> str:
    return "Your refund of $42.50 was processed successfully."


def over_redact(result: Any) -> Any:
    """A custom degrade_fn: instead of garbling all text like the default
    degrader, only mangle anything that looks like a dollar amount --
    simulating a specific, narrower class of bug (a broken redaction step)
    rather than generic noise."""
    if isinstance(result, str):
        return re.sub(r"\$[\d,.]+", "[REDACTED]", result)
    return result


def demo_delay_mode() -> None:
    print("--- TokenTimeoutFault(mode='delay') ---")
    with chaos_session([TokenTimeoutFault(hang_seconds=0.3, mode="delay")]) as session:
        start = time.perf_counter()
        result = chaos_call(call_llm, "What's my refund status?", faults=["token_timeout"])
        elapsed = time.perf_counter() - start

    print(f"Call succeeded ({elapsed:.2f}s late): {result!r}")
    print(f"Recorded outcome: {session.events[0].outcome!r}")  # "delayed", not "errored"


def demo_custom_degrade_fn() -> None:
    print("\n--- SilentDegradationFault(degrade_fn=...) ---")
    with chaos_session([SilentDegradationFault(degrade_fn=over_redact)]) as session:
        result = chaos_call(call_llm, "What's my refund status?", faults=["silent_degradation"])

    print(f"Degraded result: {result!r}")
    print(f"Recorded outcome: {session.events[0].outcome!r}")


if __name__ == "__main__":
    demo_delay_mode()
    demo_custom_degrade_fn()
