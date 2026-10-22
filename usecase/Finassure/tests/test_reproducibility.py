"""Unit tests for Reproducibility.

Same seed produces identical synthetic cases, decisions, and deterministic oracle outcomes.
"""

from finassure.packs.kyc.generator import generate_kyc_cases
from finassure.packs.underwriting.generator import generate_underwriting_cases
from finassure.packs.underwriting.oracle import underwriting_oracle


def test_underwriting_generator_reproducibility():
    """Verify that same seed generates byte-for-byte identical underwriting cases."""
    cases_batch1 = generate_underwriting_cases(count=50, seed=12345)
    cases_batch2 = generate_underwriting_cases(count=50, seed=12345)

    assert len(cases_batch1) == len(cases_batch2) == 50

    for c1, c2 in zip(cases_batch1, cases_batch2, strict=False):
        assert c1.id == c2.id
        assert c1.name == c2.name
        assert c1.ssn == c2.ssn
        assert c1.stated_annual_income == c2.stated_annual_income
        assert c1.monthly_debt == c2.monthly_debt
        assert c1.requested_amount == c2.requested_amount
        assert c1.credit_score == c2.credit_score
        assert c1.bank_statement_monthly_deposits == c2.bank_statement_monthly_deposits
        assert c1.synthetic_group == c2.synthetic_group
        assert c1.documents_text == c2.documents_text
        assert c1.expected_decision == c2.expected_decision
        assert c1.expected_factors == c2.expected_factors


def test_kyc_generator_reproducibility():
    """Verify that same seed generates byte-for-byte identical KYC cases."""
    cases_batch1 = generate_kyc_cases(count=30, seed=999)
    cases_batch2 = generate_kyc_cases(count=30, seed=999)

    assert len(cases_batch1) == len(cases_batch2) == 30

    for c1, c2 in zip(cases_batch1, cases_batch2, strict=False):
        assert c1.id == c2.id
        assert c1.name == c2.name
        assert c1.ssn == c2.ssn
        assert c1.credit_score == c2.credit_score
        assert c1.expected_decision == c2.expected_decision
        assert c1.expected_factors == c2.expected_factors


def test_oracle_deterministic_decisions():
    """Verify that oracle is pure-deterministic and yields identical decisions across runs."""
    cases = generate_underwriting_cases(count=20, seed=42)
    for c in cases:
        out1 = underwriting_oracle(c)
        out2 = underwriting_oracle(c)
        assert out1.decision == out2.decision
        assert out1.reason_factors == out2.reason_factors
        assert out1.metrics == out2.metrics
