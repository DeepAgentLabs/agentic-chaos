"""KYC Onboarding Agents with AgenticLens and Agentic Chaos."""

from __future__ import annotations

import logging
from typing import Any

import agenticlens
from finassure.core.models import CaseApplicant, DecisionOutcome
from finassure.llm import llm_client
from finassure.packs.kyc.tools import sanctions_screening_tool
from pydantic import BaseModel, Field

from agentic_chaos import chaos_call

logger = logging.getLogger(__name__)


class KYCState(BaseModel):
    case: CaseApplicant
    version: str = "v1"
    verified_name: str = ""
    id_verified: bool = False
    sanctions_hit: bool = False
    pep_hit: bool = False
    sanctions_verified: bool = False
    tools_called: list[str] = Field(default_factory=list)
    risk_level: str = "LOW"
    decision: DecisionOutcome = DecisionOutcome.APPROVE
    reason_factors: list[str] = Field(default_factory=list)
    narrative: str = ""
    escalated: bool = False
    escalation_reason: str | None = None


def run_id_check_agent(state: KYCState) -> KYCState:
    with agenticlens.step(
        name="identity_verification",
        type="planner",
        agent_name="id_check_agent",
        agent_role="Government identification validation",
        handoff_to="sanctions_agent",
    ):

        def _get_name(n: str) -> str:
            return n

        # Allow chaos fault (silent degradation / altered_name) to intercept name
        effective_name = chaos_call(
            _get_name,
            state.case.name,
            step_id="id_check_agent.name",
            step_name="id_check_agent.name",
            _chaos_edge_id="id_check_agent->sanctions_agent",
            _chaos_from_node="id_check_agent",
            _chaos_to_node="sanctions_agent",
        )
        state.verified_name = effective_name
        state.id_verified = True

        # Hardened v2: detect if name was altered/corrupted against source document
        if state.version == "v2" and effective_name != state.case.name:
            state.escalated = True
            state.escalation_reason = "IDENTITY_NAME_MISMATCH"
            state.reason_factors.append("IDENTITY_VERIFICATION_DISCREPANCY")

        return state


def run_sanctions_agent(state: KYCState) -> KYCState:
    with agenticlens.step(
        name="sanctions_screening",
        type="tool_call",
        agent_name="sanctions_agent",
        agent_role="OFAC and PEP watchlists screening",
        handoff_from="id_check_agent",
        handoff_to="kyc_risk_agent",
    ):
        lookup_name = state.verified_name or state.case.name
        retries = 2 if state.version == "v2" else 1
        tool_succeeded = False

        for attempt in range(retries):
            try:
                state.tools_called.append("sanctions_screening")
                res = sanctions_screening_tool(
                    name=lookup_name,
                    ssn=state.case.ssn,
                    purpose=state.case.loan_purpose,
                    credit_score=state.case.credit_score,
                )
                if res and isinstance(res, dict):
                    state.sanctions_hit = res.get("sanctions_hit", False)
                    state.pep_hit = res.get("pep_hit", False)
                    state.sanctions_verified = True
                    tool_succeeded = True
                    break
            except Exception as e:
                logger.warning(f"Sanctions screening fault attempt {attempt + 1}: {e}")
                if state.version == "v2" and attempt < retries - 1:
                    continue

        if not tool_succeeded:
            if state.version == "v1":
                # Naive flaw: assume clear on failure, leading to unsupported onboarding!
                state.sanctions_hit = False
                state.sanctions_verified = False
            else:
                # Hardened v2: Escalate immediately, never default to clear
                state.escalated = True
                state.escalation_reason = "SANCTIONS_SERVICE_UNAVAILABLE"
                state.reason_factors.append("UNVERIFIED_SANCTIONS_DATA")

        def _send_screening_payload(payload: dict[str, Any]) -> dict[str, Any]:
            return payload

        screening_payload = chaos_call(
            _send_screening_payload,
            {
                "sanctions_hit": state.sanctions_hit,
                "pep_hit": state.pep_hit,
                "sanctions_verified": state.sanctions_verified,
            },
            step_id="sanctions_to_risk_handoff",
            step_name="sanctions_agent->kyc_risk_agent",
            _chaos_edge_id="sanctions_agent->kyc_risk_agent",
            _chaos_from_node="sanctions_agent",
            _chaos_to_node="kyc_risk_agent",
        )

        if screening_payload is None:
            if state.version == "v1":
                state.sanctions_hit = False
                state.pep_hit = False
                state.sanctions_verified = True
            else:
                state.sanctions_verified = False
                state.escalated = True
                state.escalation_reason = "SANCTIONS_HANDOFF_PAYLOAD_DROPPED"
                state.reason_factors.append("MISSING_SANCTIONS_HANDOFF")
        else:
            state.sanctions_hit = screening_payload.get("sanctions_hit", False)
            state.pep_hit = screening_payload.get("pep_hit", False)
            state.sanctions_verified = screening_payload.get("sanctions_verified", False)

        return state


def run_kyc_risk_agent(state: KYCState) -> KYCState:
    with agenticlens.step(
        name="kyc_risk_rating",
        type="planner",
        agent_name="kyc_risk_agent",
        agent_role="Customer risk rating classification",
        handoff_from="sanctions_agent",
        handoff_to="kyc_reviewer_agent",
    ):
        # Contract validation: verify required screening handoff was actually completed
        if (
            state.version == "v2"
            and not state.escalated
            and ("sanctions_screening" not in state.tools_called or not state.sanctions_verified)
        ):
            state.escalated = True
            state.escalation_reason = "SANCTIONS_VERIFICATION_MISSING"
            state.reason_factors.append("MISSING_SANCTIONS_HANDOFF")

        if state.sanctions_hit:
            state.decision = DecisionOutcome.DECLINE
            state.reason_factors.append("OFAC_SANCTIONS_MATCH")
        elif state.pep_hit or state.case.employment_years > 20:
            state.decision = DecisionOutcome.REFER
            state.reason_factors.append("POLITICALLY_EXPOSED_PERSON_ENHANCED_DUE_DILIGENCE")
        elif state.case.synthetic_group == "gig_economy" and state.case.monthly_debt > 8000:
            state.decision = DecisionOutcome.REFER
            state.reason_factors.append("HIGH_RISK_PROFILE_REQUIRES_COMPLIANCE_SIGN_OFF")
        elif state.escalated:
            state.decision = DecisionOutcome.REFER
        else:
            state.decision = DecisionOutcome.APPROVE
            state.reason_factors.append("STANDARD_IDENTITY_AND_SANCTIONS_CLEAR")

        return state


def run_kyc_reviewer_agent(state: KYCState) -> KYCState:
    with agenticlens.step(
        name="kyc_compliance_review",
        type="llm_call",
        agent_name="kyc_reviewer_agent",
        agent_role="KYC compliance documentation sign-off",
        handoff_from="kyc_risk_agent",
    ):
        decision = DecisionOutcome.REFER if state.escalated else state.decision
        prompt = (
            f"Review KYC onboarding decision for {state.case.name}.\n"
            f"Decision: {decision.value}\n"
            f"Factors: {', '.join(state.reason_factors)}\n"
            f"Provide a 1-sentence KYC audit summary."
        )
        state.narrative = llm_client.generate_text(
            prompt=prompt,
            system_instruction="You are a senior AML/KYC officer drafting compliance sign-offs.",
        )
        return state
