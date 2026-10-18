"""Explicit-input scenario estimates, independent of provider pricing and execution."""

import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FailureEstimate:
    fault: str
    retries: int
    calls: int
    baseline_usd: float
    extra_usd: float
    total_usd: float
    assumption: str = "each retry is billed as one full call; no target code is executed"

    def as_json(self) -> dict[str, str | int | float]:
        return asdict(self)


def estimate_failure(
    *, fault: str, retries: int, calls: int = 1, cost_per_call_usd: float
) -> FailureEstimate:
    """Upper-bound retry scenario using a caller-supplied constant call cost."""
    from agentic_chaos.chaos.faults import FAULT_REGISTRY

    if fault not in FAULT_REGISTRY:
        raise ValueError(f"Unknown fault: {fault}")
    for name, value, minimum in (("retries", retries, 0), ("calls", calls, 1)):
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    if not math.isfinite(cost_per_call_usd) or cost_per_call_usd < 0:
        raise ValueError("cost_per_call_usd must be finite and non-negative")
    baseline = calls * cost_per_call_usd
    extra = baseline * retries
    if not math.isfinite(baseline + extra):
        raise ValueError("estimated cost exceeds finite range")
    return FailureEstimate(fault, retries, calls, baseline, extra, baseline + extra)
