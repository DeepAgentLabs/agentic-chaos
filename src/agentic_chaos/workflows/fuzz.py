"""Topology fuzzer: place one fault per trial, weighted by agent-graph structure.

Unlike a fixed workflow, `fuzz_topology()` explores. Each trial picks a node of
the recorded `AgentTopology` (weighted by fan-out, so coordinators that call
many others are hit more often than leaf tools), picks a fault suited to that
node's type, scopes the fault to exactly that node and runs the target once.
It complements `find_breaking_point()`, which searches one parameter.
"""

import json
import random
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentic_chaos.agents.topology import TopologyTracker, get_active_tracker, reset_active_tracker
from agentic_chaos.chaos.context import get_active_session
from agentic_chaos.chaos.faults import FAULT_REGISTRY, BaseFault
from agentic_chaos.chaos.scope import Scope
from agentic_chaos.chaos.session import chaos_session
from agentic_chaos.contracts.base import Contract, check_contracts
from agentic_chaos.models.agent_topology import AgentNode, AgentTopology
from agentic_chaos.models.report import ChaosReport
from agentic_chaos.safety import CircuitBreaker

FaultFactory = str | Callable[[], BaseFault]
FaultPool = Sequence[FaultFactory] | Mapping[str, Sequence[FaultFactory]]
TopologySource = AgentTopology | TopologyTracker | ChaosReport | Mapping[str, Any] | str | Path

# Node type -> default faults. "*" covers types without their own entry.
DEFAULT_FAULTS: dict[str, tuple[str, ...]] = {
    "tool": ("tool_failure",),
    "memory": ("memory_corruption",),
    "agent": ("rate_limit_storm", "silent_degradation"),
    "router": ("rate_limit_storm", "silent_degradation"),
    "*": ("rate_limit_storm",),
}


class FuzzTrial(BaseModel):
    index: int
    node: str
    node_type: str
    weight: float
    fault_type: str
    reached: bool
    passed: bool
    message: str
    duration_s: float
    report: dict[str, Any] | None = None
    contracts: dict[str, Any] | None = None


class FuzzNodeSummary(BaseModel):
    node: str
    node_type: str
    weight: float
    trials: int = 0
    failures: int = 0
    not_reached: int = 0


class FuzzReport(BaseModel):
    kind: str = "topology_fuzz"
    seed: int | None
    n: int
    start_time: datetime
    end_time: datetime | None = None
    scope: dict[str, Any] | None = None
    nodes: list[FuzzNodeSummary] = Field(default_factory=list)
    trials: list[FuzzTrial] = Field(default_factory=list)

    @property
    def failures(self) -> list[FuzzTrial]:
        return [trial for trial in self.trials if trial.reached and not trial.passed]

    @property
    def failing_nodes(self) -> list[str]:
        """Nodes with at least one failing reached trial, most failures first."""
        ranked = sorted(
            (node for node in self.nodes if node.failures), key=lambda n: (-n.failures, n.node)
        )
        return [node.node for node in ranked]

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return destination


def _topology(source: TopologySource) -> AgentTopology:
    if isinstance(source, AgentTopology):
        return source
    if isinstance(source, TopologyTracker):
        return source.topology
    data: Any
    if isinstance(source, ChaosReport):
        data = source.agent_topology
    else:
        loaded: Any = (
            json.loads(Path(source).read_text(encoding="utf-8"))
            if isinstance(source, (str, Path))
            else source
        )
        if not isinstance(loaded, Mapping):
            raise ValueError("topology must be an AgentTopology, tracker, report or mapping")
        data = loaded.get("agent_topology", loaded)
    if not data:
        raise ValueError("the report has no agent_topology to fuzz")
    return AgentTopology.model_validate(data)


def topology_weights(topology: AgentTopology) -> dict[str, float]:
    """Fan-out weight per node: 1 + the number of distinct nodes it sends to."""
    names = {node.id: node.name for node in topology.nodes}
    successors: dict[str, set[str]] = {node.name: set() for node in topology.nodes}
    for edge in topology.edges:
        source, target = names.get(edge.source_id), names.get(edge.target_id)
        if source is not None and target is not None and source != target:
            successors[source].add(target)
    return {name: 1.0 + len(targets) for name, targets in successors.items()}


def _baseline(target: Callable[[], Any]) -> tuple[AgentTopology, set[str]]:
    """Run once without faults; return its topology and the step names it called."""
    reset_active_tracker()
    with chaos_session([]) as session:
        try:
            target()
        except Exception as exc:
            raise ValueError(
                f"the fault-free baseline run failed ({type(exc).__name__}: {exc}); "
                "fuzzing needs a healthy steady state"
            ) from exc
    tracker = get_active_tracker()
    reset_active_tracker()
    called = {record["step_name"] for record in session.calls.as_json() if record["step_name"]}
    if tracker is not None and tracker.topology.nodes:
        return tracker.topology, called
    nodes = [AgentNode(name=name, type="step") for name in sorted(called)]
    return AgentTopology(nodes=nodes), called


def _factories(pool: FaultPool | None, node_type: str) -> list[FaultFactory]:
    if pool is None:
        return list(DEFAULT_FAULTS.get(node_type, DEFAULT_FAULTS["*"]))
    if isinstance(pool, Mapping):
        chosen = pool.get(node_type, pool.get("*"))
        return list(chosen) if chosen else []
    return list(pool)


def _build(factory: FaultFactory) -> BaseFault:
    if isinstance(factory, str):
        if factory not in FAULT_REGISTRY:
            known = ", ".join(sorted(FAULT_REGISTRY))
            raise ValueError(f"Unknown fault '{factory}'. Known faults: {known}")
        fault = FAULT_REGISTRY[factory]()
    else:
        fault = factory()
    if not isinstance(fault, BaseFault):
        raise ValueError(f"fault factory {factory!r} did not return a BaseFault")
    return fault


def fuzz_topology(
    target: Callable[[], Any],
    *,
    n: int = 20,
    topology: TopologySource | None = None,
    faults: FaultPool | None = None,
    scope: Scope | None = None,
    seed: int | None = 0,
    recovered: Callable[[Any], bool] | None = None,
    contracts: Sequence[Contract] = (),
    breaker: CircuitBreaker | None = None,
) -> FuzzReport:
    """Run `n` single-fault trials placed on the topology by fan-out weight.

    Without `topology`, one fault-free baseline run discovers it (from the
    `TopologyTracker` the target creates, else from the step names it calls)
    and only nodes that baseline actually called are candidates. `scope`
    removes nodes (`exclude_steps`) or restricts them (`steps`). `faults` is a
    list of fault names/factories for every node, or a mapping from node type
    to such a list (``"*"`` for the rest); see `DEFAULT_FAULTS`.

    A trial passes when the target returns, `recovered(output)` (if given)
    accepts the output and every contract passes. A trial whose fault never
    fired is `reached=False` (for example, a node that is only a caller label
    with no wrapped call site). Targets must not pin `faults=[...]` at call
    sites to names outside the pool, and must reset their own external state
    per invocation. The same seed gives the same placements.
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("n must be a positive integer")
    if get_active_session() is not None:
        raise RuntimeError("fuzz_topology() cannot run inside an active chaos_session()")
    started = datetime.now(timezone.utc)
    called: set[str] | None = None
    if topology is None:
        graph, called = _baseline(target)
    else:
        graph = _topology(topology)
    weights = topology_weights(graph)
    types = {node.name: node.type for node in graph.nodes}
    candidates = [
        name
        for name in weights
        if (called is None or name in called)
        and (scope is None or scope.allows(step_name=name))
        and _factories(faults, types[name])
    ]
    if not candidates:
        raise ValueError("no topology node is eligible for fuzzing under this scope and pool")
    rng = random.Random(seed)
    summaries = {
        name: FuzzNodeSummary(node=name, node_type=types[name], weight=weights[name])
        for name in candidates
    }
    trials: list[FuzzTrial] = []
    for index in range(n):
        node = rng.choices(candidates, weights=[weights[c] for c in candidates])[0]
        fault = _build(rng.choice(_factories(faults, types[node])))
        if fault.scope is not None and not fault.scope.allows(step_name=node):
            trial = FuzzTrial(
                index=index,
                node=node,
                node_type=types[node],
                weight=weights[node],
                fault_type=fault.name,
                reached=False,
                passed=True,
                message=f"not run: the fault's own scope excludes '{node}'",
                duration_s=0.0,
            )
        else:
            fault.scope = Scope(steps=[node]).intersect(scope).intersect(fault.scope)
            trial = _trial(
                index,
                node,
                types[node],
                weights[node],
                fault,
                target,
                recovered=recovered,
                contracts=contracts,
                breaker=breaker,
            )
        trials.append(trial)
        summary = summaries[node]
        summary.trials += 1
        if not trials[-1].reached:
            summary.not_reached += 1
        elif not trials[-1].passed:
            summary.failures += 1
    return FuzzReport(
        seed=seed,
        n=n,
        start_time=started,
        end_time=datetime.now(timezone.utc),
        scope=scope.as_json() if scope is not None else None,
        nodes=sorted(summaries.values(), key=lambda s: (-s.weight, s.node)),
        trials=trials,
    )


def _trial(
    index: int,
    node: str,
    node_type: str,
    weight: float,
    fault: BaseFault,
    target: Callable[[], Any],
    *,
    recovered: Callable[[Any], bool] | None,
    contracts: Sequence[Contract],
    breaker: CircuitBreaker | None,
) -> FuzzTrial:
    crashed: BaseException | None = None
    output: Any = None
    clock = time.monotonic()
    reset_active_tracker()
    with chaos_session([fault], breaker=breaker) as session:
        try:
            output = target()
        except Exception as exc:
            crashed = exc
    reset_active_tracker()
    report = session.to_report(f"fuzz-{index}-{node}", error=crashed)
    contract_report = check_contracts(report, contracts) if contracts else None
    if crashed is not None:
        passed, message = False, f"target raised {type(crashed).__name__}: {crashed}"
    elif recovered is not None and not recovered(output):
        passed, message = False, "recovered() rejected the output"
    elif contract_report is not None and not contract_report.passed:
        passed, message = False, contract_report.summary()
    else:
        passed, message = True, "recovered"
    reached = bool(report.chaos_events)
    if not reached:
        message = f"fault never fired at '{node}'; {message}"
    return FuzzTrial(
        index=index,
        node=node,
        node_type=node_type,
        weight=weight,
        fault_type=fault.name,
        reached=reached,
        passed=passed,
        message=message,
        duration_s=time.monotonic() - clock,
        report=report.model_dump(mode="json"),
        contracts=contract_report.as_json() if contract_report is not None else None,
    )
