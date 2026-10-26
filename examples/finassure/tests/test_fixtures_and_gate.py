"""Unit tests for Known-Good and Known-Bad workflow fixtures, degrade functions, and gate logic."""

from finassure.core.gate import evaluate_release_gate
from finassure.core.models import (
    DecisionOutcome,
    EvaluationResult,
    OracleResult,
    RunArtifact,
    WorkflowOutcome,
)
from finassure.core.scenario import ChaosScenario


def test_degrade_functions_behavior():
    """Verify degrade functions implemented in ChaosScenario."""
    # halve
    sc_halve = ChaosScenario(
        id="sc_halve",
        name="Halve Test",
        pack="underwriting",
        fault_type="silent_degradation",
        target="income",
        params={"corruption": "halve"},
        hypothesis="test",
    )
    faults = sc_halve.instantiate_faults()
    assert len(faults) == 1
    degrade_fn = faults[0].degrade_fn
    assert degrade_fn(100000.0) == 50000.0

    # drop_digit
    sc_digit = ChaosScenario(
        id="sc_digit",
        name="Drop Digit Test",
        pack="underwriting",
        fault_type="silent_degradation",
        target="income",
        params={"corruption": "drop_digit"},
        hypothesis="test",
    )
    faults_digit = sc_digit.instantiate_faults()
    assert faults_digit[0].degrade_fn(100000.0) == 10000.0


def test_known_bad_workflow_fixture_must_fail_gate():
    """Known-bad workflow fixture: systematically generates unsupported approvals and silent flips.
    Must ALWAYS fail the gate with specific reasons."""
    bad_artifacts = []
    for i in range(10):
        art = RunArtifact(
            run_id=f"bad-run-{i}",
            pack_name="fixture_pack",
            pack_version="known_bad",
            scenario_id="bureau_outage",
            case_id=f"CASE-{i}",
            clean_run=False,
            workflow_outcome=WorkflowOutcome(
                decision=DecisionOutcome.APPROVE,
                reason_factors=["DEFAULTED_SCORE"],
                tools_called=[],
            ),
            oracle_result=OracleResult(
                decision=DecisionOutcome.DECLINE,
                reason_factors=["SUBPRIME_CREDIT"],
            ),
            evaluations=[
                EvaluationResult(
                    evaluator_name="unsupported_approval",
                    passed=False,
                    score=0.0,
                    is_hard_fail=True,
                ),
                EvaluationResult(
                    evaluator_name="chaos_stability", passed=False, score=0.0, is_hard_fail=True
                ),
                EvaluationResult(
                    evaluator_name="decision_consistency",
                    passed=False,
                    score=0.0,
                    is_hard_fail=False,
                ),
            ],
            unsupported_approval=True,
            silent_failure=True,
            safe_degraded=False,
            total_cost=0.002,
            latency_ms=120.0,
        )
        bad_artifacts.append(art)

    verdict = evaluate_release_gate(bad_artifacts)
    assert verdict.verdict == "FAILED"
    assert verdict.unsupported_approvals_count == 10
    assert verdict.silent_failure_rate == 1.0
    assert len(verdict.failure_reasons) >= 2
    assert any("HARD FAIL" in r for r in verdict.failure_reasons)


def test_known_good_workflow_fixture_must_pass_gate():
    """Known-good workflow fixture: flawless adherence to oracle and safe escalation.

    Must ALWAYS pass the gate.
    """
    good_artifacts = []
    # 5 clean runs
    for i in range(5):
        art = RunArtifact(
            run_id=f"good-clean-{i}",
            pack_name="fixture_pack",
            pack_version="known_good",
            scenario_id="clean_baseline",
            case_id=f"CASE-{i}",
            clean_run=True,
            workflow_outcome=WorkflowOutcome(
                decision=DecisionOutcome.APPROVE,
                reason_factors=["PRIME_CREDIT_PROFILE"],
                tools_called=["bureau_lookup"],
            ),
            oracle_result=OracleResult(
                decision=DecisionOutcome.APPROVE,
                reason_factors=["PRIME_CREDIT_PROFILE"],
            ),
            evaluations=[
                EvaluationResult(evaluator_name="decision_consistency", passed=True, score=1.0),
                EvaluationResult(evaluator_name="chaos_stability", passed=True, score=1.0),
                EvaluationResult(evaluator_name="required_tools_called", passed=True, score=1.0),
                EvaluationResult(evaluator_name="unsupported_approval", passed=True, score=1.0),
                EvaluationResult(evaluator_name="reason_fidelity", passed=True, score=0.98),
            ],
            unsupported_approval=False,
            silent_failure=False,
            safe_degraded=False,
            total_cost=0.002,
            latency_ms=150.0,
        )
        good_artifacts.append(art)

    # 10 faulted runs: 6 maintain correctness and 4 escalate safely (within 35% cap)
    for i in range(10):
        escalates = i < 4
        art = RunArtifact(
            run_id=f"good-faulted-{i}",
            pack_name="fixture_pack",
            pack_version="known_good",
            scenario_id="bureau_outage",
            case_id=f"CASE-{i + 5}",
            clean_run=False,
            workflow_outcome=WorkflowOutcome(
                decision=DecisionOutcome.REFER if escalates else DecisionOutcome.APPROVE,
                reason_factors=["UNVERIFIED_CREDIT_BUREAU_DATA"]
                if escalates
                else ["PRIME_CREDIT_PROFILE"],
                escalated=escalates,
                escalation_reason="BUREAU_SERVICE_UNAVAILABLE" if escalates else None,
                tools_called=["bureau_lookup"],
            ),
            oracle_result=OracleResult(
                decision=DecisionOutcome.APPROVE,
                reason_factors=["PRIME_CREDIT_PROFILE"],
            ),
            evaluations=[
                EvaluationResult(
                    evaluator_name="decision_consistency",
                    passed=not escalates,
                    score=1.0 if not escalates else 0.0,
                ),
                EvaluationResult(
                    evaluator_name="chaos_stability", passed=True, score=0.95 if escalates else 1.0
                ),
                EvaluationResult(evaluator_name="required_tools_called", passed=True, score=1.0),
                EvaluationResult(evaluator_name="unsupported_approval", passed=True, score=1.0),
                EvaluationResult(evaluator_name="reason_fidelity", passed=True, score=0.95),
            ],
            unsupported_approval=False,
            silent_failure=False,
            safe_degraded=True,
            total_cost=0.0025,
            latency_ms=200.0,
        )
        good_artifacts.append(art)

    verdict = evaluate_release_gate(good_artifacts)
    assert verdict.verdict == "PASSED"
    assert verdict.unsupported_approvals_count == 0
    assert verdict.silent_failure_rate == 0.0
    assert verdict.safe_degradation_rate == 1.0
    assert verdict.escalation_rate <= 0.35
    assert len(verdict.failure_reasons) == 0
