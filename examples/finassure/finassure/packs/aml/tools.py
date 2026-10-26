"""Tools for AML Triage Pack wrapped with Agentic Chaos."""

from __future__ import annotations

from typing import Any

from finassure.core.inject import inject


def _raw_jurisdiction_lookup(country_or_entity: str) -> dict[str, Any]:
    """Mock Jurisdiction and FATF List Lookup tool."""
    lower = country_or_entity.lower()
    is_high_risk = "offshore" in lower or "shell" in lower or "high_risk" in lower
    return {
        "target": country_or_entity,
        "is_fatf_greylist": is_high_risk,
        "risk_tier": "HIGH" if is_high_risk else "LOW",
        "status": "completed",
    }


def jurisdiction_lookup_tool(**kwargs):
    """Tool-failure injection point for ToolCallFailureFault(tool_name="jurisdiction_lookup")."""
    return inject(
        ("tool_failure",), _raw_jurisdiction_lookup, step_name="jurisdiction_lookup", **kwargs
    )
