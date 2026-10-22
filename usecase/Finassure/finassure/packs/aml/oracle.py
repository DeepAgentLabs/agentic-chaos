"""Deterministic Policy Oracle for AML Triage Pack."""

from __future__ import annotations
from finassure.core.models import CaseApplicant, DecisionOutcome, OracleResult


def aml_oracle(case: CaseApplicant) -> OracleResult:
    """Evaluate AML alert against deterministic anti-money-laundering rules."""
    reasons: list[str] = []
    
    # Check for rapid structuring or excessive transaction size
    amount = case.requested_amount
    is_structuring = 9000 <= amount <= 9999
    is_high_value = amount >= 50000
    is_high_risk_country = "high_risk" in case.loan_purpose.lower() or "offshore" in case.employer.lower() or "shell" in case.employer.lower()
    
    if is_structuring:
        reasons.append("SUSPICIOUS_STRUCTURING_BELOW_REPORTING_THRESHOLD")
        return OracleResult(
            decision=DecisionOutcome.DECLINE,  # File SAR
            reason_factors=reasons,
            policy_version="aml-1.0",
            metrics={"risk_level": "CRITICAL", "sar_required": True},
        )
        
    if is_high_risk_country and is_high_value:
        reasons.append("HIGH_RISK_JURISDICTION_LARGE_VALUE_TRANSFER")
        return OracleResult(
            decision=DecisionOutcome.REFER,  # Enhanced Due Diligence (EDD)
            reason_factors=reasons,
            policy_version="aml-1.0",
            metrics={"risk_level": "ELEVATED", "edd_required": True},
        )

    if amount > 100000:
        reasons.append("SIGNIFICANT_TRANSACTION_REQUIRING_SENIOR_OFFICER_REVIEW")
        return OracleResult(
            decision=DecisionOutcome.REFER,
            reason_factors=reasons,
            policy_version="aml-1.0",
            metrics={"risk_level": "MEDIUM", "edd_required": False},
        )

    reasons.append("STANDARD_TRANSACTION_ACTIVITY_CLEAR")
    return OracleResult(
        decision=DecisionOutcome.APPROVE,  # False positive / Dismiss alert
        reason_factors=reasons,
        policy_version="aml-1.0",
        metrics={"risk_level": "LOW", "sar_required": False},
    )
