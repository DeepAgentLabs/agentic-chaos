"""Deterministic Underwriting Policy Oracle (Ground Truth).

Defines the mathematically and regulatorily correct answer for every synthetic
applicant case without using an LLM.
"""

from __future__ import annotations

from finassure.core.models import CaseApplicant, DecisionOutcome, OracleResult


def underwriting_oracle(case: CaseApplicant) -> OracleResult:
    """Evaluate applicant against deterministic policy rules."""
    reasons: list[str] = []

    monthly_stated = max(case.stated_annual_income / 12.0, 1.0)
    dti = case.monthly_debt / monthly_stated

    # 1. Income cross-check discrepancy check
    annualized_deposits = case.bank_statement_monthly_deposits * 12.0
    income_ratio = annualized_deposits / max(case.stated_annual_income, 1.0)

    # 2. Hard decline rules
    if case.credit_score < 580:
        reasons.append("CREDIT_SCORE_BELOW_MINIMUM")
        return OracleResult(
            decision=DecisionOutcome.DECLINE,
            reason_factors=reasons,
            metrics={
                "dti": round(dti, 4),
                "credit_score": case.credit_score,
                "income_ratio": round(income_ratio, 2),
            },
        )

    if dti > 0.50:
        reasons.append("EXCESSIVE_DEBT_TO_INCOME")
        return OracleResult(
            decision=DecisionOutcome.DECLINE,
            reason_factors=reasons,
            metrics={
                "dti": round(dti, 4),
                "credit_score": case.credit_score,
                "income_ratio": round(income_ratio, 2),
            },
        )

    if case.requested_amount > (3.5 * case.stated_annual_income):
        reasons.append("LOAN_AMOUNT_EXCEEDS_CAPACITY")
        return OracleResult(
            decision=DecisionOutcome.DECLINE,
            reason_factors=reasons,
            metrics={
                "dti": round(dti, 4),
                "credit_score": case.credit_score,
                "income_ratio": round(income_ratio, 2),
            },
        )

    # 3. Refer to human review (Borderline cases or discrepancies)
    if income_ratio < 0.75:
        reasons.append("INCOME_VERIFICATION_DISCREPANCY")
        return OracleResult(
            decision=DecisionOutcome.REFER,
            reason_factors=reasons,
            metrics={
                "dti": round(dti, 4),
                "credit_score": case.credit_score,
                "income_ratio": round(income_ratio, 2),
            },
        )

    if 580 <= case.credit_score < 620:
        reasons.append("SUBPRIME_CREDIT_TIER_REQUIRES_MANUAL_REVIEW")
        return OracleResult(
            decision=DecisionOutcome.REFER,
            reason_factors=reasons,
            metrics={
                "dti": round(dti, 4),
                "credit_score": case.credit_score,
                "income_ratio": round(income_ratio, 2),
            },
        )

    if 0.43 < dti <= 0.50:
        reasons.append("ELEVATED_DTI_REQUIRES_UNDERWRITER_SIGN_OFF")
        return OracleResult(
            decision=DecisionOutcome.REFER,
            reason_factors=reasons,
            metrics={
                "dti": round(dti, 4),
                "credit_score": case.credit_score,
                "income_ratio": round(income_ratio, 2),
            },
        )

    if (620 <= case.credit_score < 660) and (0.38 < dti <= 0.43):
        reasons.append("BORDERLINE_CREDIT_AND_DEBT_COMBINATION")
        return OracleResult(
            decision=DecisionOutcome.REFER,
            reason_factors=reasons,
            metrics={
                "dti": round(dti, 4),
                "credit_score": case.credit_score,
                "income_ratio": round(income_ratio, 2),
            },
        )

    # 4. Clear approvals
    if case.credit_score >= 680 and dti <= 0.36:
        reasons.append("PRIME_CREDIT_PROFILE")
        reasons.append("ACCEPTABLE_DTI")
        return OracleResult(
            decision=DecisionOutcome.APPROVE,
            reason_factors=reasons,
            metrics={
                "dti": round(dti, 4),
                "credit_score": case.credit_score,
                "income_ratio": round(income_ratio, 2),
            },
        )

    if case.credit_score >= 720 and dti <= 0.43:
        reasons.append("EXCELLENT_CREDIT_COMPENSATING_FACTOR")
        return OracleResult(
            decision=DecisionOutcome.APPROVE,
            reason_factors=reasons,
            metrics={
                "dti": round(dti, 4),
                "credit_score": case.credit_score,
                "income_ratio": round(income_ratio, 2),
            },
        )

    # Standard approval
    reasons.append("STANDARD_UNDERWRITING_CRITERIA_MET")
    return OracleResult(
        decision=DecisionOutcome.APPROVE,
        reason_factors=reasons,
        metrics={
            "dti": round(dti, 4),
            "credit_score": case.credit_score,
            "income_ratio": round(income_ratio, 2),
        },
    )
