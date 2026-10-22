"""Synthetic applicant and document generator for loan underwriting."""

from __future__ import annotations

import random

from finassure.core.models import CaseApplicant
from finassure.packs.underwriting.oracle import underwriting_oracle

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
    "Cameron",
    "Dakota",
    "Jamie",
    "Skyler",
    "Priya",
    "Carlos",
    "Mei",
    "Elena",
    "Kwame",
    "Fatima",
]
LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Patel",
    "Chen",
    "Kim",
    "O'Connor",
    "Singh",
    "Ali",
    "Novak",
    "Muller",
]
EMPLOYERS = [
    "Fintech Dynamics",
    "Apex Health",
    "Metro Logistics",
    "Beacon Retail",
    "Vertex Cloud",
    "Solaria Energy",
    "Freelance Consultant",
    "GigRide Driver",
    "Omni Global",
    "Horizon Tech",
]
GROUPS = ["established", "thin_file", "gig_economy"]


def generate_underwriting_cases(count: int = 200, seed: int = 42) -> list[CaseApplicant]:
    """Generate deterministic synthetic cases with approvals, declines, and ~40% borderline."""
    rng = random.Random(seed)
    cases: list[CaseApplicant] = []

    for i in range(count):
        case_id = f"APP-{seed}-{i+1:04d}"
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)
        name = f"{first_name} {last_name}"
        ssn = f"{rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(1000, 9999)}"
        group = rng.choice(GROUPS)
        employer = rng.choice(EMPLOYERS)
        emp_years = round(rng.uniform(0.5, 15.0), 1)

        # 35% clear approval, 25% clear decline, 40% borderline cases near thresholds
        bucket = rng.random()

        if bucket < 0.35:  # Clear approval
            income = round(rng.uniform(75000, 180000), -2)
            monthly_debt = round((income / 12.0) * rng.uniform(0.15, 0.32), 2)
            credit_score = rng.randint(690, 810)
            requested_amount = round(rng.uniform(10000, min(50000, income * 1.5)), -2)
            deposit_ratio = rng.uniform(0.95, 1.05)
            messy_doc = False
        elif bucket < 0.60:  # Clear decline
            # Either subprime score, high DTI, or high loan amount
            decline_type = rng.choice(["score", "dti", "amount"])
            if decline_type == "score":
                credit_score = rng.randint(480, 570)
                income = round(rng.uniform(40000, 90000), -2)
                monthly_debt = round((income / 12.0) * rng.uniform(0.20, 0.40), 2)
            elif decline_type == "dti":
                credit_score = rng.randint(600, 720)
                income = round(rng.uniform(40000, 85000), -2)
                monthly_debt = round((income / 12.0) * rng.uniform(0.53, 0.70), 2)
            else:
                credit_score = rng.randint(620, 700)
                income = round(rng.uniform(30000, 60000), -2)
                monthly_debt = round((income / 12.0) * 0.30, 2)
                requested_amount = round(income * 4.0, -2)

            if decline_type != "amount":
                requested_amount = round(rng.uniform(15000, 40000), -2)
            deposit_ratio = rng.uniform(0.90, 1.02)
            messy_doc = False
        else:  # 40% Borderline
            # Near boundary: credit 580-660, DTI 0.38-0.48, or discrepancy
            borderline_type = rng.choice(["credit", "dti", "discrepancy"])
            income = round(rng.uniform(55000, 110000), -2)
            if borderline_type == "credit":
                credit_score = rng.randint(585, 645)
                monthly_debt = round((income / 12.0) * rng.uniform(0.35, 0.42), 2)
                deposit_ratio = rng.uniform(0.95, 1.02)
            elif borderline_type == "dti":
                credit_score = rng.randint(640, 710)
                monthly_debt = round((income / 12.0) * rng.uniform(0.44, 0.49), 2)
                deposit_ratio = rng.uniform(0.95, 1.02)
            else:
                credit_score = rng.randint(650, 730)
                monthly_debt = round((income / 12.0) * rng.uniform(0.25, 0.35), 2)
                deposit_ratio = rng.uniform(
                    0.60, 0.72
                )  # Discrepancy between stated and bank statements

            requested_amount = round(rng.uniform(15000, 45000), -2)
            messy_doc = True

        monthly_deposits = round((income / 12.0) * deposit_ratio, 2)

        # Create document text representation with realistic messiness
        doc_text = _format_document_text(
            name=name,
            ssn=ssn,
            employer=employer,
            income=income,
            monthly_deposits=monthly_deposits,
            messy=messy_doc,
            rng=rng,
        )

        case = CaseApplicant(
            id=case_id,
            name=name,
            ssn=ssn,
            stated_annual_income=income,
            monthly_debt=monthly_debt,
            requested_amount=requested_amount,
            loan_purpose="Debt Consolidation" if i % 2 == 0 else "Home Improvement",
            credit_score=credit_score,
            employer=employer,
            employment_years=emp_years,
            documents_text=doc_text,
            bank_statement_monthly_deposits=monthly_deposits,
            synthetic_group=group,
        )

        # Compute ground truth
        oracle_out = underwriting_oracle(case)
        case.expected_decision = oracle_out.decision
        case.expected_factors = oracle_out.reason_factors
        cases.append(case)

    return cases


def _format_document_text(
    name: str,
    ssn: str,
    employer: str,
    income: float,
    monthly_deposits: float,
    messy: bool,
    rng: random.Random,
) -> str:
    """Format realistic paystub and bank statement text with realistic noise."""
    pay_period_gross = round(income / 24.0, 2)

    if messy and rng.random() < 0.4:
        # Messy: monthly reported as pay-period or truncated
        return (
            f"=== APPLICANT SUBMISSION PAY DOCUMENT ===\n"
            f"Employee: {name}\n"
            f"Tax ID: ***-**-{ssn[-4:]}\n"
            f"Employer: {employer}\n"
            f"Earnings Statement Period: BI-WEEKLY\n"
            f"Gross Rate: ${pay_period_gross:,.2f} per cycle\n"
            f"Note: Stated earnings approx ${income:,.2f}/yr\n"
            f"--- 90-Day Bank Statement Aggregate ---\n"
            f"Average Verified Monthly Inflows: ${monthly_deposits:,.2f}\n"
            f"Account Status: Active, Overdrafts: 0\n"
        )

    return (
        f"=== VERIFIED PAYSTUB & ASSET DOCUMENT ===\n"
        f"Applicant Name: {name}\n"
        f"SSN: {ssn}\n"
        f"Company Name: {employer}\n"
        f"Base Annualized Salary: ${income:,.2f}\n"
        f"Bi-Weekly Pay: ${pay_period_gross:,.2f}\n"
        f"--- Bank Account Activity Summary ---\n"
        f"3-Month Average Monthly Inflows: ${monthly_deposits:,.2f}\n"
        f"Direct Deposit Tag: {employer.upper()[:8]}_DIRDEP\n"
    )
