"""Tool definitions for the Underwriting Pack, wrapped with Agentic Chaos."""

from __future__ import annotations

from typing import Any

from finassure.core.inject import inject


def _raw_bureau_lookup(ssn: str, credit_score: int = 700) -> dict[str, Any]:
    """Mock Credit Bureau lookup API returning credit file details."""
    if not ssn or len(ssn) < 9:
        raise ValueError("Invalid SSN format for bureau lookup")

    return {
        "ssn": ssn,
        "credit_score": credit_score,
        "delinquencies_24m": 0 if credit_score >= 650 else 2,
        "revolving_utilization": round(max(0.1, min(0.95, (850 - credit_score) / 400)), 2),
        "total_tradelines": 12,
        "bankruptcies": 0,
        "status": "verified",
    }


def bureau_lookup_tool(**kwargs):
    """Tool-failure injection point for ToolCallFailureFault(tool_name="bureau_lookup")."""
    return inject(("tool_failure",), _raw_bureau_lookup, step_name="bureau_lookup", **kwargs)
