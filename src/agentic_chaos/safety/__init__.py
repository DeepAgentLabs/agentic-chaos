"""Session-scoped safety limits; no provider prices or cancellation guarantees inferred."""

import math
import time
from collections import deque
from threading import RLock
from typing import Any


class ChaosAbortedError(RuntimeError):
    """Safety limit reached. Further instrumented dispatches are rejected."""


class CircuitBreaker:
    """Immutable configuration copied into fresh state for each session.

    Failure rate counts completed wrapped operations (exceptions or errored faults),
    over the last ``window_size`` completions after ``min_calls`` samples.
    Cost is explicitly recorded, never estimated from unknown provider pricing.
    """

    def __init__(
        self,
        *,
        max_cost_usd: float | None = None,
        max_failure_rate: float | None = None,
        window_size: int = 20,
        min_calls: int = 1,
        max_duration_seconds: float | None = None,
        max_injections: int | None = None,
    ) -> None:
        for name, value in (
            ("max_cost_usd", max_cost_usd),
            ("max_duration_seconds", max_duration_seconds),
        ):
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value <= 0
            ):
                raise ValueError(f"{name} must be finite and positive")
        if max_failure_rate is not None and (
            isinstance(max_failure_rate, bool)
            or not math.isfinite(max_failure_rate)
            or not 0 <= max_failure_rate <= 1
        ):
            raise ValueError("max_failure_rate must be between 0 and 1")
        for name, value in (
            ("window_size", window_size),
            ("min_calls", min_calls),
            ("max_injections", max_injections),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 1
            ):
                raise ValueError(f"{name} must be a positive integer")
        if min_calls > window_size:
            raise ValueError("min_calls must not exceed window_size")
        self.max_cost_usd = max_cost_usd
        self.max_failure_rate = max_failure_rate
        self.window_size = window_size
        self.min_calls = min_calls
        self.max_duration_seconds = max_duration_seconds
        self.max_injections = max_injections


class SafetyState:
    """Shared, locked state for a session, including async worker contexts."""

    def __init__(self, breaker: CircuitBreaker | None) -> None:
        self.breaker = breaker
        self.lock = RLock()
        self.started = time.monotonic()
        self.cost = 0.0
        self.failures: deque[bool] = deque(maxlen=breaker.window_size if breaker else 20)
        self.injections = 0
        self.in_flight = 0
        self.abort: dict[str, Any] | None = None

    def _abort(self, threshold: str, limit: float, observed: float) -> None:
        if self.abort is None:
            self.abort = {
                "threshold": threshold,
                "limit": limit,
                "observed": observed,
                "in_flight_at_abort": self.in_flight,
            }
        raise ChaosAbortedError(f"Chaos aborted: {self.abort['threshold']}")

    def check(self) -> None:
        with self.lock:
            if self.abort is not None:
                raise ChaosAbortedError(f"Chaos aborted: {self.abort['threshold']}")
            b = self.breaker
            if b and b.max_duration_seconds is not None:
                elapsed = time.monotonic() - self.started
                if elapsed >= b.max_duration_seconds:
                    self._abort("max_duration_seconds", b.max_duration_seconds, elapsed)

    def begin(self) -> None:
        with self.lock:
            self.check()
            self.in_flight += 1

    def inject(self) -> None:
        with self.lock:
            self.check()
            b = self.breaker
            if b and b.max_injections is not None and self.injections >= b.max_injections:
                self._abort("max_injections", b.max_injections, self.injections)
            self.injections += 1

    def finish(self, failed: bool) -> None:
        with self.lock:
            self.in_flight -= 1
            self.failures.append(failed)
            b = self.breaker
            if self.abort is not None:
                return
            self.check()
            if b and b.max_failure_rate is not None and len(self.failures) >= b.min_calls:
                rate = sum(self.failures) / len(self.failures)
                if rate > b.max_failure_rate:
                    self._abort("max_failure_rate", b.max_failure_rate, rate)

    def record_cost(self, cost_usd: float) -> None:
        if isinstance(cost_usd, bool) or not math.isfinite(cost_usd) or cost_usd < 0:
            raise ValueError("cost_usd must be finite and non-negative")
        with self.lock:
            self.check()
            total = self.cost + cost_usd
            if not math.isfinite(total):
                raise ValueError("cumulative cost must be finite")
            self.cost = total
            b = self.breaker
            if b and b.max_cost_usd is not None and self.cost >= b.max_cost_usd:
                self._abort("max_cost_usd", b.max_cost_usd, self.cost)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "aborted": self.abort is not None,
                "abort_reason": self.abort,
                "cost_usd": self.cost,
                "injections": self.injections,
                "in_flight": self.in_flight,
            }
