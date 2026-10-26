"""Tools for KYC Onboarding Pack, wrapped with Agentic Chaos."""

from __future__ import annotations

from typing import Any

from finassure.core.inject import inject


def _raw_sanctions_lookup(
    name: str, ssn: str, purpose: str = "", credit_score: int = 700
) -> dict[str, Any]:
    """Mock Sanctions and PEP Screening tool."""
    name_lower = name.lower()
    purpose_lower = purpose.lower()
    hit = (
        "sanction" in name_lower
        or "blocked" in name_lower
        or "sanction" in purpose_lower
        or credit_score < 450
    )
    pep = "senator" in name_lower or "minister" in name_lower or "pep" in purpose_lower

    return {
        "name": name,
        "sanctions_hit": hit,
        "pep_hit": pep,
        "matched_lists": ["OFAC_SDN"] if hit else ([]),
        "status": "completed",
    }


def sanctions_screening_tool(**kwargs):
    """Tool-failure injection point for ToolCallFailureFault(tool_name="sanctions_screening")."""
    return inject(
        ("tool_failure",), _raw_sanctions_lookup, step_name="sanctions_screening", **kwargs
    )
