"""Underwriting Workflow Pack implementation."""

from __future__ import annotations
from typing import Sequence
from finassure.core.pack import BaseWorkflowPack
from finassure.core.models import CaseApplicant, DecisionOutcome, OracleResult, WorkflowOutcome
from finassure.packs.underwriting.oracle import underwriting_oracle
from finassure.packs.underwriting.generator import generate_underwriting_cases
from finassure.packs.underwriting.agents import (
    UnderwritingState,
    run_intake_agent,
    run_doc_extraction_agent,
    run_bureau_agent,
    run_risk_scorer_agent,
    run_compliance_reviewer_agent,
)


class UnderwritingPack(BaseWorkflowPack):
    """Loan Underwriting workflow pack supporting v1 (naive) and v2 (hardened)."""

    def __init__(self, version: str = "v1") -> None:
        if version not in ("v1", "v2"):
            raise ValueError(f"Version must be 'v1' or 'v2', got '{version}'")
        self._version = version

    @property
    def name(self) -> str:
        return "underwriting"

    @property
    def version(self) -> str:
        return self._version

    def oracle(self, case: CaseApplicant) -> OracleResult:
        return underwriting_oracle(case)

    def generate_cases(self, count: int = 200, seed: int = 42) -> Sequence[CaseApplicant]:
        return generate_underwriting_cases(count=count, seed=seed)

    def run(self, case: CaseApplicant) -> WorkflowOutcome:
        """Run the 5-agent underwriting pipeline."""
        state = UnderwritingState(case=case, version=self._version)

        # 1. Intake
        state = run_intake_agent(state)

        # 2. Document extraction
        state = run_doc_extraction_agent(state)

        # 3. Bureau lookup
        state = run_bureau_agent(state)

        # 4. Risk scoring
        state = run_risk_scorer_agent(state)

        # 5. Compliance review
        state = run_compliance_reviewer_agent(state)

        final_decision = DecisionOutcome.REFER if state.escalated else state.preliminary_decision

        return WorkflowOutcome(
            decision=final_decision,
            reason_factors=list(dict.fromkeys(state.reason_factors)),
            narrative=state.narrative,
            risk_score=float(state.bureau_score) if state.bureau_score else None,
            dti=state.calculated_dti,
            escalated=state.escalated,
            escalation_reason=state.escalation_reason,
            tools_called=state.tools_called,
            raw_state={
                "bureau_status": state.bureau_status,
                "extracted_income": state.extracted_income,
                "extracted_deposits": state.extracted_monthly_deposits,
                "validation_errors": state.validation_errors,
            },
        )
