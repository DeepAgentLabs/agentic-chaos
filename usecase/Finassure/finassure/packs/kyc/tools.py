"""Tools for KYC Onboarding Pack, wrapped with Agentic Chaos."""

from __future__ import annotations

from typing import Any

from agentic_chaos import wrap_tool


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


sanctions_screening_tool = wrap_tool(_raw_sanctions_lookup, tool_name="sanctions_screening")
