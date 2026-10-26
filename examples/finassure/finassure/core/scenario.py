"""Chaos scenario definition and loader for FinAssure."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from agentic_chaos import (
    HandoffCorruptionFault,
    InfiniteLoopFault,
    MemoryCorruptionFault,
    RateLimitStormFault,
    SilentDegradationFault,
    ToolCallFailureFault,
)

FAULT_TYPES = {
    "none",
    "clean",
    "tool_failure",
    "tool_call_failure",
    "silent_degradation",
    "handoff_corruption",
    "infinite_loop",
    "rate_limit_storm",
    "memory_corruption",
}


class ChaosScenario(BaseModel):
    id: str
    name: str
    pack: str
    fault_type: str  # "tool_failure", "silent_degradation", "handoff_corruption", "none", etc.
    target: str
    params: dict[str, Any] = Field(default_factory=dict)
    hypothesis: str
    runs_per_case: int = 1
    unsafe_outcomes: list[str] = Field(default_factory=list)

    @field_validator("fault_type")
    @classmethod
    def _known_fault_type(cls, value: str) -> str:
        if value not in FAULT_TYPES:
            raise ValueError(f"Unknown fault_type {value!r}; expected one of {sorted(FAULT_TYPES)}")
        return value

    def instantiate_faults(self) -> list[Any]:
        """Convert scenario specifications into agentic-chaos Fault objects."""
        if self.fault_type in ("none", "clean"):
            return []

        if self.fault_type in ("tool_failure", "tool_call_failure"):
            mode = self.params.get("mode", "error")
            tool_name = self.params.get("tool_name", "bureau_lookup")
            timeout_sec = float(self.params.get("timeout_seconds", 0.2))
            return [
                ToolCallFailureFault(
                    tool_name=tool_name,
                    mode=mode,
                    timeout_seconds=timeout_sec,
                    error_message=f"Simulated {mode} fault on {tool_name}",
                )
            ]

        if self.fault_type == "silent_degradation":
            corruption = self.params.get("corruption", "halve")
            if corruption == "halve":

                def degrade_fn(x):
                    return x / 2.0 if isinstance(x, int | float) else x
            elif corruption == "double":

                def degrade_fn(x):
                    return x * 2.0 if isinstance(x, int | float) else x
            elif corruption == "drop_digit":

                def degrade_fn(x):
                    return x / 10.0 if isinstance(x, int | float) else x
            elif corruption == "alter_text":

                def degrade_fn(x):
                    # Swap the first two letters of the last word: a plausible typo.
                    if not isinstance(x, str) or " " not in x:
                        return x
                    head, last = x.rsplit(" ", 1)
                    return f"{head} {last[1::-1]}{last[2:]}" if len(last) > 1 else x
            else:

                def degrade_fn(x):
                    return x * 0.5 if isinstance(x, int | float) else x

            return [SilentDegradationFault(degrade_fn=degrade_fn)]

        if self.fault_type == "handoff_corruption":
            from_node = self.params.get("from_node", "doc_extraction_agent")
            to_node = self.params.get("to_node", "bureau_agent")
            mode = self.params.get("mode", "corrupt")
            return [
                HandoffCorruptionFault(
                    from_node=from_node,
                    to_node=to_node,
                    mode=mode,
                )
            ]

        if self.fault_type == "infinite_loop":
            force_turns = int(self.params.get("force_turns", 5))
            return [InfiniteLoopFault(force_turns=force_turns)]

        if self.fault_type == "rate_limit_storm":
            burst = int(self.params.get("burst_count", 3))
            retry_after = float(self.params.get("retry_after", 1.0))
            return [RateLimitStormFault(burst_count=burst, retry_after=retry_after)]

        if self.fault_type == "memory_corruption":
            mode = self.params.get("mode", "garble")
            rate = float(self.params.get("rate", 0.3))
            return [MemoryCorruptionFault(mode=mode, rate=rate)]

        raise ValueError(f"Unsupported fault_type {self.fault_type!r}")


def load_scenarios_from_yaml(yaml_path: Path | str) -> list[ChaosScenario]:
    """Parse scenarios from a YAML file."""
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    raw_list = data.get("scenarios", [])
    return [ChaosScenario.model_validate(item) for item in raw_list]
