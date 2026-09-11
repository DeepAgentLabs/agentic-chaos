"""Instrumentation-overhead benchmark for `chaos_call()`.

Not part of the pytest suite (timing numbers are hardware-dependent and
would make CI flaky) -- run it directly:

    uv run python scripts/benchmark_overhead.py

Measures three per-call costs against a trivial function standing in for a
real LLM/tool call:

1. baseline       -- call the function directly, no chaos_call() involved
2. no session     -- chaos_call(fn, ...) with no active chaos_session()
                     (the "transparent outside a session" path the
                     chaos_call() docstring claims)
3. active session -- chaos_call(fn, ...) inside a chaos_session() with
                     SilentDegradationFault active. That fault is used
                     deliberately: unlike TokenTimeoutFault or
                     RateLimitStormFault it adds no artificial sleep/raise,
                     so the measured time isolates chaos_call()'s own
                     dispatch overhead (fault selection, signature()
                     introspection, event construction, score_outcome())
                     from any fault's intentionally-simulated latency.

Reports mean per-call overhead in microseconds, relative to the baseline.
"""

from __future__ import annotations

import statistics
import time

from agentic_chaos.chaos.faults import SilentDegradationFault
from agentic_chaos.chaos.inject import chaos_call
from agentic_chaos.chaos.session import chaos_session

ITERATIONS = 20_000
WARMUP = 1_000


def fake_llm_call(prompt: str) -> str:
    return f"{prompt} response"


def _time_calls(fn: object, iterations: int) -> float:
    """Return total elapsed seconds for `iterations` calls to `fn()`."""
    start = time.perf_counter()
    for _ in range(iterations):
        fn()  # type: ignore[operator]
    return time.perf_counter() - start


def _run(label: str, fn: object) -> float:
    _time_calls(fn, WARMUP)  # warm up: import caches, branch prediction, etc.
    samples = [_time_calls(fn, ITERATIONS) / ITERATIONS * 1e6 for _ in range(5)]
    mean_us = statistics.mean(samples)
    stdev_us = statistics.stdev(samples)
    print(f"{label:<28} {mean_us:8.3f} us/call  (stdev {stdev_us:.3f} us, n={ITERATIONS}x5)")
    return mean_us


def main() -> None:
    print("Python-call baseline reference (no chaos_call at all):")
    baseline_direct = _run("direct call", lambda: fake_llm_call("hello"))

    print()
    print("chaos_call() overhead:")
    baseline = _run("no active session", lambda: chaos_call(fake_llm_call, "hello"))

    with chaos_session([SilentDegradationFault(seed=0)]):
        active = _run(
            "active session (silent_degradation)",
            lambda: chaos_call(fake_llm_call, "hello"),
        )

    print()
    print("Summary (mean overhead added vs. a direct call):")
    print(f"  chaos_call(), no session:      +{baseline - baseline_direct:7.3f} us/call")
    print(f"  chaos_call(), fault active:    +{active - baseline_direct:7.3f} us/call")


if __name__ == "__main__":
    main()
