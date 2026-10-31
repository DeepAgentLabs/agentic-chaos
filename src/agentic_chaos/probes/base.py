"""Probe protocol, results and the phase vocabulary.

A probe is a reusable steady-state check, separate from faults. It runs in one
or more phases of a chaos run:

- ``pre`` -- before any fault is active; establishes that the system was
  healthy to begin with, so a later failure can be blamed on the chaos
- ``during`` -- inside the chaos session after the target ran, with every fault
  still active; probe calls that go through ``chaos_call`` can be hit too
- ``post`` -- after the session closed; shows whether the system returned to
  steady state once the chaos stopped

Contracts (v0.6) judge what happened *during* a run from its report. Probes
call the live system and judge whether it *recovered*.
"""

import math
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Literal

Phase = Literal["pre", "during", "post"]
ProbeStatus = Literal["passed", "failed"]

PHASES: tuple[Phase, ...] = ("pre", "during", "post")
DEFAULT_PHASES: tuple[Phase, ...] = ("pre", "post")

_OUTPUT_LIMIT = 500


@dataclass(frozen=True)
class ProbeResult:
    """One probe evaluation in one phase."""

    probe: str
    kind: str
    phase: Phase
    status: ProbeStatus
    message: str
    attempts: int = 1
    duration_ms: float = 0.0
    weight: float = 1.0
    started_at: str | None = None
    step: str | None = None
    observed: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def as_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "probe": self.probe,
            "kind": self.kind,
            "phase": self.phase,
            "status": self.status,
            "message": self.message,
            "attempts": self.attempts,
            "duration_ms": self.duration_ms,
            "weight": self.weight,
            "started_at": self.started_at,
            "observed": self.observed,
        }
        if self.step is not None:
            data["step"] = self.step
        return data


class ProbeError(Exception):
    """Raised inside `Probe.evaluate()` to fail the probe with a clear message."""


def short(value: Any) -> str:
    """A bounded repr for recording outputs in probe results."""
    try:
        text = repr(value)
    except Exception:  # pragma: no cover - defensive
        text = f"<unreprable {type(value).__name__}>"
    return text if len(text) <= _OUTPUT_LIMIT else text[: _OUTPUT_LIMIT - 3] + "..."


def normalize_phases(phases: str | Iterable[str]) -> tuple[Phase, ...]:
    """Validate phases (a name or names, in any order) and return them in run order."""
    names = [phases] if isinstance(phases, str) else list(phases)
    unknown = sorted({name for name in names if name not in PHASES}, key=str)
    if unknown:
        raise ValueError(f"unknown probe phase(s) {unknown}; use 'pre', 'during' or 'post'")
    if not names:
        raise ValueError("a probe needs at least one phase")
    return tuple(phase for phase in PHASES if phase in names)


class Probe(ABC):
    """A reusable steady-state check run before, during and/or after chaos.

    Subclasses implement `evaluate()`, which returns a message and observed
    values when the system is healthy and raises (`ProbeError` or anything
    else) when it is not. `run()` adds retries, timing and the result record;
    it never raises for an unhealthy system.

    `weight` scales the probe's share of the resilience score's probe
    component. `retries` re-evaluates a failing probe `retry_delay_seconds`
    apart, for systems that need a moment to settle after chaos stops.
    """

    kind: ClassVar[str] = "probe"

    def __init__(
        self,
        *,
        name: str | None = None,
        phases: str | Iterable[str] = DEFAULT_PHASES,
        retries: int = 0,
        retry_delay_seconds: float = 0.0,
        weight: float = 1.0,
    ) -> None:
        if name is not None and (not isinstance(name, str) or not name.strip()):
            raise ValueError("probe name must be a non-empty string")
        if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
            raise ValueError("retries must be a non-negative integer")
        _check_number("retry_delay_seconds", retry_delay_seconds)
        _check_number("weight", weight)
        if weight == 0:
            raise ValueError("weight must be greater than 0")
        self.name = name.strip() if name is not None else self.kind
        self.phases = normalize_phases(phases)
        self.retries = retries
        self.retry_delay_seconds = float(retry_delay_seconds)
        self.weight = float(weight)

    @abstractmethod
    def evaluate(self) -> tuple[str, dict[str, Any]]:
        """Check the system once; return (message, observed) or raise when unhealthy."""
        raise NotImplementedError

    def runs_in(self, phase: Phase) -> bool:
        return phase in self.phases

    def parameters(self) -> dict[str, Any]:
        """JSON-safe description of this probe's configuration."""
        return {"phases": list(self.phases)}

    def run(self, phase: Phase, *, step: str | None = None) -> ProbeResult:
        """Evaluate with retries and return a result; never raises for a failing check."""
        started_at = datetime.now(timezone.utc).isoformat()
        clock = time.monotonic()
        attempts = 0
        while True:
            attempts += 1
            try:
                message, observed = self.evaluate()
                status: ProbeStatus = "passed"
            except Exception as exc:
                message = str(exc) if isinstance(exc, ProbeError) else _describe(exc)
                observed = dict(getattr(exc, "observed", {}) or {})
                status = "failed"
            if status == "passed" or attempts > self.retries:
                break
            if self.retry_delay_seconds:
                time.sleep(self.retry_delay_seconds)
        return ProbeResult(
            probe=self.name,
            kind=self.kind,
            phase=phase,
            status=status,
            message=message,
            attempts=attempts,
            duration_ms=(time.monotonic() - clock) * 1000,
            weight=self.weight,
            started_at=started_at,
            step=step,
            observed=observed,
        )

    def __repr__(self) -> str:
        args = ", ".join(f"{key}={value!r}" for key, value in self.parameters().items())
        return f"{type(self).__name__}(name={self.name!r}, {args})"


def failure(message: str, **observed: Any) -> ProbeError:
    """A `ProbeError` that also records what was observed."""
    error = ProbeError(message)
    error.observed = observed  # type: ignore[attr-defined]
    return error


def _describe(exc: BaseException) -> str:
    return f"raised {type(exc).__name__}: {exc}"


def _check_number(name: str, value: Any) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{name} must be a finite number >= 0")
