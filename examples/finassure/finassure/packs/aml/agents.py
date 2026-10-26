"""Agents for AML Triage Pack implementing AgenticLens spans."""

from __future__ import annotations

import logging
from typing import Any

import agenticlens
from finassure.core.inject import inject
from finassure.core.models import CaseApplicant, DecisionOutcome
from finassure.llm import llm_client
from finassure.packs.aml.tools import jurisdiction_lookup_tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AMLState(BaseModel):
    case: CaseApplicant
    version: str = "v1"
    parsed_amount: float = 0.0
    jurisdiction_risk: str = "LOW"
    jurisdiction_verified: bool = False
    tools_called: list[str] = Field(default_factory=list)
    decision: DecisionOutcome = DecisionOutcome.APPROVE
    reason_factors: list[str] = Field(default_factory=list)
    narrative: str = ""
    escalated: bool = False
    escalation_reason: str | None = None


def run_transaction_ingestion_agent(state: AMLState) -> AMLState:
    with agenticlens.step(
        name="transaction_ingestion",
        type="planner",
        agent_name="transaction_ingestion_agent",
        agent_role="Transaction monitoring message parsing",
        handoff_to="jurisdiction_agent",
    ):

        def _get_amount(amt: float) -> float:
            return amt

        # Allow chaos fault (silent degradation / corrupted amount) to intercept
        amt = inject(
            ("silent_degradation",),
            _get_amount,
            state.case.requested_amount,
            step_id="transaction_ingestion.amount",
            step_name="transaction_ingestion.amount",
            _chaos_from_node="transaction_ingestion_agent",
            _chaos_to_node="jurisdiction_agent",
        )
        state.parsed_amount = amt

        if state.version == "v2":
            if not isinstance(amt, int | float) or amt <= 0:
                state.escalated = True
                state.escalation_reason = "INVALID_TRANSACTION_PAYLOAD"
                state.reason_factors.append("MALFORMED_TRANSACTION_AMOUNT")
            elif state.case.requested_amount > 0:
                diff = abs(amt - state.case.requested_amount) / state.case.requested_amount
                if diff > 0.05:
                    state.escalated = True
                    state.escalation_reason = "TRANSACTION_AMOUNT_DISCREPANCY"
                    state.reason_factors.append("INGESTION_PAYLOAD_MISMATCH")
        return state


def run_jurisdiction_agent(state: AMLState) -> AMLState:
    with agenticlens.step(
        name="jurisdiction_screening",
        type="tool_call",
        agent_name="jurisdiction_agent",
        agent_role="FATF watchlist & offshore jurisdiction screening",
        handoff_from="transaction_ingestion_agent",
        handoff_to="aml_triage_agent",
    ):
        retries = 2 if state.version == "v2" else 1
        tool_succeeded = False

        for attempt in range(retries):
            try:
                state.tools_called.append("jurisdiction_lookup")
                query = f"{state.case.employer} {state.case.loan_purpose}"
                res = jurisdiction_lookup_tool(country_or_entity=query)
                if res and isinstance(res, dict):
                    state.jurisdiction_risk = res.get("risk_tier", "LOW")
                    state.jurisdiction_verified = True
                    tool_succeeded = True
                    break
            except Exception as e:
                logger.warning(f"Jurisdiction lookup attempt {attempt + 1} failed: {e}")
                if state.version == "v2" and attempt < retries - 1:
                    continue

        if not tool_succeeded:
            if state.version == "v1":
                # Naive flaw: assume domestic clear on failure
                state.jurisdiction_risk = "LOW"
            else:
                # Hardened v2: Escalate immediately to AML compliance officer
                state.escalated = True
                state.escalation_reason = "JURISDICTION_SERVICE_UNAVAILABLE"
                state.reason_factors.append("UNVERIFIED_JURISDICTION_DATA")

        def _send_aml_payload(payload: dict[str, Any]) -> dict[str, Any]:
            return payload

        handoff_payload = inject(
            ("handoff_corruption",),
            _send_aml_payload,
            {
                "jurisdiction_risk": state.jurisdiction_risk,
                "jurisdiction_verified": state.jurisdiction_verified,
            },
            step_id="jurisdiction_to_triage_handoff",
            step_name="jurisdiction_agent->aml_triage_agent",
            _chaos_edge_id="jurisdiction_agent->aml_triage_agent",
            _chaos_from_node="jurisdiction_agent",
            _chaos_to_node="aml_triage_agent",
        )

        if handoff_payload is None:
            if state.version == "v1":
                state.jurisdiction_risk = "LOW"
                state.jurisdiction_verified = True
            else:
                state.jurisdiction_verified = False
                state.escalated = True
                state.escalation_reason = "MISSING_JURISDICTION_HANDOFF"
                state.reason_factors.append("UNVERIFIED_JURISDICTION")
        else:
            state.jurisdiction_risk = handoff_payload.get("jurisdiction_risk", "LOW")
            state.jurisdiction_verified = handoff_payload.get("jurisdiction_verified", False)

        return state


def run_aml_triage_agent(state: AMLState) -> AMLState:
    with agenticlens.step(
        name="aml_triage_evaluation",
        type="planner",
        agent_name="aml_triage_agent",
        agent_role="SAR filing & structuring determination",
        handoff_from="jurisdiction_agent",
        handoff_to="aml_reviewer_agent",
    ):
        amt = state.parsed_amount

        if (
            state.version == "v2"
            and not state.escalated
            and ("jurisdiction_lookup" not in state.tools_called or not state.jurisdiction_verified)
        ):
            state.escalated = True
            state.escalation_reason = "MISSING_JURISDICTION_HANDOFF"
            state.reason_factors.append("UNVERIFIED_JURISDICTION")

        if 9000 <= amt <= 9999:
            state.decision = DecisionOutcome.DECLINE  # File SAR
            state.reason_factors.append("SUSPICIOUS_STRUCTURING_BELOW_REPORTING_THRESHOLD")
        elif state.jurisdiction_risk == "HIGH" and amt >= 50000:
            state.decision = DecisionOutcome.REFER  # EDD
            state.reason_factors.append("HIGH_RISK_JURISDICTION_LARGE_VALUE_TRANSFER")
        elif amt > 100000:
            state.decision = DecisionOutcome.REFER
            state.reason_factors.append("SIGNIFICANT_TRANSACTION_REQUIRING_SENIOR_OFFICER_REVIEW")
        elif state.escalated:
            state.decision = DecisionOutcome.REFER
        else:
            state.decision = DecisionOutcome.APPROVE
            state.reason_factors.append("STANDARD_TRANSACTION_ACTIVITY_CLEAR")

        return state


def run_aml_reviewer_agent(state: AMLState) -> AMLState:
    with agenticlens.step(
        name="aml_compliance_memo",
        type="llm_call",
        agent_name="aml_reviewer_agent",
        agent_role="SAR filing memo formulation",
        handoff_from="aml_triage_agent",
    ):
        decision = DecisionOutcome.REFER if state.escalated else state.decision
        prompt = (
            f"Review AML transaction alert for {state.case.name}.\n"
            f"Amount: ${state.parsed_amount:,.2f}\n"
            f"Decision: {decision.value}\n"
            f"Factors: {', '.join(state.reason_factors)}\n"
            f"Draft 1-sentence AML audit disposition memo."
        )
        state.narrative = llm_client.generate_text(
            prompt=prompt,
            system_instruction="You are an AML Compliance Officer drafting SAR audit memos.",
        )
        return state
