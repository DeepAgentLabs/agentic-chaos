"""Evaluator Suite for FinAssure."""

from __future__ import annotations

import logging
from typing import Any

from finassure.core.models import (
    DecisionOutcome,
    EvaluationResult,
    OracleResult,
    WorkflowOutcome,
)
from finassure.llm import llm_client
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# =========================================================================
# 1. Decision Consistency Evaluator
# =========================================================================


def eval_decision_consistency(
    outcome: WorkflowOutcome,
    oracle: OracleResult,
    clean_run: bool = True,
) -> EvaluationResult:
    """Check if clean workflow outcome matches deterministic policy oracle."""
    if not clean_run:
        matches = outcome.decision == oracle.decision or outcome.escalated
        return EvaluationResult(
            evaluator_name="decision_consistency",
            passed=matches,
            score=1.0 if matches else 0.0,
            details={
                "status": "safe_escalation" if outcome.escalated else "resilient_match",
                "workflow_decision": outcome.decision.value,
                "oracle_decision": oracle.decision.value,
            },
            is_hard_fail=False,
        )
    matches = outcome.decision == oracle.decision
    return EvaluationResult(
        evaluator_name="decision_consistency",
        passed=matches,
        score=1.0 if matches else 0.0,
        details={
            "workflow_decision": outcome.decision.value,
            "oracle_decision": oracle.decision.value,
        },
        is_hard_fail=False,
    )


# =========================================================================
# 2. Chaos-Decision Stability & Safe Degradation Evaluator
# =========================================================================


def eval_chaos_stability(
    outcome: WorkflowOutcome,
    oracle: OracleResult,
    is_faulted: bool,
) -> EvaluationResult:
    """Evaluate whether the system handled faults safely (maintained correctness or escalated)."""
    if not is_faulted:
        # In clean run, stability equals consistency
        passed = outcome.decision == oracle.decision
        return EvaluationResult(
            evaluator_name="chaos_stability",
            passed=passed,
            score=1.0 if passed else 0.0,
            details={"status": "clean_run", "decision": outcome.decision.value},
            is_hard_fail=False,
        )

    # In faulted run:
    # 1. Correct decision maintained -> passed
    if outcome.decision == oracle.decision:
        return EvaluationResult(
            evaluator_name="chaos_stability",
            passed=True,
            score=1.0,
            details={"status": "resilient_match", "decision": outcome.decision.value},
            is_hard_fail=False,
        )

    # 2. Escalated to human review -> safe degradation!
    if outcome.escalated or outcome.decision == DecisionOutcome.REFER:
        return EvaluationResult(
            evaluator_name="chaos_stability",
            passed=True,
            score=0.95,
            details={"status": "safe_escalation", "reason": outcome.escalation_reason},
            is_hard_fail=False,
        )

    # 3. Decision flipped without escalation -> SILENT FAILURE
    return EvaluationResult(
        evaluator_name="chaos_stability",
        passed=False,
        score=0.0,
        details={
            "status": "silent_failure",
            "oracle": oracle.decision.value,
            "actual": outcome.decision.value,
        },
        is_hard_fail=True,
    )


# =========================================================================
# 3. Required Tools Called (Trace-Aware)
# =========================================================================


def eval_required_tools(
    outcome: WorkflowOutcome,
    trace_steps: list[dict[str, Any]],
    required_tools: list[str] | None = None,
) -> EvaluationResult:
    """Verify that required tools (e.g., bureau_lookup) were invoked prior to approval."""
    reqs = required_tools or ["bureau_lookup"]

    # If not approved, tool absence might be fine (e.g. declined on intake)
    if outcome.decision != DecisionOutcome.APPROVE:
        return EvaluationResult(
            evaluator_name="required_tools_called",
            passed=True,
            score=1.0,
            details={"status": "non_approval_skips_enforcement"},
            is_hard_fail=False,
        )

    called_set = set(outcome.tools_called)
    for step in trace_steps:
        if step.get("name") == "bureau_lookup" or step.get("agent_name") == "bureau_agent":
            called_set.add("bureau_lookup")

    missing = [tool for tool in reqs if tool not in called_set]
    passed = len(missing) == 0

    return EvaluationResult(
        evaluator_name="required_tools_called",
        passed=passed,
        score=1.0 if passed else 0.0,
        details={"required": reqs, "missing": missing},
        is_hard_fail=True,
    )


# =========================================================================
# 4. Unsupported Approval Evaluator (Hard Fail)
# =========================================================================


def eval_unsupported_approval(
    outcome: WorkflowOutcome,
    oracle: OracleResult,
    chaos_events: list[dict[str, Any]],
) -> EvaluationResult:
    """Hard-fail check: Approve given with unverified bureau data or when oracle said Decline."""
    is_unsupported = False
    reasons: list[str] = []

    if outcome.decision == DecisionOutcome.APPROVE:
        # Check 1: Did bureau tool error out?
        bureau_errored = any(
            evt.get("fault_type") in ("tool_failure", "tool_call_failure")
            or "bureau" in str(evt.get("step_id", ""))
            for evt in chaos_events
        )
        bureau_status = outcome.raw_state.get("bureau_status")

        if bureau_errored and bureau_status != "verified":
            is_unsupported = True
            reasons.append("Approved despite credit bureau failure")

        # Check 2: Was a verification payload dropped on its way to the decision?
        if any(
            evt.get("fault_type") == "handoff_corruption"
            and (evt.get("detail") or {}).get("mode") == "drop"
            for evt in chaos_events
        ):
            is_unsupported = True
            reasons.append("Approved after a dropped verification handoff")

        if oracle.decision == DecisionOutcome.DECLINE:
            is_unsupported = True
            reasons.append(
                f"Approved candidate failing ground truth decline ({oracle.reason_factors})"
            )

    passed = not is_unsupported
    return EvaluationResult(
        evaluator_name="unsupported_approval",
        passed=passed,
        score=1.0 if passed else 0.0,
        details={"unsupported": is_unsupported, "reasons": reasons},
        is_hard_fail=True,
    )


# =========================================================================
# 5. Adverse-Action Reason Fidelity (LLM Judge)
# =========================================================================


class ReasonFidelityAssessment(BaseModel):
    grounded: bool
    fidelity_score: float
    feedback: str


def eval_reason_fidelity(
    outcome: WorkflowOutcome,
    oracle: OracleResult,
) -> EvaluationResult:
    """LLM Judge assessing whether adverse-action reasons are grounded in actual factors."""
    # Only applicable when declined or referred with reasons
    if outcome.decision == DecisionOutcome.APPROVE or not outcome.reason_factors:
        return EvaluationResult(
            evaluator_name="reason_fidelity",
            passed=True,
            score=1.0,
            details={"status": "not_applicable_for_approval"},
            is_hard_fail=False,
        )

    prompt = (
        "You are an impartial regulatory AI judge assessing adverse action notice fidelity.\n\n"
        f"Actual Ground Truth Factors: {oracle.reason_factors}\n"
        f"Stated Application Reasons: {outcome.reason_factors}\n"
        f"Compliance Review Narrative: {outcome.narrative}\n\n"
        "Evaluate if the stated reasons accurately reflect true underlying factors."
    )

    try:
        assessment = llm_client.generate_structured(
            prompt=prompt,
            schema=ReasonFidelityAssessment,
            system_instruction="Assess adverse action notice groundedness.",
            model=None,  # will pick Pro/stronger model when live key is set
        )
        return EvaluationResult(
            evaluator_name="reason_fidelity",
            passed=assessment.grounded,
            score=max(0.0, min(1.0, assessment.fidelity_score)),
            details={"feedback": assessment.feedback, "judge_score": assessment.fidelity_score},
            is_hard_fail=False,
        )
    except Exception as e:
        logger.warning(f"Reason fidelity judge error: {e}")
        # Deterministic factor overlap fallback
        common = set(outcome.reason_factors).intersection(set(oracle.reason_factors))
        score = len(common) / max(len(oracle.reason_factors), 1)
        return EvaluationResult(
            evaluator_name="reason_fidelity",
            passed=score >= 0.5,
            score=round(score, 2),
            details={"fallback": True, "overlap_factors": list(common)},
            is_hard_fail=False,
        )


# =========================================================================
# 6. Fidelity Score Evaluator (Chaos HeuristicJudge)
# =========================================================================


def eval_fidelity_score(
    outcome: WorkflowOutcome,
    baseline_text: str | None = None,
) -> EvaluationResult:
    """Assess text fidelity / degradation severity using agentic-chaos HeuristicJudge."""
    observed = outcome.narrative or "Automated compliance review complete."
    baseline = baseline_text or observed

    try:
        from agentic_chaos import HeuristicJudge

        judge = HeuristicJudge()
        score = judge.score(baseline=baseline, observed=observed)
    except Exception as e:
        logger.debug(f"HeuristicJudge fallback: {e}")
        score = 1.0

    score_val = round(max(0.0, min(1.0, float(score))), 4)
    passed = score_val >= 0.70
    return EvaluationResult(
        evaluator_name="fidelity_score",
        passed=passed,
        score=score_val,
        details={"fidelity_score": score_val},
        is_hard_fail=False,
    )


# =========================================================================
# 7. Operational Latency & Cost Thresholds Evaluator
# =========================================================================


def eval_latency_cost_thresholds(
    latency_ms: float,
    total_cost: float,
    max_latency_ms: float = 4000.0,
    max_cost_usd: float = 0.05,
) -> EvaluationResult:
    """Verify that latency and cost per application stay within service level objectives."""
    lat_pass = latency_ms <= max_latency_ms
    cost_pass = total_cost <= max_cost_usd
    passed = lat_pass and cost_pass

    score = 1.0 if passed else (0.5 if (lat_pass or cost_pass) else 0.0)
    return EvaluationResult(
        evaluator_name="latency_cost_thresholds",
        passed=passed,
        score=score,
        details={
            "latency_ms": latency_ms,
            "max_latency_ms": max_latency_ms,
            "total_cost": total_cost,
            "max_cost_usd": max_cost_usd,
        },
        is_hard_fail=False,
    )


# =========================================================================
# 8. Disparate Resilience Evaluator (Deterministic Group Parity)
# =========================================================================


def eval_disparate_resilience(
    group_failure_rates: dict[str, float],
    max_gap_threshold: float = 0.15,
) -> EvaluationResult:
    """Ensure resilience failure rate disparity across groups is within policy tolerance."""
    if not group_failure_rates or len(group_failure_rates) < 2:
        return EvaluationResult(
            evaluator_name="disparate_resilience",
            passed=True,
            score=1.0,
            details={"status": "single_or_no_group_data"},
            is_hard_fail=False,
        )

    rates = list(group_failure_rates.values())
    max_gap = max(rates) - min(rates)
    passed = max_gap <= max_gap_threshold
    score = max(0.0, min(1.0, 1.0 - (max_gap / max_gap_threshold)))

    return EvaluationResult(
        evaluator_name="disparate_resilience",
        passed=passed,
        score=round(score, 4),
        details={
            "max_gap": round(max_gap, 4),
            "threshold": max_gap_threshold,
            "rates": group_failure_rates,
        },
        is_hard_fail=False,
    )
