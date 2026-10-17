"""Name registry and the compact spec syntax used by the CLI.

A spec is ``name`` or ``name:arg[,arg...]``, where each arg is a positional
value or ``key=value``. List values separate items with ``|``::

    completes_within:30
    max_retries:3,step=search
    max_cost_impact:2,metric=calls
    no_retry_storm:5,window_seconds=10
    full_topology_traversal:expected_nodes=Planner|Reviewer
"""

from collections.abc import Callable
from typing import Any

from agentic_chaos.contracts.base import Contract
from agentic_chaos.contracts.builtin import (
    BUILTIN_CONTRACTS,
    CompletesWithin,
    FullTopologyTraversal,
    MaxCostImpact,
    MaxRetries,
    NoRetryStorm,
    NoUnhandledError,
    RecoveredAfterFailure,
)

CONTRACT_REGISTRY: dict[str, type[Contract]] = {cls.name: cls for cls in BUILTIN_CONTRACTS}


def _bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in ("1", "true", "yes", "on"):
        return True
    if lowered in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"expected a boolean, got '{value}'")


def _names(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


# Positional parameter order and converters for every spec-addressable parameter.
_SPEC: dict[type[Contract], tuple[list[str], dict[str, Callable[[str], Any]]]] = {
    CompletesWithin: (["timeout_s"], {"timeout_s": float}),
    NoUnhandledError: ([], {}),
    MaxRetries: (["n"], {"n": int, "step": str}),
    RecoveredAfterFailure: ([], {"require_step_success": _bool}),
    MaxCostImpact: (
        ["factor"],
        {"factor": float, "metric": str, "baseline_value": float},
    ),
    NoRetryStorm: (
        ["max_retries_per_window"],
        {"max_retries_per_window": int, "window_seconds": float},
    ),
    FullTopologyTraversal: ([], {"expected_nodes": _names, "ignore": _names}),
}


def parse_contract(spec: str) -> Contract:
    """Build a built-in contract from a CLI spec such as ``max_retries:3``."""
    name, _, raw_args = spec.strip().partition(":")
    name = name.strip()
    if name not in CONTRACT_REGISTRY:
        known = ", ".join(sorted(CONTRACT_REGISTRY))
        raise ValueError(f"Unknown contract '{name}'. Known contracts: {known}")
    cls = CONTRACT_REGISTRY[name]
    positional, converters = _SPEC[cls]
    kwargs: dict[str, Any] = {}
    index = 0
    for raw in (part.strip() for part in raw_args.split(",")) if raw_args.strip() else ():
        if not raw:
            continue
        key, sep, value = raw.partition("=")
        if not sep:
            if index >= len(positional):
                raise ValueError(f"Too many positional arguments for contract '{name}'")
            key, value = positional[index], raw
            index += 1
        key = key.strip()
        if key not in converters:
            allowed = ", ".join(converters) or "none"
            raise ValueError(f"Unknown parameter '{key}' for '{name}' (allowed: {allowed})")
        if key in kwargs:
            raise ValueError(f"Parameter '{key}' given twice for '{name}'")
        try:
            kwargs[key] = converters[key](value.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid value for '{name}' parameter '{key}': {exc}") from exc
    try:
        return cls(**kwargs)
    except TypeError as exc:
        raise ValueError(f"Invalid parameters for contract '{name}': {exc}") from exc


def describe_contracts() -> list[dict[str, Any]]:
    """Name, class, summary and spec parameters of every built-in contract."""
    entries = []
    for name, cls in sorted(CONTRACT_REGISTRY.items()):
        positional, converters = _SPEC[cls]
        doc = (cls.__doc__ or "").strip().splitlines()
        entries.append(
            {
                "name": name,
                "class": cls.__name__,
                "summary": doc[0] if doc else "",
                "positional": positional,
                "parameters": list(converters),
            }
        )
    return entries
