"""Chaos workflows (v0.8): multi-stage campaigns, gates and topology fuzzing.

```python
from agentic_chaos.workflows import ChaosWorkflow, HealthCheck, Parallel, Step, Suspend

workflow = ChaosWorkflow("resilience-suite", steps=[
    Step("warm-up", faults=[RateLimitStormFault(burst_count=2)]),
    HealthCheck(fn=my_agent, query="Are you working?"),
    Parallel(Step("tools", faults=["tool_failure"]), Step("memory", faults=["memory_corruption"])),
    Suspend("approve-full-blast", reason="next stage hits the shared staging provider"),
    Step("full-blast", faults=[cascade(first=..., then=...)]),
])
report = workflow.run(my_app)
```
"""

from agentic_chaos.chaos.scope import Scope
from agentic_chaos.workflows.engine import ChaosWorkflow
from agentic_chaos.workflows.nodes import (
    HealthCheck,
    Node,
    Parallel,
    Step,
    Suspend,
    Template,
    TemplateUse,
)
from agentic_chaos.workflows.report import NodeResult, WorkflowReport
from agentic_chaos.workflows.targets import ScriptExitError, check_target, resolve_target

__all__ = [
    "ChaosWorkflow",
    "HealthCheck",
    "Node",
    "NodeResult",
    "Parallel",
    "Scope",
    "ScriptExitError",
    "Step",
    "Suspend",
    "Template",
    "TemplateUse",
    "WorkflowReport",
    "check_target",
    "resolve_target",
]
