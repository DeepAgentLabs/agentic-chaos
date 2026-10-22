"""Deterministic Policy Oracle for KYC Onboarding Pack."""

from __future__ import annotations
from finassure.core.models import CaseApplicant, DecisionOutcome, OracleResult


def kyc_oracle(case: CaseApplicant) -> OracleResult:
    """Evaluate KYC applicant against deterministic compliance rules."""
    reasons: list[str] = []
    
    # Ground truth indicators simulated from applicant fields
    name_l = case.name.lower()
    is_sanctioned = "sanction" in name_l or "blocked" in name_l or "sanction" in case.loan_purpose.lower() or case.credit_score < 450
    is_pep = "minister" in name_l or "senator" in name_l or "pep" in case.loan_purpose.lower() or case.employment_years > 20
    is_high_risk = case.synthetic_group == "gig_economy" and case.monthly_debt > 8000
    
    if is_sanctioned:
        reasons.append("OFAC_SANCTIONS_MATCH")
        return OracleResult(
            decision=DecisionOutcome.DECLINE,
            reason_factors=reasons,
            policy_version="kyc-1.0",
            metrics={"risk_level": "CRITICAL"},
        )

    if is_pep:
        reasons.append("POLITICALLY_EXPOSED_PERSON_ENHANCED_DUE_DILIGENCE")
        return OracleResult(
            decision=DecisionOutcome.REFER,
            reason_factors=reasons,
            policy_version="kyc-1.0",
            metrics={"risk_level": "ELEVATED"},
        )

    if is_high_risk:
        reasons.append("HIGH_RISK_PROFILE_REQUIRES_COMPLIANCE_SIGN_OFF")
        return OracleResult(
            decision=DecisionOutcome.REFER,
            reason_factors=reasons,
            policy_version="kyc-1.0",
            metrics={"risk_level": "MEDIUM_HIGH"},
        )

    reasons.append("STANDARD_IDENTITY_AND_SANCTIONS_CLEAR")
    return OracleResult(
        decision=DecisionOutcome.APPROVE,
        reason_factors=reasons,
        policy_version="kyc-1.0",
        metrics={"risk_level": "LOW"},
    )
