"""KYC Onboarding Pack implementing BaseWorkflowPack."""

from __future__ import annotations

from collections.abc import Sequence

from finassure.core.models import CaseApplicant, DecisionOutcome, OracleResult, WorkflowOutcome
from finassure.core.pack import BaseWorkflowPack
from finassure.packs.kyc.agents import (
    KYCState,
    run_id_check_agent,
    run_kyc_reviewer_agent,
    run_kyc_risk_agent,
    run_sanctions_agent,
)
from finassure.packs.kyc.generator import generate_kyc_cases
from finassure.packs.kyc.oracle import kyc_oracle


class KYCPack(BaseWorkflowPack):
    """KYC and Sanctions Onboarding workflow pack."""

    def __init__(self, version: str = "v1") -> None:
        self._version = version

    @property
    def name(self) -> str:
        return "kyc"

    @property
    def version(self) -> str:
        return self._version

    def oracle(self, case: CaseApplicant) -> OracleResult:
        return kyc_oracle(case)

    def generate_cases(self, count: int = 100, seed: int = 77) -> Sequence[CaseApplicant]:
        return generate_kyc_cases(count=count, seed=seed)

    def run(self, case: CaseApplicant) -> WorkflowOutcome:
        state = KYCState(case=case, version=self._version)
        state = run_id_check_agent(state)
        state = run_sanctions_agent(state)
        state = run_kyc_risk_agent(state)
        state = run_kyc_reviewer_agent(state)

        final_decision = DecisionOutcome.REFER if state.escalated else state.decision

        return WorkflowOutcome(
            decision=final_decision,
            reason_factors=state.reason_factors,
            narrative=state.narrative,
            escalated=state.escalated,
            escalation_reason=state.escalation_reason,
            tools_called=state.tools_called,
            raw_state={
                "id_verified": state.id_verified,
                "sanctions_hit": state.sanctions_hit,
                "pep_hit": state.pep_hit,
            },
        )
