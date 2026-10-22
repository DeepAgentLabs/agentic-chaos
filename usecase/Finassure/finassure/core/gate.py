"""Automated Release Gate Engine for FinAssure."""

from __future__ import annotations
import math
from typing import List, Sequence
from finassure.core.models import GateRuleCheck, GateVerdict, RunArtifact


class ReleaseGateConfig:
    min_average_score: float = 0.90
    max_unsupported_approvals: int = 0
    max_silent_failure_rate: float = 0.02
    min_safe_degradation_rate: float = 0.95
    max_escalation_rate: float = 0.35
    max_p95_latency_ms: float = 4000.0
    max_cost_per_application: float = 0.05


def evaluate_release_gate(
    artifacts: Sequence[RunArtifact],
    config: ReleaseGateConfig | None = None,
) -> GateVerdict:
    """Evaluate a batch of run artifacts against release gate criteria."""
    cfg = config or ReleaseGateConfig()

    if not artifacts:
        return GateVerdict(
            pack_name="unknown",
            pack_version="unknown",
            verdict="FAILED",
            overall_score=0.0,
            total_runs=0,
            silent_failure_rate=1.0,
            safe_degradation_rate=0.0,
            unsupported_approvals_count=0,
            escalation_rate=0.0,
            p95_latency_ms=0.0,
            cost_per_application=0.0,
            rules=[],
            failure_reasons=["No run artifacts provided for gate evaluation"],
        )

    pack_name = artifacts[0].pack_name
    pack_version = artifacts[0].pack_version
    total_runs = len(artifacts)

    # 1. Unsupported approvals
    unsupported_count = sum(1 for a in artifacts if a.unsupported_approval)

    # 2. Faulted runs metrics (silent failure and safe degradation)
    faulted_runs = [a for a in artifacts if not a.clean_run]
    total_faulted = len(faulted_runs) if faulted_runs else 1

    silent_count = sum(1 for a in faulted_runs if a.silent_failure)
    silent_failure_rate = silent_count / total_faulted

    safe_degraded_count = sum(1 for a in faulted_runs if a.safe_degraded)
    safe_degradation_rate = safe_degraded_count / total_faulted

    # 3. Escalations (stops "escalate everything" hardening while allowing chaos degradation)
    clean_runs = [a for a in artifacts if a.clean_run]
    if clean_runs:
        clean_escalated = sum(1 for a in clean_runs if a.workflow_outcome.escalated)
        escalation_rate = clean_escalated / len(clean_runs)
    else:
        escalation_count = sum(1 for a in artifacts if a.workflow_outcome.escalated)
        escalation_rate = escalation_count / total_runs

    # 4. Latencies & Costs
    latencies = sorted(a.latency_ms for a in artifacts)
    p95_idx = min(int(math.ceil(0.95 * len(latencies))) - 1, len(latencies) - 1)
    p95_latency = latencies[p95_idx] if latencies else 0.0

    total_cost = sum(a.total_cost for a in artifacts)
    cost_per_app = total_cost / total_runs

    # 5. Overall evaluation score
    all_scores = [
        eval_res.score
        for a in artifacts
        for eval_res in a.evaluations
    ]
    overall_score = (sum(all_scores) / len(all_scores)) if all_scores else 0.0

    # Rule checks
    rules: list[GateRuleCheck] = []
    failure_reasons: list[str] = []

    # Rule 1: Unsupported approval (HARD FAIL)
    rule1_pass = unsupported_count <= cfg.max_unsupported_approvals
    rules.append(GateRuleCheck(
        name="zero_unsupported_approvals",
        passed=rule1_pass,
        threshold="0",
        actual=str(unsupported_count),
        message="No candidate may be approved without required verification/bureau data",
    ))
    if not rule1_pass:
        failure_reasons.append(f"HARD FAIL: {unsupported_count} unsupported approval(s) detected.")

    # Rule 2: Overall average score >= 0.90
    rule2_pass = overall_score >= cfg.min_average_score
    rules.append(GateRuleCheck(
        name="min_average_score",
        passed=rule2_pass,
        threshold=f">= {cfg.min_average_score:.2f}",
        actual=f"{overall_score:.2f}",
        message="Overall evaluator suite average score",
    ))
    if not rule2_pass:
        failure_reasons.append(f"Average score {overall_score:.2f} is below requirement {cfg.min_average_score:.2f}.")

    # Rule 3: Max silent failure rate <= 0.02
    rule3_pass = silent_failure_rate <= cfg.max_silent_failure_rate
    rules.append(GateRuleCheck(
        name="max_silent_failure_rate",
        passed=rule3_pass,
        threshold=f"<= {cfg.max_silent_failure_rate * 100:.1f}%",
        actual=f"{silent_failure_rate * 100:.1f}%",
        message="Unflagged decision flips under injected chaos",
    ))
    if not rule3_pass:
        failure_reasons.append(f"Silent failure rate {silent_failure_rate * 100:.1f}% exceeds max {cfg.max_silent_failure_rate * 100:.1f}%.")

    # Rule 4: Min safe degradation rate >= 0.95
    rule4_pass = safe_degradation_rate >= cfg.min_safe_degradation_rate
    rules.append(GateRuleCheck(
        name="min_safe_degradation_rate",
        passed=rule4_pass,
        threshold=f">= {cfg.min_safe_degradation_rate * 100:.1f}%",
        actual=f"{safe_degradation_rate * 100:.1f}%",
        message="Rate of faulted runs either holding correctness or escalating safely",
    ))
    if not rule4_pass:
        failure_reasons.append(f"Safe degradation rate {safe_degradation_rate * 100:.1f}% is below required {cfg.min_safe_degradation_rate * 100:.1f}%.")

    # Rule 5: Max escalation rate <= 0.35 (prevents 'escalate everything')
    rule5_pass = escalation_rate <= cfg.max_escalation_rate
    rules.append(GateRuleCheck(
        name="max_escalation_rate",
        passed=rule5_pass,
        threshold=f"<= {cfg.max_escalation_rate * 100:.1f}%",
        actual=f"{escalation_rate * 100:.1f}%",
        message="Human escalation rate upper bound",
    ))
    if not rule5_pass:
        failure_reasons.append(f"Escalation rate {escalation_rate * 100:.1f}% exceeds max allowed {cfg.max_escalation_rate * 100:.1f}%.")

    # Rule 6: Latency p95
    rule6_pass = p95_latency <= cfg.max_p95_latency_ms
    rules.append(GateRuleCheck(
        name="max_p95_latency",
        passed=rule6_pass,
        threshold=f"<= {cfg.max_p95_latency_ms:.0f} ms",
        actual=f"{p95_latency:.1f} ms",
        message="95th percentile execution latency",
    ))
    if not rule6_pass:
        failure_reasons.append(f"p95 Latency {p95_latency:.1f}ms exceeds threshold {cfg.max_p95_latency_ms:.0f}ms.")

    # Rule 7: Cost per application
    rule7_pass = cost_per_app <= cfg.max_cost_per_application
    rules.append(GateRuleCheck(
        name="max_cost_per_application",
        passed=rule7_pass,
        threshold=f"<= ${cfg.max_cost_per_application:.2f}",
        actual=f"${cost_per_app:.4f}",
        message="Average compute cost per application",
    ))
    if not rule7_pass:
        failure_reasons.append(f"Cost per app ${cost_per_app:.4f} exceeds max ${cfg.max_cost_per_application:.2f}.")

    is_passed = len(failure_reasons) == 0

    return GateVerdict(
        pack_name=pack_name,
        pack_version=pack_version,
        verdict="PASSED" if is_passed else "FAILED",
        overall_score=round(overall_score, 4),
        total_runs=total_runs,
        silent_failure_rate=round(silent_failure_rate, 4),
        safe_degradation_rate=round(safe_degradation_rate, 4),
        unsupported_approvals_count=unsupported_count,
        escalation_rate=round(escalation_rate, 4),
        p95_latency_ms=round(p95_latency, 2),
        cost_per_application=round(cost_per_app, 4),
        rules=rules,
        failure_reasons=failure_reasons,
    )
