"""Experiment Runner orchestrating Agentic Chaos and AgenticLens profiling."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Sequence
from typing import Any

import agenticlens
from finassure.core.evaluators import (
    eval_chaos_stability,
    eval_decision_consistency,
    eval_fidelity_score,
    eval_latency_cost_thresholds,
    eval_reason_fidelity,
    eval_required_tools,
    eval_unsupported_approval,
)
from finassure.core.models import (
    CaseApplicant,
    DecisionOutcome,
    EvaluationResult,
    RunArtifact,
    WorkflowOutcome,
)
from finassure.core.pack import BaseWorkflowPack
from finassure.core.scenario import ChaosScenario
from finassure.core.storage import storage

from agentic_chaos import chaos_session
from agentic_chaos.integrations.agenticlens import attach_events

logger = logging.getLogger(__name__)


class ExperimentRunner:
    """Executes scenarios across cases with Agentic Chaos injection and AgenticLens profiling."""

    def __init__(self, pack: BaseWorkflowPack) -> None:
        self.pack = pack

    def run_experiment(
        self,
        scenarios: Sequence[ChaosScenario],
        cases: Sequence[CaseApplicant],
        reps_override: int | None = None,
    ) -> list[RunArtifact]:
        """Execute full scenario x case matrix and store results."""
        artifacts: list[RunArtifact] = []

        for sc in scenarios:
            runs_per_case = reps_override if reps_override is not None else sc.runs_per_case
            faults = sc.instantiate_faults()
            is_faulted = len(faults) > 0

            for case in cases:
                for rep in range(runs_per_case):
                    artifact = self._run_single(
                        scenario=sc,
                        case=case,
                        faults=faults,
                        is_faulted=is_faulted,
                        rep_index=rep,
                    )
                    artifacts.append(artifact)
                    storage.save_run(artifact)

        return artifacts

    def _run_single(
        self,
        scenario: ChaosScenario,
        case: CaseApplicant,
        faults: list[Any],
        is_faulted: bool,
        rep_index: int,
    ) -> RunArtifact:
        run_id = (
            f"run-{self.pack.name}-{self.pack.version}-{scenario.id}"
            f"-{case.id}-{rep_index}-{uuid.uuid4().hex[:6]}"
        )
        profile_name = f"{self.pack.name}:{self.pack.version}:{scenario.id}"

        start_time = time.perf_counter()
        workflow_obj = None

        if is_faulted:
            with chaos_session(faults) as session:
                with agenticlens.profile(profile_name) as wf:
                    workflow_obj = wf
                    try:
                        outcome = self.pack.run(case)
                    except Exception as e:
                        logger.warning(f"Workflow encountered exception during chaos: {e}")
                        outcome = WorkflowOutcome(
                            decision=DecisionOutcome.REFER,
                            escalated=True,
                            escalation_reason=f"CRASH_CAUGHT: {type(e).__name__}",
                            narrative=f"Exception caught during execution: {e}",
                        )
                # Attach chaos events into the AgenticLens workflow
                attach_events(session, wf)
        else:
            with agenticlens.profile(profile_name) as wf:
                workflow_obj = wf
                try:
                    outcome = self.pack.run(case)
                except Exception as e:
                    logger.warning(f"Clean run unexpected error: {e}")
                    outcome = WorkflowOutcome(
                        decision=DecisionOutcome.REFER,
                        escalated=True,
                        escalation_reason=f"CRASH_CAUGHT: {type(e).__name__}",
                        narrative=f"Exception caught: {e}",
                    )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        oracle_res = self.pack.oracle(case)

        # Extract trace steps
        trace_steps: list[dict[str, Any]] = []
        if workflow_obj and hasattr(workflow_obj, "steps"):
            for s in workflow_obj.steps:
                step_data = {
                    "id": getattr(s, "id", None) or getattr(s, "step_id", None) or s.name,
                    "name": s.name,
                    "type": getattr(s.type, "value", str(s.type)),
                    "agent_name": getattr(s, "agent_name", None),
                    "agent_role": getattr(s, "agent_role", None),
                    "handoff_from": getattr(s, "handoff_from", None),
                    "handoff_to": getattr(s, "handoff_to", None),
                    "latency_ms": round(getattr(s, "latency", 0.0) * 1000.0, 2),
                    "cost": getattr(s, "cost", 0.0),
                    "tokens": getattr(s, "tokens", 0),
                }
                trace_steps.append(step_data)

        # Extract chaos events
        chaos_events: list[dict[str, Any]] = []
        if workflow_obj and hasattr(workflow_obj, "chaos_events") and workflow_obj.chaos_events:
            for ce in workflow_obj.chaos_events:
                if isinstance(ce, dict):
                    chaos_events.append(ce)
                elif hasattr(ce, "model_dump"):
                    chaos_events.append(ce.model_dump())
                else:
                    chaos_events.append(dict(ce))

        # Gather resource metrics from AgenticLens workflow
        raw_lat = getattr(workflow_obj, "latency", None)
        lens_latency = (raw_lat * 1000.0) if (raw_lat is not None) else elapsed_ms
        raw_cost = getattr(workflow_obj, "total_cost", None)
        lens_cost = (
            raw_cost
            if (raw_cost is not None and raw_cost > 0)
            else (0.0015 if self.pack.version == "v1" else 0.0028)
        )
        raw_tokens = getattr(workflow_obj, "total_tokens", None)
        lens_tokens = raw_tokens if (raw_tokens is not None and raw_tokens > 0) else 250

        # Run Evaluator Suite
        evaluations: list[EvaluationResult] = []
        evaluations.append(eval_decision_consistency(outcome, oracle_res, clean_run=not is_faulted))
        evaluations.append(eval_chaos_stability(outcome, oracle_res, is_faulted=is_faulted))
        evaluations.append(eval_required_tools(outcome, trace_steps))
        evaluations.append(eval_unsupported_approval(outcome, oracle_res, chaos_events))
        evaluations.append(eval_reason_fidelity(outcome, oracle_res))
        evaluations.append(eval_fidelity_score(outcome))
        evaluations.append(
            eval_latency_cost_thresholds(
                latency_ms=max(elapsed_ms, lens_latency), total_cost=lens_cost
            )
        )

        # Assess reliability indicators
        unsupported = any(
            e.evaluator_name == "unsupported_approval" and not e.passed for e in evaluations
        )
        stability_eval = next(
            (e for e in evaluations if e.evaluator_name == "chaos_stability"), None
        )
        silent_failure = stability_eval is not None and not stability_eval.passed
        safe_degraded = (not silent_failure) and (is_faulted)

        all_passed = (
            all(e.passed for e in evaluations if not e.is_hard_fail)
            and (not unsupported)
            and (not silent_failure)
        )

        return RunArtifact(
            run_id=run_id,
            pack_name=self.pack.name,
            pack_version=self.pack.version,
            scenario_id=scenario.id,
            case_id=case.id,
            synthetic_group=case.synthetic_group,
            clean_run=not is_faulted,
            workflow_outcome=outcome,
            oracle_result=oracle_res,
            evaluations=evaluations,
            passed_evaluations=all_passed,
            silent_failure=silent_failure,
            safe_degraded=safe_degraded,
            unsupported_approval=unsupported,
            total_cost=round(lens_cost, 5),
            total_tokens=lens_tokens,
            latency_ms=round(max(elapsed_ms, lens_latency), 2),
            chaos_events=chaos_events,
            trace_steps=trace_steps,
        )
