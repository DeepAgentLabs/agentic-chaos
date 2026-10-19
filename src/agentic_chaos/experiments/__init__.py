"""Declarative chaos experiments (v0.8): YAML/JSON/TOML definitions, lint and schedules.

```yaml
# experiments/rate-limit-recovery.yaml
name: rate-limit-recovery
target: ../my_app.py
faults:
  - type: rate_limit_storm
    burst_count: 5
assertions:
  - completes_within: 30
  - recovered_after_failure: true
schedule:
  cron: "0 2 * * *"
```

```python
from agentic_chaos.experiments import load_experiment, validate_experiment

result = validate_experiment("experiments/rate-limit-recovery.yaml")  # never runs the target
report = load_experiment("experiments/rate-limit-recovery.yaml").run()
```
"""

from agentic_chaos.experiments.cron import CronSchedule, parse_cron
from agentic_chaos.experiments.loader import (
    SUFFIXES,
    ValidationResult,
    load_experiment,
    read_document,
    validate_experiment,
)
from agentic_chaos.experiments.schema import (
    EXPERIMENT_VERSION,
    Experiment,
    ExperimentError,
    ExperimentIssue,
    LazyTarget,
    compile_document,
)

__all__ = [
    "EXPERIMENT_VERSION",
    "SUFFIXES",
    "CronSchedule",
    "Experiment",
    "ExperimentError",
    "ExperimentIssue",
    "LazyTarget",
    "ValidationResult",
    "compile_document",
    "load_experiment",
    "parse_cron",
    "read_document",
    "validate_experiment",
]
