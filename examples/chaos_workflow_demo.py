"""v0.8 demo: a chaos workflow, experiment lint and topology fuzzing, all offline.

Run: uv run python examples/chaos_workflow_demo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "workflows"))

from support_agent import HANDOFF, handle, ping  # noqa: E402

from agentic_chaos import (  # noqa: E402
    RateLimitStormFault,
    Scope,
    SilentDegradationFault,
    TokenTimeoutFault,
    ToolCallFailureFault,
    cascade,
)
from agentic_chaos.contracts import (  # noqa: E402
    MaxRetries,
    NoUnhandledError,
    RecoveredAfterFailure,
)
from agentic_chaos.experiments import validate_experiment  # noqa: E402
from agentic_chaos.workflows import (  # noqa: E402
    ChaosWorkflow,
    HealthCheck,
    Parallel,
    Step,
    Suspend,
    Template,
    fuzz_topology,
)

LLM = Scope(steps=["llm"])

storm = Template(
    "storm",
    lambda burst=2: [
        Step(
            "rate-limits",
            faults=[RateLimitStormFault(burst_count=burst, retry_after=0, scope=LLM)],
            contracts=[RecoveredAfterFailure(), MaxRetries(burst, step="llm")],
        ),
        HealthCheck(fn=handle, name="answers", expect_contains="Answer:"),
    ],
)

workflow = ChaosWorkflow(
    "support-resilience-suite",
    steps=[
        HealthCheck(fn=ping, query="Are you working?", name="steady-state"),
        storm.use(name="warm-up"),
        Parallel(
            Step("retriever-outage", faults=[ToolCallFailureFault(tool_name="retriever")]),
            Step("degraded-model", faults=[SilentDegradationFault(seed=7, scope=LLM)]),
            name="dependencies",
        ),
        Suspend("approve-escalation", reason="next stages are louder"),
        storm.use(name="escalate", burst=5),
        Step(
            "cascade",
            faults=[
                cascade(
                    first=RateLimitStormFault(burst_count=2, retry_after=0),
                    then=TokenTimeoutFault(hang_seconds=0.01),
                    scope=LLM,
                )
            ],
            contracts=[NoUnhandledError(), RecoveredAfterFailure()],
        ),
    ],
    scope=Scope(exclude_steps=["safety_check"]),  # explosion radius: never the guard
)

print("== chaos workflow (gate approved) ==")
report = workflow.run(handle, approve={"approve-escalation"})
for node in report.walk():
    events = len(node.report["chaos_events"]) if node.report else 0
    print(f"{node.name:<22} {node.kind:<13} {node.status:<9} events={events}")
print(f"workflow {report.status}: {len(report.chaos_events)} chaos events")

print("\n== without approval the run stops at the gate ==")
paused = workflow.run(handle)
print(f"status={paused.status} suspended_at={paused.suspended_at}")
resumed = workflow.run(handle, resume_from="approve-escalation")
print(f"resumed status={resumed.status}")

print("\n== experiment lint (nothing is executed) ==")
result = validate_experiment(
    {
        "name": "typo",
        "target": "workflows/support_agent.py:handle",
        "faults": [{"type": "rate_limt_storm"}, {"type": "token_timeout", "probability": 2}],
        "assertions": [{"max_retrys": 3}],
        "schedule": {"cron": "0 25 * * *"},
    },
    base_dir=Path(__file__).resolve().parent,
)
for issue in result.issues:
    print(f"{issue.location}: {issue.message}")

print("\n== topology fuzzing (weighted by fan-out) ==")
fuzz = fuzz_topology(
    handle,
    n=24,
    seed=11,
    scope=Scope(exclude_steps=["safety_check"]),
    # A garbled answer is a failure even when nothing raised.
    recovered=lambda answer: answer.startswith("Answer:") or answer == HANDOFF,
)
for node in fuzz.nodes:
    print(
        f"{node.node:<10} type={node.node_type:<5} weight={node.weight:g} "
        f"trials={node.trials:<2} failures={node.failures}"
    )
print(f"failing nodes: {', '.join(fuzz.failing_nodes) or 'none'}")
print("the planner node has no retry of its own: a fault there reaches the caller")
