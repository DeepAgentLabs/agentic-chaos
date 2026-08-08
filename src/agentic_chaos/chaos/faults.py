import random
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from agentic_chaos.models.chaos_event import ChaosEvent


class ChaosFaultError(Exception):
    """Base class for exceptions raised by a triggered fault.

    Carries the `ChaosEvent` describing the trigger, so callers that catch and
    handle a specific fault type (as a resilient app should) can still recover
    the event for their own logging if they don't go through `chaos_call`.
    """

    def __init__(self, message: str, event: ChaosEvent) -> None:
        super().__init__(message)
        self.event = event


class TokenTimeoutError(ChaosFaultError):
    """Raised by `TokenTimeoutFault` to simulate a hung/slow completion."""


class RateLimitStormError(ChaosFaultError):
    """Raised by `RateLimitStormFault` to simulate a provider 429/backoff cascade."""

    def __init__(self, message: str, event: ChaosEvent, retry_after: float) -> None:
        super().__init__(message, event)
        self.retry_after = retry_after


@dataclass
class FaultOutcome:
    """What happened when a fault was given the chance to act on a call.

    Exactly one of `raised` or a populated `result` is meaningful for the
    caller; `event` is `None` only when the fault chose not to trigger (e.g. a
    rate-limit storm that has already exhausted its burst count).
    """

    result: Any = None
    event: ChaosEvent | None = None
    raised: BaseException | None = None
    baseline: Any = None


class BaseFault(ABC):
    """A single injectable fault type.

    Instances are stateful per chaos session (e.g. `RateLimitStormFault` counts
    how many times it has fired) and are not safe to share across concurrent
    sessions -- construct a fresh instance per `chaos_session(...)`.
    """

    name: str

    @abstractmethod
    def trigger(
        self,
        call: Callable[..., Any],
        *,
        step_id: str | None,
        step_name: str | None,
        call_args: tuple[Any, ...] = (),
        call_kwargs: dict[str, Any] | None = None,
        edge_id: str | None = None,
        from_node: str | None = None,
        to_node: str | None = None,
    ) -> FaultOutcome:
        """Decide how `call()` should be affected by this fault this time.

        Implementations call `call()` themselves (zero or one times) and
        return a `FaultOutcome` describing what happened.
        """
        raise NotImplementedError


class TokenTimeoutFault(BaseFault):
    """Simulates a hung/slow completion mid-generation.

    In "raise" mode (the default) the call never resolves for the caller --
    it hangs for `hang_seconds` and then the fault raises `TokenTimeoutError`,
    the way a client-side timeout would. In "delay" mode the real call still
    completes, just late, so you can test whether slow-but-successful calls
    degrade the user experience without erroring outright.
    """

    name = "token_timeout"

    def __init__(self, hang_seconds: float = 2.0, mode: str = "raise") -> None:
        if mode not in ("raise", "delay"):
            raise ValueError("mode must be 'raise' or 'delay'")
        self.hang_seconds = hang_seconds
        self.mode = mode

    def trigger(
        self,
        call: Callable[..., Any],
        *,
        step_id: str | None,
        step_name: str | None,
        call_args: tuple[Any, ...] = (),
        call_kwargs: dict[str, Any] | None = None,
        edge_id: str | None = None,
        from_node: str | None = None,
        to_node: str | None = None,
    ) -> FaultOutcome:
        call_kwargs = call_kwargs or {}
        time.sleep(self.hang_seconds)

        if self.mode == "delay":
            result = call(*call_args, **call_kwargs)
            event = ChaosEvent(
                fault_type=self.name,
                step_id=step_id,
                step_name=step_name,
                outcome="delayed",
                message=f"call delayed {self.hang_seconds:.1f}s before completing",
                detail={"hang_seconds": self.hang_seconds, "mode": self.mode},
            )
            return FaultOutcome(result=result, event=event)

        message = f"call hung for {self.hang_seconds:.1f}s then timed out"
        event = ChaosEvent(
            fault_type=self.name,
            step_id=step_id,
            step_name=step_name,
            outcome="errored",
            message=message,
            detail={"hang_seconds": self.hang_seconds, "mode": self.mode},
        )
        return FaultOutcome(event=event, raised=TokenTimeoutError(message, event))


class RateLimitStormFault(BaseFault):
    """Simulates a burst of provider 429s/backoff cascades.

    The first `burst_count` calls this fault sees raise `RateLimitStormError`
    with a `retry_after` hint; after that it lets calls through untouched,
    simulating a provider that recovers once its rate-limit window rolls over.
    """

    name = "rate_limit_storm"

    def __init__(self, burst_count: int = 3, retry_after: float = 1.0) -> None:
        self.burst_count = burst_count
        self.retry_after = retry_after
        self._fired = 0

    def trigger(
        self,
        call: Callable[..., Any],
        *,
        step_id: str | None,
        step_name: str | None,
        call_args: tuple[Any, ...] = (),
        call_kwargs: dict[str, Any] | None = None,
        edge_id: str | None = None,
        from_node: str | None = None,
        to_node: str | None = None,
    ) -> FaultOutcome:
        call_kwargs = call_kwargs or {}
        if self._fired >= self.burst_count:
            return FaultOutcome(result=call(*call_args, **call_kwargs))

        self._fired += 1
        message = f"429 Too Many Requests (attempt {self._fired}/{self.burst_count})"
        event = ChaosEvent(
            fault_type=self.name,
            step_id=step_id,
            step_name=step_name,
            outcome="errored",
            message=message,
            detail={
                "retry_after": self.retry_after,
                "attempt": self._fired,
                "burst_count": self.burst_count,
            },
        )
        return FaultOutcome(
            event=event,
            raised=RateLimitStormError(message, event, retry_after=self.retry_after),
        )


_GARBLE_ALPHABET = "abcdefghijklmnopqrstuvwxyz"


def garble_text(text: str, rng: random.Random | None = None) -> str:
    """Replace each run of alphabetic characters with random letters.

    Preserves whitespace, punctuation, and overall length, so downstream
    token/latency metrics look unchanged -- only the content is garbage. This
    is what makes silent degradation the hardest fault to detect from
    cost/latency monitoring alone.

    Operates on alphabetic *runs*, not whole whitespace-split tokens, so
    words with attached punctuation (`"fox,"`, `"well."`, `'"hello"'`) still
    get garbled instead of passing through untouched.
    """
    rng = rng or random.Random()

    def _replace(match: re.Match[str]) -> str:
        return "".join(rng.choice(_GARBLE_ALPHABET) for _ in match.group())

    return re.sub(r"[A-Za-z]+", _replace, text)


def mutate_text_attrs(result: Any, mutator: Callable[[str], str]) -> Any:
    """Apply `mutator` to the first text attribute found on `result`.

    Probes `.content` and `.text` on dicts and objects. Returns the (possibly
    mutated) result. Shared utility to avoid duplicating the attribute-probing
    pattern across fault implementations.
    """
    if isinstance(result, str):
        return mutator(result)

    if isinstance(result, dict):
        mutated = dict(result)
        for key in ("content", "text"):
            if isinstance(mutated.get(key), str):
                mutated[key] = mutator(mutated[key])
                return mutated
        return mutated

    for attr in ("content", "text"):
        value = getattr(result, attr, None)
        if isinstance(value, str):
            try:
                object.__setattr__(result, attr, mutator(value))
                return result
            except (AttributeError, TypeError):
                continue

    return result


def _default_degrade(result: Any, rng: random.Random) -> Any:
    """Best-effort content corruption across common LLM response shapes."""
    return mutate_text_attrs(result, lambda text: garble_text(text, rng))


class SilentDegradationFault(BaseFault):
    """Simulates same latency/token count, garbage output.

    Calls the real function to get a genuine response (so latency and token
    usage stay realistic), then corrupts its text content in place. The
    hardest fault to detect -- and the highest-value one, per the roadmap --
    because nothing in cost/latency telemetry looks wrong.

    Pass `degrade_fn` to handle response shapes this package doesn't know
    about; it receives the real result and returns the (corrupted) value that
    gets passed back to the caller.
    """

    name = "silent_degradation"

    def __init__(
        self,
        degrade_fn: Callable[[Any], Any] | None = None,
        seed: int | None = None,
    ) -> None:
        self._rng = random.Random(seed)
        self.degrade_fn = degrade_fn or (lambda result: _default_degrade(result, self._rng))

    def trigger(
        self,
        call: Callable[..., Any],
        *,
        step_id: str | None,
        step_name: str | None,
        call_args: tuple[Any, ...] = (),
        call_kwargs: dict[str, Any] | None = None,
        edge_id: str | None = None,
        from_node: str | None = None,
        to_node: str | None = None,
    ) -> FaultOutcome:
        call_kwargs = call_kwargs or {}
        result = call(*call_args, **call_kwargs)
        degraded = self.degrade_fn(result)
        event = ChaosEvent(
            fault_type=self.name,
            step_id=step_id,
            step_name=step_name,
            outcome="degraded",
            message="output silently degraded (same shape, corrupted content)",
        )
        return FaultOutcome(result=degraded, event=event, baseline=result)


FAULT_REGISTRY: dict[str, type[BaseFault]] = {
    "token_timeout": TokenTimeoutFault,
    "rate_limit_storm": RateLimitStormFault,
    "silent_degradation": SilentDegradationFault,
}


def resolve_faults(names: "str | Sequence[str | BaseFault]") -> list[BaseFault]:
    """Build fault instances from names (using each fault's defaults) or pass
    already-constructed `BaseFault` instances through unchanged.

    `names` may be a comma-separated string (as accepted from the CLI's
    `--inject` option) or a list mixing fault-name strings and instances.
    """
    entries: Sequence[str | BaseFault]
    if isinstance(names, str):
        entries = [n.strip() for n in names.split(",") if n.strip()]
    else:
        entries = names

    faults: list[BaseFault] = []
    for entry in entries:
        if isinstance(entry, BaseFault):
            faults.append(entry)
            continue
        try:
            fault_cls = FAULT_REGISTRY[entry]
        except KeyError as exc:
            known = ", ".join(sorted(FAULT_REGISTRY))
            raise ValueError(f"Unknown fault '{entry}'. Known faults: {known}") from exc
        faults.append(fault_cls())
    return faults
