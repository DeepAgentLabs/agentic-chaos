"""Tools for AML Triage Pack wrapped with Agentic Chaos."""

from __future__ import annotations

from typing import Any

from agentic_chaos import wrap_tool


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


jurisdiction_lookup_tool = wrap_tool(_raw_jurisdiction_lookup, tool_name="jurisdiction_lookup")
