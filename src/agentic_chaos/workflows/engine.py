"""`ChaosWorkflow`: multi-stage chaos campaigns with gates between stages."""

import contextvars
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_chaos.agents.topology import get_active_tracker, reset_active_tracker
from agentic_chaos.chaos.context import get_active_session
from agentic_chaos.chaos.scope import Scope
from agentic_chaos.chaos.session import chaos_session
from agentic_chaos.contracts.base import ReportLike, check_contracts
from agentic_chaos.probes.base import Probe, ProbeResult
from agentic_chaos.probes.runner import check_probes, run_probes
from agentic_chaos.resilience.history import ResilienceHistory
from agentic_chaos.resilience.score import compute_resilience, validate_weights
from agentic_chaos.safety import CircuitBreaker
from agentic_chaos.workflows.nodes import (
    Approver,
    HealthCheck,
    Node,
    Parallel,
    Step,
    Suspend,
    Target,
    expand_nodes,
)
from agentic_chaos.workflows.report import (
    NodeKind,
    NodeResult,
    NodeStatus,
    WorkflowReport,
    WorkflowStatus,
    contract_line,
)

_OUTPUT_LIMIT = 500
# Most severe first: the terminal status a parallel block propagates.
_SEVERITY: tuple[WorkflowStatus, ...] = ("aborted", "halted", "rejected", "failed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _short(value: Any) -> str:
    try:
        text = repr(value)
    except Exception:  # pragma: no cover - defensive
        text = f"<unreprable {type(value).__name__}>"
    return text if len(text) <= _OUTPUT_LIMIT else text[: _OUTPUT_LIMIT - 3] + "..."


def _kind(node: Any) -> NodeKind:
    if isinstance(node, Step):
        return "step"
    if isinstance(node, HealthCheck):
        return "health_check"
    if isinstance(node, Parallel):
        return "parallel"
    return "suspend"


def _walk(nodes: Iterable[Any]) -> Iterable[Any]:
    for node in nodes:
        yield node
        if isinstance(node, Parallel):
            for branch in node.branches:
                yield from _walk(branch)


def _approver_from(approve: "Approver | Iterable[str] | bool | None") -> Approver | None:
    if approve is None or callable(approve):
        return approve
    if isinstance(approve, bool):
        decision = approve
        return lambda gate, report: decision
    if isinstance(approve, str):
        approve = [approve]
    names = set(approve)
    return lambda gate, report: True if gate.name in names else None


class ChaosWorkflow:
    """A named chaos campaign: steps, health-check gates, parallel blocks and suspends.

    ```python
    workflow = ChaosWorkflow("resilience-suite", steps=[
        Step("warm-up", faults=[RateLimitStormFault(burst_count=2)]),
        HealthCheck(fn=my_agent, query="Are you working?"),
        Step("escalate", faults=[cascade(first=RateLimitStormFault(burst_count=5),
                                          then=TokenTimeoutFault(hang_seconds=1))]),
    ])
    report = workflow.run(my_app)
    ```

    Steps run in order. By default the first failing step stops the workflow
    (`stop_on_failure=False` keeps going); a failing health check halts it.
    `scope` and `breaker` apply to every step that has none of its own
    (scopes intersect; a step breaker replaces the workflow breaker).

    `probes` (v0.9) run ``pre`` before the first node (a failure halts the
    workflow before any chaos), ``during`` inside every step's session after
    its target, and ``post`` after the last node. Every run is scored; see
    `agentic_chaos.resilience`. `weights` overrides the score's component weights.
    """

    def __init__(
        self,
        name: str,
        steps: Sequence[Node],
        *,
        target: Target | None = None,
        stop_on_failure: bool = True,
        breaker: CircuitBreaker | None = None,
        scope: Scope | None = None,
        probes: Sequence[Probe] = (),
        weights: Mapping[str, float] | None = None,
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("workflow name must be a non-empty string")
        if isinstance(steps, (str, bytes)) or not isinstance(steps, Sequence) or not steps:
            raise ValueError("a workflow needs at least one node")
        if target is not None and not callable(target):
            raise ValueError("workflow target must be callable")
        self.name = name
        self.target = target
        self.stop_on_failure = stop_on_failure
        self.breaker = breaker
        self.scope = scope
        self.probes = check_probes(probes)
        validate_weights(weights)
        self.weights = dict(weights) if weights is not None else None
        self.nodes = self._named(expand_nodes(list(steps)))

    @staticmethod
    def _named(nodes: list[Any]) -> list[Any]:
        counters = {"health-check": 0, "parallel": 0}

        def numbered(kind: str) -> str:
            counters[kind] += 1
            return f"{kind}-{counters[kind]}"

        def name(node: Any) -> Any:
            if isinstance(node, Parallel):
                if node.name is None:
                    node.name = numbered("parallel")
                node.branches = [[name(child) for child in branch] for branch in node.branches]
                return node
            if isinstance(node, HealthCheck) and node.name is None:
                return replace(node, name=numbered("health-check"))
            return node

        named = [name(node) for node in nodes]
        seen: set[str] = set()
        for node in _walk(named):
            if node.name in seen:
                raise ValueError(f"duplicate workflow node name '{node.name}'")
            seen.add(node.name)
        return named

    @property
    def node_names(self) -> list[str]:
        """Every node name, depth-first, as it will appear in the report."""
        return [node.name for node in _walk(self.nodes)]

    def run(
        self,
        target: Target | None = None,
        *,
        dry_run: bool = False,
        approve: "Approver | Iterable[str] | bool | None" = None,
        resume_from: str | None = None,
        experiment: dict[str, Any] | None = None,
        baseline: ReportLike | None = None,
        history: ResilienceHistory | str | Path | None = None,
    ) -> WorkflowReport:
        """Run the workflow and return its report; never raises for chaos outcomes.

        `approve` decides `Suspend` gates without their own approver: a
        callable ``(gate, report_so_far) -> True | False | None``, a set of
        gate names to approve, or True/False for every gate. `resume_from`
        skips everything up to and including the named top-level `Suspend`
        (treating that gate as approved). `dry_run=True` previews every step
        (targets and health checks still execute, as with all Chaos previews)
        and passes suspends without stopping. `baseline` (a fault-free report)
        enables the score's latency and cost components; `history` records the
        score of every finished (not suspended) run and adds its trend.
        """
        if get_active_session() is not None:
            raise RuntimeError("ChaosWorkflow.run() cannot run inside an active chaos_session()")
        default_target = target if target is not None else self.target
        if default_target is not None and not callable(default_target):
            raise ValueError("workflow target must be callable")
        for node in _walk(self.nodes):
            if isinstance(node, Step) and node.target is None and default_target is None:
                raise ValueError(f"step '{node.name}' has no target; pass one to run()")
            if isinstance(node, HealthCheck) and node.fn is None and default_target is None:
                raise ValueError(f"health check '{node.name}' has no fn and no workflow target")
        start = 0
        if resume_from is not None:
            gates = [i for i, n in enumerate(self.nodes) if isinstance(n, Suspend)]
            matches = [i for i in gates if self.nodes[i].name == resume_from]
            if not matches:
                known = ", ".join(self.nodes[i].name for i in gates) or "none"
                raise ValueError(
                    f"resume_from '{resume_from}' is not a top-level Suspend (gates: {known})"
                )
            start = matches[0] + 1
        run = _Run(
            self,
            default_target,
            dry_run=dry_run,
            approver=_approver_from(approve),
            experiment=experiment,
            baseline=baseline,
            history=ResilienceHistory(history) if isinstance(history, (str, Path)) else history,
        )
        return run.execute(start, resume_from)


class _Run:
    def __init__(
        self,
        workflow: ChaosWorkflow,
        target: Target | None,
        *,
        dry_run: bool,
        approver: Approver | None,
        experiment: dict[str, Any] | None,
        baseline: ReportLike | None = None,
        history: ResilienceHistory | None = None,
    ) -> None:
        self.workflow = workflow
        self.target = target
        self.dry_run = dry_run
        self.approver = approver
        self.experiment = experiment
        self.id = str(uuid.uuid4())
        self.started = _now()
        self.completed: list[NodeResult] = []
        self.baseline = baseline
        self.history = history
        self.probe_results: list[ProbeResult] = []
        self._probe_lock = threading.Lock()

    def snapshot(self, status: WorkflowStatus, **fields: Any) -> WorkflowReport:
        nodes = list(self.completed)
        events = [
            event
            for node in nodes
            for result in node.walk()
            if result.kind == "step" and result.report is not None
            for event in result.report.get("chaos_events", [])
        ]
        return WorkflowReport(
            id=self.id,
            name=self.workflow.name,
            status=status,
            start_time=self.started,
            end_time=fields.pop("end_time", None),
            dry_run=self.dry_run,
            nodes=nodes,
            chaos_events=events,
            experiment=self.experiment,
            **fields,
        )

    def execute(self, start: int, resume_from: str | None) -> WorkflowReport:
        self.probe_results.extend(run_probes(self.workflow.probes, "pre"))
        unsteady = sorted({r.probe for r in self.probe_results if not r.passed})
        if unsteady:
            for node in self.workflow.nodes:
                self.completed.append(self.skipped(node, "not run: pre-chaos probes failed"))
            return self.finish(
                self.snapshot(
                    "halted",
                    end_time=_now(),
                    resumed_from=resume_from,
                    message=f"pre-chaos probes failed ({', '.join(unsteady)}); no chaos injected",
                ),
                injected=False,
            )
        for node in self.workflow.nodes[:start]:
            resumed = node.name == resume_from
            self.completed.append(
                NodeResult(
                    name=node.name,
                    kind=_kind(node),
                    status="resumed" if resumed else "skipped",
                    message="approved by resume" if resumed else "before the resume point",
                )
            )
        terminal = self.sequence(self.workflow.nodes[start:], self.completed)
        status: WorkflowStatus
        if terminal is not None:
            status = terminal
        else:
            statuses = {result.status for result in self.snapshot("passed").walk()}
            status = (
                "aborted"
                if "aborted" in statuses
                else "failed"
                if "failed" in statuses
                else "passed"
            )
        fields: dict[str, Any] = {"end_time": _now(), "resumed_from": resume_from}
        suspended = [r for r in self.completed if r.status == "suspended"]
        if suspended:
            fields["suspended_at"] = suspended[0].name
            fields["message"] = (
                f"waiting for approval at '{suspended[0].name}'; "
                f"re-run with resume_from='{suspended[0].name}' once approved"
            )
        else:
            self.probe_results.extend(run_probes(self.workflow.probes, "post"))
        return self.finish(self.snapshot(status, **fields))

    def finish(self, report: WorkflowReport, *, injected: bool = True) -> WorkflowReport:
        """Attach probe results and the resilience score (recorded unless suspended)."""
        report.probes = [result.as_json() for result in self.probe_results]
        score = compute_resilience(
            report.to_chaos_report(), baseline=self.baseline, weights=self.workflow.weights
        )
        if not injected:
            score.reasons.append("chaos was not injected")
        if self.history is not None and report.status != "suspended":
            self.history.record(score)
        report.resilience = score.as_json()
        return report

    def sequence(self, nodes: Sequence[Any], results: list[NodeResult]) -> WorkflowStatus | None:
        """Run nodes in order into `results`; return a terminal status when stopping early."""
        for index, node in enumerate(nodes):
            result, terminal = self.node(node)
            results.append(result)
            if terminal is not None:
                for rest in nodes[index + 1 :]:
                    results.append(self.skipped(rest, f"not run: workflow {terminal}"))
                return terminal
        return None

    def skipped(self, node: Any, message: str) -> NodeResult:
        branches = (
            [[self.skipped(child, message) for child in branch] for branch in node.branches]
            if isinstance(node, Parallel)
            else []
        )
        return NodeResult(
            name=node.name, kind=_kind(node), status="skipped", message=message, branches=branches
        )

    def node(self, node: Any) -> tuple[NodeResult, WorkflowStatus | None]:
        if isinstance(node, Step):
            result = self.step(node)
            if result.status == "aborted":
                return result, "aborted"
            stop = result.status == "failed" and self.workflow.stop_on_failure
            return result, "failed" if stop else None
        if isinstance(node, HealthCheck):
            result = self.check(node)
            halt = result.status == "failed" and node.halt_on_failure
            return result, "halted" if halt else None
        if isinstance(node, Parallel):
            return self.parallel(node)
        return self.suspend(node)

    def step(self, step: Step) -> NodeResult:
        target = step.target if step.target is not None else self.target
        assert target is not None
        faults = step.fresh_faults(self.workflow.scope)
        breaker = step.breaker if step.breaker is not None else self.workflow.breaker
        crashed: BaseException | None = None
        reset_active_tracker()
        started = _now()
        clock = time.monotonic()
        with chaos_session(
            faults, breaker=breaker, dry_run=self.dry_run or step.dry_run
        ) as session:
            for _ in range(step.repeat):
                try:
                    target()
                except Exception as exc:
                    crashed = exc
                    break
            ended = _now()  # probe time is not part of the step's duration
            elapsed = time.monotonic() - clock
            during = run_probes(self.workflow.probes, "during", step=step.name)
        with self._probe_lock:
            self.probe_results.extend(during)
        tracker = get_active_tracker()
        topology = tracker.topology.as_json() if tracker and tracker.topology.nodes else None
        reset_active_tracker()
        report = session.to_report(
            f"{self.workflow.name}/{step.name}",
            end_time=ended,
            error=crashed,
            agent_topology=topology,
        )
        provenance = {"id": self.id, "name": self.workflow.name, "step": step.name}
        for event in report.chaos_events:
            event["detail"] = {**(event.get("detail") or {}), "workflow": provenance}
        contract_report = check_contracts(report, step.contracts) if step.contracts else None
        status: NodeStatus
        if report.aborted:
            status, message = "aborted", f"circuit breaker aborted the step: {report.abort_reason}"
        elif crashed is not None:
            status, message = "failed", f"target raised {type(crashed).__name__}: {crashed}"
        elif contract_report is not None and not contract_report.passed:
            status, message = "failed", contract_line(contract_report)
        else:
            status = "passed"
            message = f"{len(report.chaos_events)} fault event(s) over {step.repeat} run(s)"
            if contract_report is not None:
                message += f"; {contract_line(contract_report)}"
        return NodeResult(
            name=step.name,
            kind="step",
            status=status,
            message=message,
            started_at=started,
            ended_at=ended,
            duration_s=elapsed,
            faults=[fault.name for fault in faults],
            repeat=step.repeat,
            report=report.model_dump(mode="json"),
            contracts=contract_report.as_json() if contract_report is not None else None,
        )

    def check(self, check: HealthCheck) -> NodeResult:
        fn: Callable[..., Any] | None = check.fn if check.fn is not None else self.target
        assert fn is not None
        started = _now()
        clock = time.monotonic()
        attempts = 0
        passed, message, output = False, "", None
        while True:
            attempts += 1
            passed, message, output = self.attempt(check, fn)
            if passed or attempts > check.retries:
                break
            if check.retry_delay_seconds:
                time.sleep(check.retry_delay_seconds)
        return NodeResult(
            name=check.name or "health-check",
            kind="health_check",
            status="passed" if passed else "failed",
            message=message,
            started_at=started,
            ended_at=_now(),
            duration_s=time.monotonic() - clock,
            output=output,
            attempts=attempts,
        )

    @staticmethod
    def attempt(check: HealthCheck, fn: Callable[..., Any]) -> tuple[bool, str, str | None]:
        try:
            output = fn(check.query) if check.has_query else fn()
        except Exception as exc:
            if not check.expect_success:
                return True, f"raised {type(exc).__name__} as expected", None
            return False, f"raised {type(exc).__name__}: {exc}", None
        shown = _short(output)
        if not check.expect_success:
            return False, "returned normally; expected it to fail", shown
        if check.expect_contains is not None and check.expect_contains not in str(output):
            return False, f"output does not contain {check.expect_contains!r}", shown
        if check.expect is not None:
            try:
                accepted = bool(check.expect(output))
            except Exception as exc:
                return False, f"expect predicate raised {type(exc).__name__}: {exc}", shown
            if not accepted:
                return False, "expect predicate rejected the output", shown
        return True, "healthy", shown

    def parallel(self, node: Parallel) -> tuple[NodeResult, WorkflowStatus | None]:
        assert node.name is not None  # named when the workflow was defined
        branches = [list(branch) for branch in node.branches]
        started = _now()
        clock = time.monotonic()
        workers = node.max_workers or len(branches)

        def run_branch(branch: list[Any]) -> tuple[list[NodeResult], WorkflowStatus | None]:
            results: list[NodeResult] = []
            return results, self.sequence(branch, results)

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="chaos-workflow") as pool:
            # A fresh, empty context per branch: one chaos session (and tracker) each.
            futures = [
                pool.submit(contextvars.Context().run, run_branch, branch) for branch in branches
            ]
            outcomes = [future.result() for future in futures]
        terminals = [terminal for _, terminal in outcomes if terminal is not None]
        terminal = next((s for s in _SEVERITY if s in terminals), None)
        nested = {r.status for results, _ in outcomes for n in results for r in n.walk()}
        status: NodeStatus = (
            "aborted"
            if terminal == "aborted" or "aborted" in nested
            else "failed"
            if terminal is not None or "failed" in nested
            else "passed"
        )
        return (
            NodeResult(
                name=node.name,
                kind="parallel",
                status=status,
                message=f"{len(branches)} branches; {len(terminals)} stopped early",
                started_at=started,
                ended_at=_now(),
                duration_s=time.monotonic() - clock,
                branches=[results for results, _ in outcomes],
            ),
            terminal,
        )

    def suspend(self, gate: Suspend) -> tuple[NodeResult, WorkflowStatus | None]:
        started = _now()
        if self.dry_run:
            return (
                NodeResult(
                    name=gate.name,
                    kind="suspend",
                    status="would_suspend",
                    message="dry run: gate not enforced",
                    started_at=started,
                    ended_at=started,
                ),
                None,
            )
        approver = gate.approve if gate.approve is not None else self.approver
        decision = approver(gate, self.snapshot("suspended")) if approver is not None else None
        status: NodeStatus
        terminal: WorkflowStatus | None
        if decision is True:
            status, message, terminal = "approved", "approved", None
        elif decision is False:
            status, message, terminal = "rejected", "rejected by approver", "rejected"
        else:
            status, terminal = "suspended", "suspended"
            message = gate.reason or "waiting for approval"
        result = NodeResult(
            name=gate.name,
            kind="suspend",
            status=status,
            message=message,
            started_at=started,
            ended_at=_now(),
        )
        return result, terminal
