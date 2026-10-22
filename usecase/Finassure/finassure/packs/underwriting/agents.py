"""Agent implementations for Underwriting Pack (v1 Naive and v2 Hardened)."""

from __future__ import annotations

import logging
import time

import agenticlens
from finassure.core.models import CaseApplicant, DecisionOutcome
from finassure.llm import llm_client
from finassure.packs.underwriting.tools import bureau_lookup_tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExtractedFinancials(BaseModel):
    extracted_income: float
    extracted_monthly_deposits: float
    employer_verified: str = "Verified"
    extraction_confidence: float = 0.95


class UnderwritingState(BaseModel):
    case: CaseApplicant
    version: str = "v1"

    # State fields populated by agents
    intake_complete: bool = False
    extracted_income: float = 0.0
    extracted_monthly_deposits: float = 0.0
    bureau_score: int | None = None
    bureau_status: str | None = None
    tools_called: list[str] = Field(default_factory=list)

    # Decision fields
    calculated_dti: float = 0.0
    preliminary_decision: DecisionOutcome = DecisionOutcome.REFER
    reason_factors: list[str] = Field(default_factory=list)
    narrative: str = ""

    # Hardening & HITL flags
    escalated: bool = False
    escalation_reason: str | None = None
    validation_errors: list[str] = Field(default_factory=list)


# =========================================================================
# 1. Intake Agent
# =========================================================================


def run_intake_agent(state: UnderwritingState) -> UnderwritingState:
    with agenticlens.step(
        name="intake_processing",
        type="planner",
        agent_name="intake_agent",
        agent_role="Application intake validator",
        handoff_to="doc_extraction_agent",
    ):
        state.intake_complete = True
        return state


# =========================================================================
# 2. Document Extraction Agent
# =========================================================================


def run_doc_extraction_agent(state: UnderwritingState) -> UnderwritingState:
    with agenticlens.step(
        name="document_extraction",
        type="llm_call",
        agent_name="doc_extraction_agent",
        agent_role="Financial document information extraction",
        handoff_from="intake_agent",
        handoff_to="bureau_agent",
    ):
        prompt = (
            "Extract stated annualized income and monthly bank deposits "
            "from the following document:\n\n"
            f"{state.case.documents_text}\n\n"
            f"Stated income: ${state.case.stated_annual_income}\n"
            f"Monthly deposits: ${state.case.bank_statement_monthly_deposits}"
        )

        extracted = llm_client.generate_structured(
            prompt=prompt,
            schema=ExtractedFinancials,
            system_instruction="Extract financial values into JSON schema.",
        )

        from agentic_chaos import chaos_call

        # Allow chaos faults (silent_degradation / handoff_corruption) to intercept extraction
        def _get_income(inc: float) -> float:
            return inc

        income_val = chaos_call(
            _get_income,
            extracted.extracted_income,
            step_id="extraction_income",
            step_name="extraction.income",
            _chaos_edge_id="doc_extraction_agent->bureau_agent",
            _chaos_from_node="doc_extraction_agent",
            _chaos_to_node="bureau_agent",
        )

        state.extracted_income = income_val if income_val is not None else 0.0
        state.extracted_monthly_deposits = extracted.extracted_monthly_deposits

        if state.version == "v2":
            # Hardening v2: Schema validation & Income cross-check
            if income_val is None or not isinstance(income_val, int | float) or income_val <= 0:
                state.escalated = True
                state.escalation_reason = "INVALID_EXTRACTED_INCOME_SCHEMA"
                state.validation_errors.append("Income must be positive")

            # Cross-check stated income vs extracted income
            if state.case.stated_annual_income > 0:
                diff = (
                    abs(state.extracted_income - state.case.stated_annual_income)
                    / state.case.stated_annual_income
                )
                if diff > 0.15:
                    state.escalated = True
                    state.escalation_reason = "INCOME_EXTRACTION_STATED_MISMATCH"
                    state.reason_factors.append("INCOME_VERIFICATION_DISCREPANCY")

            # Cross-check stated income vs annualized deposits (15% standard tolerance)
            annualized_deposits = state.extracted_monthly_deposits * 12.0
            if state.extracted_income > 0:
                ratio = annualized_deposits / state.extracted_income
                if ratio < 0.85 or ratio > 1.18:
                    state.escalated = True
                    state.escalation_reason = "INCOME_VERIFICATION_DISCREPANCY"
                    state.reason_factors.append("INCOME_VERIFICATION_DISCREPANCY")

        return state


# =========================================================================
# 3. Bureau Lookup Agent
# =========================================================================


def run_bureau_agent(state: UnderwritingState) -> UnderwritingState:
    with agenticlens.step(
        name="bureau_verification",
        type="tool_call",
        agent_name="bureau_agent",
        agent_role="Credit bureau lookup coordinator",
        handoff_from="doc_extraction_agent",
        handoff_to="risk_scorer_agent",
    ):
        tool_succeeded = False
        retries = 2 if state.version == "v2" else 1

        for attempt in range(retries):
            try:
                state.tools_called.append("bureau_lookup")
                bureau_res = bureau_lookup_tool(
                    ssn=state.case.ssn,
                    credit_score=state.case.credit_score,
                )
                if bureau_res and isinstance(bureau_res, dict) and bureau_res.get("credit_score"):
                    state.bureau_score = int(bureau_res["credit_score"])
                    state.bureau_status = bureau_res.get("status", "verified")
                    tool_succeeded = True
                    break
            except Exception as e:
                logger.warning(f"Bureau lookup attempt {attempt + 1} encountered: {e}")
                if state.version == "v2" and attempt < retries - 1:
                    time.sleep(0.05)  # brief backoff in v2
                    continue

        if not tool_succeeded:
            if state.version == "v1":
                # Naive v1 flaw: silently assumes default score, leading to unsupported approval!
                logger.warning("v1: Bureau call failed; defaulting credit score to 680!")
                state.bureau_score = 680
                state.bureau_status = "unverified_fallback"
            else:
                # Hardened v2: Bureau failure means STRICT REFER, NEVER APPROVE
                state.bureau_score = None
                state.bureau_status = "unavailable"
                state.escalated = True
                state.escalation_reason = "BUREAU_SERVICE_UNAVAILABLE"
                state.reason_factors.append("UNVERIFIED_CREDIT_BUREAU_DATA")

        return state


# =========================================================================
# 4. Risk Scorer Agent
# =========================================================================


def run_risk_scorer_agent(state: UnderwritingState) -> UnderwritingState:
    with agenticlens.step(
        name="risk_scoring",
        type="planner",
        agent_name="risk_scorer_agent",
        agent_role="Deterministic credit risk scoring",
        handoff_from="bureau_agent",
        handoff_to="compliance_reviewer_agent",
    ):
        # Type safety & schema validation against memory corruption
        raw_income = state.extracted_income
        if not isinstance(raw_income, int | float):
            if state.version == "v2":
                state.escalated = True
                state.escalation_reason = "CORRUPTED_INCOME_DATA_TYPE"
                state.preliminary_decision = DecisionOutcome.REFER
                return state
            raw_income = 0.0

        income = (
            raw_income
            if (isinstance(raw_income, int | float) and raw_income > 0)
            else state.case.stated_annual_income
        )
        monthly_income = max(income / 12.0, 1.0)
        state.calculated_dti = round(state.case.monthly_debt / monthly_income, 4)

        score = state.bureau_score
        if score is not None and not isinstance(score, int | float):
            if state.version == "v2":
                state.escalated = True
                state.escalation_reason = "CORRUPTED_BUREAU_SCORE_DATA_TYPE"
                state.preliminary_decision = DecisionOutcome.REFER
                return state
            score = 680

        if state.version == "v2" and (score is None or state.escalated):
            state.preliminary_decision = DecisionOutcome.REFER
            return state

        # If v1 default score was used when bureau was missing:
        effective_score = score if score is not None else 680

        # Validate calculated_dti and effective_score are numeric
        if not isinstance(state.calculated_dti, int | float):
            if state.version == "v2":
                state.escalated = True
                state.escalation_reason = "CORRUPTED_DTI_DATA_TYPE"
                state.preliminary_decision = DecisionOutcome.REFER
                return state
            state.calculated_dti = 0.30

        if not isinstance(effective_score, int | float):
            if state.version == "v2":
                state.escalated = True
                state.escalation_reason = "CORRUPTED_SCORE_DATA_TYPE"
                state.preliminary_decision = DecisionOutcome.REFER
                return state
            effective_score = 680

        # Hard decline
        if effective_score < 580:
            state.preliminary_decision = DecisionOutcome.DECLINE
            state.reason_factors.append("CREDIT_SCORE_BELOW_MINIMUM")
            return state

        if state.calculated_dti > 0.50:
            state.preliminary_decision = DecisionOutcome.DECLINE
            state.reason_factors.append("EXCESSIVE_DEBT_TO_INCOME")
            return state

        if state.case.requested_amount > (3.5 * income):
            state.preliminary_decision = DecisionOutcome.DECLINE
            state.reason_factors.append("LOAN_AMOUNT_EXCEEDS_CAPACITY")
            return state

        # Refer (Borderline)
        if 580 <= effective_score < 620:
            state.preliminary_decision = DecisionOutcome.REFER
            state.reason_factors.append("SUBPRIME_CREDIT_TIER_REQUIRES_MANUAL_REVIEW")
            return state

        if 0.43 < state.calculated_dti <= 0.50:
            state.preliminary_decision = DecisionOutcome.REFER
            state.reason_factors.append("ELEVATED_DTI_REQUIRES_UNDERWRITER_SIGN_OFF")
            return state

        if (620 <= effective_score < 660) and (0.38 < state.calculated_dti <= 0.43):
            state.preliminary_decision = DecisionOutcome.REFER
            state.reason_factors.append("BORDERLINE_CREDIT_AND_DEBT_COMBINATION")
            return state

        # Approve
        if effective_score >= 680 and state.calculated_dti <= 0.36:
            state.preliminary_decision = DecisionOutcome.APPROVE
            state.reason_factors.extend(["PRIME_CREDIT_PROFILE", "ACCEPTABLE_DTI"])
            return state

        if effective_score >= 720 and state.calculated_dti <= 0.43:
            state.preliminary_decision = DecisionOutcome.APPROVE
            state.reason_factors.append("EXCELLENT_CREDIT_COMPENSATING_FACTOR")
            return state

        state.preliminary_decision = DecisionOutcome.APPROVE
        state.reason_factors.append("STANDARD_UNDERWRITING_CRITERIA_MET")
        return state


# =========================================================================
# 5. Compliance Reviewer Agent
# =========================================================================


def run_compliance_reviewer_agent(state: UnderwritingState) -> UnderwritingState:
    with agenticlens.step(
        name="compliance_review",
        type="llm_call",
        agent_name="compliance_reviewer_agent",
        agent_role="Regulatory compliance and adverse action notice formulation",
        handoff_from="risk_scorer_agent",
    ):
        # State decay / memory integrity check (F6)
        if state.version == "v2" and (
            not isinstance(state.extracted_income, int | float)
            or state.extracted_income <= 0
            or state.calculated_dti < 0
        ):
            state.escalated = True
            state.escalation_reason = "STATE_INTEGRITY_VIOLATION"
            state.reason_factors.append("CORRUPTED_INTERNAL_STATE")

        # Turn limit for reviewer loops (F6)
        reviewer_turn = getattr(state, "reviewer_turns", 1)
        max_turns = 3 if state.version == "v2" else 10
        if state.version == "v2" and reviewer_turn > max_turns:
            state.escalated = True
            state.escalation_reason = "REVIEWER_LOOP_TURN_LIMIT_EXCEEDED"
            state.reason_factors.append("MAX_REVIEW_TURNS_EXCEEDED")

        # Generate compliance narrative and final alignment
        decision = DecisionOutcome.REFER if state.escalated else state.preliminary_decision

        prompt = (
            f"Review underwriting determination for applicant {state.case.name}.\n"
            f"Preliminary Decision: {decision.value}\n"
            f"Factors: {', '.join(state.reason_factors) if state.reason_factors else 'None'}\n"
            f"Credit Score: {state.bureau_score}\n"
            f"DTI: {state.calculated_dti:.2%}\n"
            f"Provide a 1-sentence regulatory summary note."
        )

        # Retry cap with backoff for rate limits and timeouts (F6)
        narrative = ""
        retries = 3 if state.version == "v2" else 1
        for attempt in range(retries):
            try:
                narrative = llm_client.generate_text(
                    prompt=prompt,
                    system_instruction=(
                        "You are a financial compliance reviewer drafting adverse "
                        "action or approval documentation."
                    ),
                )
                break
            except Exception as e:
                logger.warning(f"Compliance reviewer LLM call attempt {attempt + 1} failed: {e}")
                if state.version == "v2" and attempt < retries - 1:
                    time.sleep(0.05 * (2**attempt))
                else:
                    if state.version == "v2":
                        state.escalated = True
                        state.escalation_reason = "COMPLIANCE_SERVICE_RATE_LIMITED"
                        narrative = (
                            "Escalated to human review due to compliance service rate limiting."
                        )
                    else:
                        raise e

        state.narrative = narrative or "Automated compliance review complete."
        return state
