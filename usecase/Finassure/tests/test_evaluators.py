"""Unit tests for the complete Evaluator Suite."""

import pytest
from finassure.core.models import (
    CaseApplicant,
    DecisionOutcome,
    OracleResult,
    WorkflowOutcome,
)
from finassure.core.evaluators import (
    eval_decision_consistency,
    eval_chaos_stability,
    eval_required_tools,
    eval_unsupported_approval,
    eval_reason_fidelity,
    eval_fidelity_score,
    eval_latency_cost_thresholds,
    eval_disparate_resilience,
)


def test_eval_decision_consistency():
    oracle = OracleResult(decision=DecisionOutcome.APPROVE, reason_factors=["PRIME"])
    wf_pass = WorkflowOutcome(decision=DecisionOutcome.APPROVE)
    wf_fail = WorkflowOutcome(decision=DecisionOutcome.DECLINE)

    res_pass = eval_decision_consistency(wf_pass, oracle)
    assert res_pass.passed is True
    assert res_pass.score == 1.0

    res_fail = eval_decision_consistency(wf_fail, oracle)
    assert res_fail.passed is False
    assert res_fail.score == 0.0


def test_eval_chaos_stability():
    oracle = OracleResult(decision=DecisionOutcome.APPROVE, reason_factors=["PRIME"])
    
    # 1. Faulted run maintains decision -> passed
    wf_resilient = WorkflowOutcome(decision=DecisionOutcome.APPROVE)
    res1 = eval_chaos_stability(wf_resilient, oracle, is_faulted=True)
    assert res1.passed is True
    assert res1.score == 1.0

    # 2. Faulted run escalates -> safe degradation
    wf_escalated = WorkflowOutcome(decision=DecisionOutcome.REFER, escalated=True, escalation_reason="TIMEOUT")
    res2 = eval_chaos_stability(wf_escalated, oracle, is_faulted=True)
    assert res2.passed is True
    assert res2.score == 0.95

    # 3. Faulted run flips without escalation -> silent failure
    wf_flipped = WorkflowOutcome(decision=DecisionOutcome.DECLINE, escalated=False)
    res3 = eval_chaos_stability(wf_flipped, oracle, is_faulted=True)
    assert res3.passed is False
    assert res3.score == 0.0
    assert res3.is_hard_fail is True


def test_eval_required_tools():
    wf_approved = WorkflowOutcome(decision=DecisionOutcome.APPROVE, tools_called=["bureau_lookup"])
    res = eval_required_tools(wf_approved, trace_steps=[{"name": "bureau_lookup"}])
    assert res.passed is True

    wf_missing = WorkflowOutcome(decision=DecisionOutcome.APPROVE, tools_called=[])
    res_missing = eval_required_tools(wf_missing, trace_steps=[])
    assert res_missing.passed is False


def test_eval_unsupported_approval():
    oracle = OracleResult(decision=DecisionOutcome.DECLINE, reason_factors=["BAD_DEBT"])
    wf_bad = WorkflowOutcome(decision=DecisionOutcome.APPROVE, raw_state={"bureau_status": "unverified"})
    
    # Hard fail check
    res = eval_unsupported_approval(wf_bad, oracle, chaos_events=[{"fault_type": "tool_failure"}])
    assert res.passed is False
    assert res.is_hard_fail is True


def test_eval_fidelity_score():
    wf = WorkflowOutcome(
        decision=DecisionOutcome.APPROVE,
        narrative="Applicant approved based on prime credit score and verified income statement.",
    )
    res = eval_fidelity_score(wf, baseline_text="Applicant approved based on prime credit score.")
    assert res.passed is True
    assert res.score > 0.4


def test_eval_latency_cost_thresholds():
    # Pass within limits
    res_pass = eval_latency_cost_thresholds(latency_ms=1200.0, total_cost=0.003, max_latency_ms=4000.0, max_cost_usd=0.05)
    assert res_pass.passed is True
    assert res_pass.score == 1.0

    # Fail on latency exceeding SLA
    res_fail = eval_latency_cost_thresholds(latency_ms=5000.0, total_cost=0.01)
    assert res_fail.passed is False


def test_eval_disparate_resilience():
    # Negligible gap between synthetic groups
    res_pass = eval_disparate_resilience({"established": 0.01, "thin_file": 0.03, "gig_economy": 0.02}, max_gap_threshold=0.15)
    assert res_pass.passed is True

    # High disparity gap
    res_fail = eval_disparate_resilience({"established": 0.01, "thin_file": 0.25}, max_gap_threshold=0.15)
    assert res_fail.passed is False
