"""Synthetic case generator for KYC Onboarding Pack."""

from __future__ import annotations

import random

from finassure.core.models import CaseApplicant
from finassure.packs.kyc.oracle import kyc_oracle

FIRST_NAMES = [
    "Alex",
    "Jordan",
    "Taylor",
    "Morgan",
    "Sam",
    "Chris",
    "Pat",
    "Avery",
    "Casey",
    "Riley",
    "Victor",
    "Tariq",
    "Elena",
]
LAST_NAMES = [
    "Vance",
    "Kovac",
    "Sanctioned_Individual",
    "Petrov",
    "Minister_Ross",
    "Chen",
    "Dubois",
    "Nakamoto",
    "Silva",
]
GROUPS = ["established", "thin_file", "gig_economy"]


def generate_kyc_cases(count: int = 100, seed: int = 77) -> list[CaseApplicant]:
    """Generate deterministic synthetic KYC cases."""
    rng = random.Random(seed)
    cases: list[CaseApplicant] = []

    for i in range(count):
        case_id = f"KYC-{seed}-{i+1:04d}"
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        name = f"{first} {last}"
        ssn = f"{rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(1000, 9999)}"
        group = rng.choice(GROUPS)

        # Inject occasional sanctions or PEP
        bucket = rng.random()
        if bucket < 0.15:
            purpose = "OFAC Sanctions match test"
            credit_score = 420
        elif bucket < 0.30:
            purpose = "PEP political official review"
            credit_score = 750
        else:
            purpose = "Retail customer standard onboarding"
            credit_score = 720

        case = CaseApplicant(
            id=case_id,
            name=name,
            ssn=ssn,
            stated_annual_income=85000.0,
            monthly_debt=1200.0,
            requested_amount=0.0,
            loan_purpose=purpose,
            credit_score=credit_score,
            employer="Acme International",
            employment_years=2.5,
            documents_text=f"Government ID: Verified Passport {name}. Proof of address: Valid.",
            bank_statement_monthly_deposits=7000.0,
            synthetic_group=group,
        )

        oracle_out = kyc_oracle(case)
        case.expected_decision = oracle_out.decision
        case.expected_factors = oracle_out.reason_factors
        cases.append(case)

    return cases
