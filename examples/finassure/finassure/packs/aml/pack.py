"""AML Triage Workflow Pack implementing BaseWorkflowPack."""

from __future__ import annotations

from collections.abc import Sequence

from finassure.core.models import CaseApplicant, DecisionOutcome, OracleResult, WorkflowOutcome
from finassure.core.pack import BaseWorkflowPack
from finassure.packs.aml.agents import (
    AMLState,
    run_aml_reviewer_agent,
    run_aml_triage_agent,
    run_jurisdiction_agent,
    run_transaction_ingestion_agent,
)
from finassure.packs.aml.generator import generate_aml_cases
from finassure.packs.aml.oracle import aml_oracle


class AMLPack(BaseWorkflowPack):
    """AML Suspicious Activity Triage workflow pack."""

    def __init__(self, version: str = "v1") -> None:
        if version not in ("v1", "v2"):
            raise ValueError(f"Version must be 'v1' or 'v2', got '{version}'")
        self._version = version

    @property
    def required_tools(self) -> list[str]:
        return ["jurisdiction_lookup"]

    @property
    def name(self) -> str:
        return "aml"

    @property
    def version(self) -> str:
        return self._version

    def oracle(self, case: CaseApplicant) -> OracleResult:
        return aml_oracle(case)

    def generate_cases(self, count: int = 50, seed: int = 88) -> Sequence[CaseApplicant]:
        return generate_aml_cases(count=count, seed=seed)

    def run(self, case: CaseApplicant) -> WorkflowOutcome:
        state = AMLState(case=case, version=self._version)
        state = run_transaction_ingestion_agent(state)
        state = run_jurisdiction_agent(state)
        state = run_aml_triage_agent(state)
        state = run_aml_reviewer_agent(state)

        final_decision = DecisionOutcome.REFER if state.escalated else state.decision

        return WorkflowOutcome(
            decision=final_decision,
            reason_factors=state.reason_factors,
            narrative=state.narrative,
            escalated=state.escalated,
            escalation_reason=state.escalation_reason,
            tools_called=state.tools_called,
            raw_state={
                "parsed_amount": state.parsed_amount,
                "jurisdiction_risk": state.jurisdiction_risk,
                "jurisdiction_verified": state.jurisdiction_verified,
            },
        )
