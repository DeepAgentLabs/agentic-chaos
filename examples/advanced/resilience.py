"""Offline v0.7 example. Run: uv run python examples/advanced/resilience.py."""

import json
from contextlib import suppress

from agentic_chaos import (
    PoisonedResponseFault,
    RateLimitStormFault,
    TokenTimeoutFault,
    cascade,
    chaos_call,
    chaos_session,
    find_breaking_point,
)
from agentic_chaos.chaos.faults import ChaosFaultError, RateLimitStormError


def retrying_agent() -> str:
    for _ in range(4):
        try:
            return chaos_call(lambda: "recovered")
        except RateLimitStormError:
            pass
    raise RuntimeError("retry budget exhausted")


def containment(*, enforce: bool) -> dict[str, object]:
    """Record actual synthetic dispatches, including a deliberately bypassed control."""
    dispatches: list[str] = []
    with chaos_session([PoisonedResponseFault("policy_bypass", seed=7)]) as session:
        response = chaos_call(lambda: "safe response", step_name="tool_response")
        if not enforce and "SYNTHETIC_SECRET" in response:
            dispatches.append("synthetic://blocked-target")
    return {
        "policy_version": "synthetic-deny-v1",
        "enforced": enforce,
        "dispatches": dispatches,
        "contained": not dispatches,
        "report": session.to_report("synthetic-containment").model_dump(mode="json"),
    }


def main() -> None:
    fault = cascade(
        first=RateLimitStormFault(burst_count=2), then=TokenTimeoutFault(hang_seconds=0)
    )
    with chaos_session([fault]) as session:
        for _ in range(4):
            with suppress(ChaosFaultError):
                chaos_call(lambda: "ok", step_name="provider")
    report = session.to_report("synthetic-cascade")
    assert [e["fault_type"] for e in report.chaos_events] == [
        "rate_limit_storm",
        "rate_limit_storm",
        "token_timeout",
    ]
    result = find_breaking_point(
        retrying_agent, fault=RateLimitStormFault, param="burst_count", range=(1, 10)
    )
    assert result.breaking_point == 4
    protected, bypassed = containment(enforce=True), containment(enforce=False)
    assert protected["contained"] and not bypassed["contained"]
    print(
        json.dumps(
            {
                "breaking_point": result.breaking_point,
                "trials": result.trials,
                "cascade": report.model_dump(mode="json"),
                "containment": [protected, bypassed],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
