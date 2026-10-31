"""v0.9 demo: resilience probes, the resilience score and its trend, all offline.

Run: uv run python examples/chaos_resilience_demo.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "workflows"))

from rich.console import Console  # noqa: E402
from support_agent import HANDOFF, handle, ping  # noqa: E402

from agentic_chaos import (  # noqa: E402
    RateLimitStormFault,
    ResilienceHistory,
    ResilienceScore,
    Scope,
    SilentDegradationFault,
    TokenTimeoutFault,
    chaos_run,
)
from agentic_chaos.cli.render import render_resilience  # noqa: E402
from agentic_chaos.probes import (  # noqa: E402
    FunctionProbe,
    LatencyProbe,
    ResponseQualityProbe,
)

console = Console(width=110)

# Defined once, reused by every run below. Pre-chaos they prove the agent was
# healthy; post-chaos they prove it came back.
probes = [
    FunctionProbe(ping, "status", name="ping"),
    ResponseQualityProbe(
        handle,
        "How do I reset my password?",
        expect_contains="Answer:",
        expect_not_contains=HANDOFF,
        name="answers",
        phases=["pre", "during", "post"],
    ),
    LatencyProbe(handle, "hello", max_ms=1000, samples=3, name="fast"),
]

LLM = Scope(steps=["llm"])


def show(label: str, score: dict[str, object] | None) -> None:
    assert score is not None
    print(f"{label}: score={score['score']} grade={score['grade']}")


# 1. An unscoped storm also hits the planner node, which has no retry of its own.
blast = chaos_run(handle, [RateLimitStormFault(burst_count=3, retry_after=0)], probes=probes)
show("unscoped storm", blast.resilience)
print(f"  escaped fault: {blast.unhandled_error and blast.unhandled_error['fault_type']}")

# 2. Scoped to the model calls the agent retries, the same storm is survivable.
with tempfile.TemporaryDirectory() as directory:
    history = ResilienceHistory(Path(directory) / "history.json", max_runs=10)
    scoped = chaos_run(
        handle,
        [RateLimitStormFault(burst_count=3, retry_after=0, scope=LLM)],
        probes=probes,
        name="support-agent",
        history=history,
    )
    show("scoped storm", scoped.resilience)

    # 3. A degraded model: the drafts still pass the probes, but without a
    #    fidelity judge the degradation itself cannot be called recovered.
    degraded = chaos_run(
        handle,
        [SilentDegradationFault(scope=LLM)],
        probes=probes,
        name="support-agent",
        history=history,
    )
    show("silent degradation", degraded.resilience)
    assert degraded.resilience is not None
    print(f"  {degraded.resilience['faults'][0]['note']}")
    trend = degraded.resilience["trend"]
    print(f"  trend: {trend['delta']:+d} from last run (was {trend['previous']})")

    # 4. Slow model calls, compared with a fault-free baseline for latency.
    baseline = chaos_run(handle, [], name="support-agent-baseline")
    slow = chaos_run(
        handle,
        [TokenTimeoutFault(hang_seconds=0.05, mode="delay", scope=LLM)],
        probes=probes,
        name="support-agent",
        baseline=baseline,
        history=history,
    )
    assert slow.resilience is not None
    print(f"  history runs kept: {len(history.entries('support-agent'))}")
    render_resilience(console, ResilienceScore.from_json(slow.resilience))
