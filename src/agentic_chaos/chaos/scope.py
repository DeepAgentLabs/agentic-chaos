"""Explosion-radius control: limit where a fault may fire.

A `Scope` is a pure, non-mutating predicate over the call-site labels
`chaos_call()` already receives (`step_name`) plus an optional provider label
(`chaos_provider`, set automatically by the provider patches). It is checked
before probability sampling, so out-of-scope calls never consume a fault's
random stream, burst count or preview state, and never appear in dry-run plans.

Include lists fail closed: a call with no step or provider label is outside a
scope that names steps or providers. Exclusions always win over inclusions.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


def _names(label: str, values: Iterable[str] | None) -> frozenset[str] | None:
    if values is None:
        return None
    if isinstance(values, str):
        raise ValueError(f"{label} must be a list of names, not a single string")
    names = frozenset(values)
    if not all(isinstance(name, str) and name.strip() for name in names):
        raise ValueError(f"{label} must contain non-empty strings")
    if not names:
        raise ValueError(f"{label} must not be empty; omit it to allow every name")
    return names


@dataclass(frozen=True)
class Scope:
    """Where a fault is allowed to fire.

    ```python
    RateLimitStormFault(
        burst_count=3,
        scope=Scope(steps=["retriever", "planner"], providers=["openai"],
                    exclude_steps=["safety_check"]),
    )
    ```

    - `steps`: only calls whose `step_name` is listed (tool and node wrappers
      use the tool/node name as `step_name`).
    - `providers`: only calls labelled with one of these providers.
    - `exclude_steps` / `exclude_providers`: never these, even when included.
    """

    steps: frozenset[str] | None = None
    providers: frozenset[str] | None = None
    exclude_steps: frozenset[str] = field(default_factory=frozenset)
    exclude_providers: frozenset[str] = field(default_factory=frozenset)

    def __init__(
        self,
        *,
        steps: Iterable[str] | None = None,
        providers: Iterable[str] | None = None,
        exclude_steps: Iterable[str] | None = None,
        exclude_providers: Iterable[str] | None = None,
    ) -> None:
        object.__setattr__(self, "steps", _names("steps", steps))
        object.__setattr__(self, "providers", _names("providers", providers))
        object.__setattr__(
            self, "exclude_steps", _names("exclude_steps", exclude_steps) or frozenset()
        )
        object.__setattr__(
            self,
            "exclude_providers",
            _names("exclude_providers", exclude_providers) or frozenset(),
        )
        if self.steps is not None and self.steps <= self.exclude_steps:
            raise ValueError("every included step is also excluded; the scope matches nothing")
        if self.providers is not None and self.providers <= self.exclude_providers:
            raise ValueError("every included provider is also excluded; the scope matches nothing")

    def allows(self, *, step_name: str | None = None, provider: str | None = None) -> bool:
        """True when a call with these labels is inside the scope."""
        if step_name is not None and step_name in self.exclude_steps:
            return False
        if provider is not None and provider in self.exclude_providers:
            return False
        if self.steps is not None and step_name not in self.steps:
            return False
        return self.providers is None or provider in self.providers

    def intersect(self, other: "Scope | None") -> "Scope":
        """A scope allowing only calls both scopes allow."""
        if other is None:
            return self
        return Scope(
            steps=_both(self.steps, other.steps),
            providers=_both(self.providers, other.providers),
            exclude_steps=self.exclude_steps | other.exclude_steps or None,
            exclude_providers=self.exclude_providers | other.exclude_providers or None,
        )

    def as_json(self) -> dict[str, Any]:
        """Sorted, JSON-ready description recorded in reports and plans."""
        data: dict[str, Any] = {}
        if self.steps is not None:
            data["steps"] = sorted(self.steps)
        if self.providers is not None:
            data["providers"] = sorted(self.providers)
        if self.exclude_steps:
            data["exclude_steps"] = sorted(self.exclude_steps)
        if self.exclude_providers:
            data["exclude_providers"] = sorted(self.exclude_providers)
        return data

    @classmethod
    def from_json(cls, data: Any) -> "Scope":
        """Build a scope from a mapping such as a YAML/TOML `scope:` table."""
        if isinstance(data, Scope):
            return data
        if not isinstance(data, dict):
            raise ValueError("scope must be a mapping")
        allowed = {"steps", "providers", "exclude_steps", "exclude_providers"}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(
                f"unknown scope field(s) {', '.join(sorted(unknown))}; "
                f"allowed: {', '.join(sorted(allowed))}"
            )
        for key, value in data.items():
            if not isinstance(value, list):
                raise ValueError(f"scope {key} must be a list of names")
        return cls(**data)

    def __repr__(self) -> str:
        parts = ", ".join(f"{key}={value!r}" for key, value in self.as_json().items())
        return f"Scope({parts})"


def _both(left: frozenset[str] | None, right: frozenset[str] | None) -> frozenset[str] | None:
    if left is None:
        return right
    if right is None:
        return left
    shared = left & right
    if not shared:
        raise ValueError("the scopes share no included names; the intersection matches nothing")
    return shared


def in_scope(fault: Any, *, step_name: str | None, provider: str | None) -> bool:
    """Apply a fault's scope; faults without one (including custom faults) match all."""
    check = getattr(fault, "in_scope", None)
    if callable(check):
        return bool(check(step_name=step_name, provider=provider))
    scope = getattr(fault, "scope", None)
    return scope is None or bool(scope.allows(step_name=step_name, provider=provider))
