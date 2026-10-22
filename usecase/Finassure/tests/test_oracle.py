"""Unit tests for deterministic policy oracles."""

import pytest
from finassure.core.models import CaseApplicant, DecisionOutcome
from finassure.packs.underwriting.oracle import underwriting_oracle
from finassure.packs.kyc.oracle import kyc_oracle


def test_underwriting_oracle_clear_approval():
    case = CaseApplicant(
        id="T1",
        name="John Doe",
        ssn="123-45-6789",
        stated_annual_income=120000.0,
        monthly_debt=2000.0,  # DTI = 2000 / 10000 = 0.20
        requested_amount=30000.0,
        loan_purpose="Debt Consolidation",
        credit_score=750,
        employer="Acme Inc",
        employment_years=5.0,
        documents_text="",
        bank_statement_monthly_deposits=10000.0,
    )
    result = underwriting_oracle(case)
    assert result.decision == DecisionOutcome.APPROVE
    assert "PRIME_CREDIT_PROFILE" in result.reason_factors or "EXCELLENT_CREDIT_COMPENSATING_FACTOR" in result.reason_factors


def test_underwriting_oracle_hard_declines():
    # Low score
    case_subprime = CaseApplicant(
        id="T2",
        name="Jane Subprime",
        ssn="123-45-6789",
        stated_annual_income=60000.0,
        monthly_debt=1000.0,
        requested_amount=20000.0,
        loan_purpose="Personal",
        credit_score=520,
        employer="Retail",
        employment_years=1.0,
        documents_text="",
        bank_statement_monthly_deposits=5000.0,
    )
    assert underwriting_oracle(case_subprime).decision == DecisionOutcome.DECLINE

    # High DTI
    case_high_dti = CaseApplicant(
        id="T3",
        name="Bob Debt",
        ssn="123-45-6789",
        stated_annual_income=60000.0,
        monthly_debt=3500.0,  # DTI = 70%
        requested_amount=20000.0,
        loan_purpose="Personal",
        credit_score=700,
        employer="Retail",
        employment_years=2.0,
        documents_text="",
        bank_statement_monthly_deposits=5000.0,
    )
    assert underwriting_oracle(case_high_dti).decision == DecisionOutcome.DECLINE


def test_kyc_oracle_sanctions():
    case_sanction = CaseApplicant(
        id="K1",
        name="Blocked Individual",
        ssn="999-99-9999",
        stated_annual_income=50000.0,
        monthly_debt=500.0,
        requested_amount=0.0,
        loan_purpose="Sanctions test",
        credit_score=400,
        employer="Unknown",
        employment_years=0.5,
        documents_text="",
        bank_statement_monthly_deposits=4000.0,
    )
    assert kyc_oracle(case_sanction).decision == DecisionOutcome.DECLINE
