"""Explicit plugin loading: installing a distribution alone does not execute it."""

import inspect
from importlib.metadata import entry_points

from agentic_chaos.chaos.faults import FAULT_REGISTRY, BaseFault


def installed_plugins() -> list[str]:
    """Enumerate installed entry points without importing plugin code."""
    return sorted(point.name for point in entry_points(group="agentic_chaos.plugins"))


def load_plugins() -> list[str]:
    """Validate all plugins before registering any, rejecting collisions."""
    pending: dict[str, type[BaseFault]] = {}
    for point in entry_points(group="agentic_chaos.plugins"):
        if point.name in FAULT_REGISTRY or point.name in pending:
            raise ValueError(f"Duplicate fault plugin: {point.name}")
        fault = point.load()
        if not isinstance(fault, type) or not issubclass(fault, BaseFault):
            raise ValueError(f"Plugin {point.name} must export a BaseFault subclass")
        if inspect.isabstract(fault) or fault.name != point.name:
            raise ValueError(f"Plugin {point.name} must be concrete and have a matching name")
        pending[point.name] = fault
    FAULT_REGISTRY.update(pending)
    return sorted(pending)
