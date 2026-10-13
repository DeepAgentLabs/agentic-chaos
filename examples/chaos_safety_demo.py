"""Offline safety preview and explicit cost-budget abort (no network calls)."""

from agentic_chaos import (
    ChaosAbortedError,
    CircuitBreaker,
    RateLimitStormFault,
    chaos_call,
    chaos_session,
)

with chaos_session([RateLimitStormFault()], dry_run=True) as preview:
    print("Preview target:", chaos_call(lambda: "unchanged", step_name="provider"))
print("Would inject:", preview.planned_events[0]["fault_type"])
print("Actual injected events:", len(preview.events))

with chaos_session([], breaker=CircuitBreaker(max_cost_usd=0.01)) as session:
    try:
        session.record_usage(
            input_tokens=10_000,
            output_tokens=0,
            input_usd_per_million=1,
            output_usd_per_million=0,
        )
    except ChaosAbortedError:
        print("Aborted at:", session.safety.abort["threshold"])
    try:
        chaos_call(lambda: print("Forbidden dispatch"))
    except ChaosAbortedError:
        print("Next instrumented dispatch: blocked")
print("In flight at abort:", session.safety.abort["in_flight_at_abort"])
