"""Core domain models for FinAssure."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DecisionOutcome(str, Enum):
    APPROVE = "approve"
    REFER = "refer"  # Escalate to human review
    DECLINE = "decline"


class CaseApplicant(BaseModel):
    """Synthetic applicant case for testing workflows."""

    id: str
    name: str
    ssn: str
    stated_annual_income: float
    monthly_debt: float
    requested_amount: float
    loan_purpose: str
    credit_score: int
    employer: str
    employment_years: float
    documents_text: str
    bank_statement_monthly_deposits: float
    synthetic_group: str = "established"  # e.g. "established", "thin_file", "gig_economy"
    expected_decision: DecisionOutcome | None = None
    expected_factors: list[str] = Field(default_factory=list)


class OracleResult(BaseModel):
    """Ground truth answer computed deterministically."""

    decision: DecisionOutcome
    reason_factors: list[str]
    policy_version: str = "1.0.0"
    metrics: dict[str, Any] = Field(default_factory=dict)


class WorkflowOutcome(BaseModel):
    """Standardized result produced by any workflow pack execution."""

    decision: DecisionOutcome
    reason_factors: list[str] = Field(default_factory=list)
    narrative: str = ""
    risk_score: float | None = None
    dti: float | None = None
    escalated: bool = False
    escalation_reason: str | None = None
    tools_called: list[str] = Field(default_factory=list)
    raw_state: dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    """Output from an evaluator check."""

    evaluator_name: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    details: dict[str, Any] = Field(default_factory=dict)
    is_hard_fail: bool = False


class RunArtifact(BaseModel):
    """Complete record of a single scenario x case x repetition run."""

    run_id: str
    pack_name: str
    pack_version: str  # "v1" or "v2"
    scenario_id: str
    case_id: str
    synthetic_group: str = "established"
    clean_run: bool = False
    workflow_outcome: WorkflowOutcome
    oracle_result: OracleResult
    evaluations: list[EvaluationResult] = Field(default_factory=list)

    # Reliability indicators
    passed_evaluations: bool = True
    silent_failure: bool = False
    safe_degraded: bool = True
    unsupported_approval: bool = False

    # Resource metrics
    total_cost: float = 0.0
    total_tokens: int = 0
    latency_ms: float = 0.0

    # Tracing & Chaos
    chaos_events: list[dict[str, Any]] = Field(default_factory=list)
    trace_steps: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GateRuleCheck(BaseModel):
    name: str
    passed: bool
    threshold: str
    actual: str
    message: str


class GateVerdict(BaseModel):
    """Summary verdict emitted by the Release Gate engine."""

    pack_name: str
    pack_version: str
    verdict: str  # "PASSED" | "FAILED"
    overall_score: float
    total_runs: int
    silent_failure_rate: float
    safe_degradation_rate: float
    unsupported_approvals_count: int
    escalation_rate: float
    p95_latency_ms: float
    cost_per_application: float
    rules: list[GateRuleCheck] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
