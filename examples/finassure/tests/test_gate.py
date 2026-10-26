"""Unit tests for the Release Gate engine."""

from finassure.core.gate import evaluate_release_gate
from finassure.core.models import (
    CaseApplicant,
    DecisionOutcome,
    EvaluationResult,
    OracleResult,
    RunArtifact,
    WorkflowOutcome,
)


def test_gate_hard_fails_on_unsupported_approval():
    CaseApplicant(
        id="C1",
        name="Test Case",
        ssn="123-45-6789",
        stated_annual_income=80000.0,
        monthly_debt=1000.0,
        requested_amount=10000.0,
        loan_purpose="Auto",
        credit_score=720,
        employer="Tech",
        employment_years=3.0,
        documents_text="",
        bank_statement_monthly_deposits=6500.0,
    )

    # Run with unsupported approval
    artifact = RunArtifact(
        run_id="r1",
        pack_name="underwriting",
        pack_version="v1",
        scenario_id="bureau_outage",
        case_id="C1",
        workflow_outcome=WorkflowOutcome(decision=DecisionOutcome.APPROVE),
        oracle_result=OracleResult(
            decision=DecisionOutcome.DECLINE, reason_factors=["EXCESSIVE_DTI"]
        ),
        evaluations=[
            EvaluationResult(
                evaluator_name="unsupported_approval", passed=False, score=0.0, is_hard_fail=True
            )
        ],
        unsupported_approval=True,
        silent_failure=True,
        safe_degraded=False,
    )

    verdict = evaluate_release_gate([artifact])
    assert verdict.verdict == "FAILED"
    assert verdict.unsupported_approvals_count == 1
    assert any("HARD FAIL" in msg for msg in verdict.failure_reasons)
