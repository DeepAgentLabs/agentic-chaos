"""Tool definitions for the Underwriting Pack, wrapped with Agentic Chaos."""

from __future__ import annotations
from typing import Any, Dict
from agentic_chaos import wrap_tool


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


# Wrap the tool with Agentic Chaos so that chaos_session can inject faults into it
bureau_lookup_tool = wrap_tool(_raw_bureau_lookup, tool_name="bureau_lookup")
