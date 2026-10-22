"""Synthetic transaction monitoring alert generator for AML Triage Pack."""

from __future__ import annotations

import random

from finassure.core.models import CaseApplicant
from finassure.packs.aml.oracle import aml_oracle

ACCOUNTS = ["ACC-US-10294", "ACC-CH-99201", "ACC-KY-33019", "ACC-SG-88129", "ACC-DE-44102"]
OFFSHORE_ENTITIES = [
    "Apex Offshore Holdings",
    "Global Shell Ltd",
    "Vertex Premier Corp",
    "Standard Domestic Payroll LLC",
]
GROUPS = ["established", "thin_file", "gig_economy"]


def generate_aml_cases(count: int = 50, seed: int = 88) -> list[CaseApplicant]:
    """Generate deterministic synthetic AML alerts."""
    rng = random.Random(seed)
    cases: list[CaseApplicant] = []

    for i in range(count):
        case_id = f"AML-{seed}-{i+1:04d}"
        group = rng.choice(GROUPS)

        bucket = rng.random()
        if bucket < 0.20:
            # Structuring ($9,500 - $9,950 to evade CTR)
            amount = float(rng.randint(9200, 9950))
            purpose = "Cash deposit structuring alert"
            employer = "Cash Heavy Retail LLC"
        elif bucket < 0.40:
            # High risk jurisdiction transfer
            amount = float(rng.randint(55000, 150000))
            purpose = "International wire high_risk corridor transfer"
            employer = rng.choice(OFFSHORE_ENTITIES)
        else:
            # Routine domestic transaction
            amount = float(rng.randint(500, 25000))
            purpose = "Routine vendor commercial invoice settlement"
            employer = "Standard Domestic Payroll LLC"

        case = CaseApplicant(
            id=case_id,
            name=f"Entity-{rng.choice(ACCOUNTS)}",
            ssn=f"{rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(1000, 9999)}",
            stated_annual_income=250000.0,
            monthly_debt=5000.0,
            requested_amount=amount,
            loan_purpose=purpose,
            credit_score=750,
            employer=employer,
            employment_years=5.0,
            documents_text=(
                f"SWIFT MT103 Transfer Message. Amount: ${amount:,.2f}. "
                f"Remitter: {employer}. Narrative: {purpose}."
            ),
            bank_statement_monthly_deposits=45000.0,
            synthetic_group=group,
        )

        oracle_out = aml_oracle(case)
        case.expected_decision = oracle_out.decision
        case.expected_factors = oracle_out.reason_factors
        cases.append(case)

    return cases
