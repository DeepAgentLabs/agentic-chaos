"""Native workflow report and its merge into one `ChaosReport`."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from agentic_chaos.contracts.base import ContractReport
from agentic_chaos.models.report import ChaosReport

NodeKind = Literal["step", "health_check", "parallel", "suspend"]
NodeStatus = Literal[
    "passed",
    "failed",
    "aborted",
    "skipped",
    "approved",
    "rejected",
    "suspended",
    "resumed",
    "would_suspend",
]
WorkflowStatus = Literal["passed", "failed", "aborted", "halted", "rejected", "suspended"]

WORKFLOW_REPORT_VERSION = "1.0"


class NodeResult(BaseModel):
    """What happened at one workflow node. `path` is unique within the workflow."""

    name: str
    kind: NodeKind
    status: NodeStatus
    message: str = ""
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_s: float | None = None
    faults: list[str] = Field(default_factory=list)
    repeat: int | None = None
    report: dict[str, Any] | None = None
    contracts: dict[str, Any] | None = None
    output: str | None = None
    attempts: int | None = None
    branches: list[list["NodeResult"]] = Field(default_factory=list)

    def walk(self) -> list["NodeResult"]:
        """This node followed by every node nested in its branches."""
        nodes = [self]
        for branch in self.branches:
            for child in branch:
                nodes.extend(child.walk())
        return nodes


class WorkflowReport(BaseModel):
    """Result of a `ChaosWorkflow` run.

    Top-level `chaos_events` (every step's events, with `detail.workflow`
    provenance) keep the file loadable wherever a `ChaosReport` or AgenticLens
    `Workflow` is read. Use `to_chaos_report()` for contracts and AIOS export.
    """

    schema_version: str = WORKFLOW_REPORT_VERSION
    kind: Literal["chaos_workflow"] = "chaos_workflow"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    status: WorkflowStatus
    start_time: datetime
    end_time: datetime | None = None
    dry_run: bool = False
    resumed_from: str | None = None
    suspended_at: str | None = None
    message: str = ""
    nodes: list[NodeResult] = Field(default_factory=list)
    chaos_events: list[dict[str, Any]] = Field(default_factory=list)
    experiment: dict[str, Any] | None = None
    # v0.9: workflow-level probe results (pre, during each step, post) and the
    # resilience score of the merged run.
    probes: list[dict[str, Any]] = Field(default_factory=list)
    resilience: dict[str, Any] | None = None

    @property
    def resilience_score(self) -> int | None:
        """The 0-100 resilience score of the merged run, or None when inconclusive."""
        score = (self.resilience or {}).get("score")
        return score if isinstance(score, int) and not isinstance(score, bool) else None

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def walk(self) -> list[NodeResult]:
        """Every node result, depth-first, including parallel branches."""
        nodes: list[NodeResult] = []
        for node in self.nodes:
            nodes.extend(node.walk())
        return nodes

    def node(self, name: str) -> NodeResult:
        """The result for the node named `name` (including nested branch nodes)."""
        for node in self.walk():
            if node.name == name:
                return node
        raise KeyError(name)

    def step_reports(self) -> list[tuple[str, ChaosReport]]:
        """(step name, native report) for every step that ran, in execution order."""
        return [
            (node.name, ChaosReport.model_validate(node.report))
            for node in self.walk()
            if node.kind == "step" and node.report is not None
        ]

    def summary(self) -> dict[str, Any]:
        """Compact description used in merged reports and AIOS extensions."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "dry_run": self.dry_run,
            "resumed_from": self.resumed_from,
            "suspended_at": self.suspended_at,
            "nodes": [
                {"name": node.name, "kind": node.kind, "status": node.status}
                for node in self.walk()
            ],
        }

    def to_chaos_report(self) -> ChaosReport:
        """Merge every step into one native report (events, calls, safety, topology).

        Call records keep their per-step order, are renumbered globally and gain
        `workflow_step`. `unhandled_error` is the first step's escaped error.
        """
        events: list[dict[str, Any]] = []
        calls: list[dict[str, Any]] = []
        planned: list[dict[str, Any]] = []
        topologies: list[dict[str, Any]] = []
        totals = {"cost_usd": 0.0, "injections": 0, "in_flight": 0, "calls_dropped": 0}
        aborted = False
        abort_reason: dict[str, Any] | None = None
        unhandled: dict[str, Any] | None = None
        for step_name, report in self.step_reports():
            events.extend(report.chaos_events)
            for record in report.calls:
                calls.append({**record, "sequence": len(calls) + 1, "workflow_step": step_name})
            planned.extend({**plan, "workflow_step": step_name} for plan in report.planned_events)
            if report.agent_topology:
                topologies.append(report.agent_topology)
            totals["cost_usd"] += report.cost_usd
            totals["injections"] += report.injections
            totals["in_flight"] += report.in_flight
            totals["calls_dropped"] += report.calls_dropped
            if report.aborted and not aborted:
                aborted, abort_reason = True, report.abort_reason
            if report.unhandled_error is not None and unhandled is None:
                unhandled = {**report.unhandled_error, "workflow_step": step_name}
        return ChaosReport(
            id=self.id,
            name=self.name,
            start_time=self.start_time,
            end_time=self.end_time,
            chaos_events=events,
            agent_topology=merge_topologies(topologies),
            aborted=aborted,
            abort_reason=abort_reason,
            dry_run=self.dry_run,
            planned_events=planned,
            cost_usd=float(totals["cost_usd"]),
            injections=int(totals["injections"]),
            in_flight=int(totals["in_flight"]),
            calls=calls,
            calls_dropped=int(totals["calls_dropped"]),
            unhandled_error=unhandled,
            workflow=self.summary(),
            probes=list(self.probes),
            resilience=self.resilience,
        )

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return destination

    @classmethod
    def load(cls, path: str | Path) -> "WorkflowReport":
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def contract_line(report: ContractReport) -> str:
    """One-line contract outcome: the count, plus the first failure when there is one."""
    passed = len(report.results) - len(report.failures)
    line = f"{passed}/{len(report.results)} contracts passed"
    if report.failures:
        first = report.failures[0]
        line += f"; {first.contract} {first.status}: {first.message}"
    return line


def merge_topologies(topologies: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Union topologies by node name; edges are kept and re-pointed at merged nodes."""
    if not topologies:
        return None
    if len(topologies) == 1:
        return topologies[0]
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    for topology in topologies:
        ids: dict[str, str] = {}
        for node in topology.get("nodes", []):
            merged = nodes.setdefault(node["name"], dict(node))
            ids[node["id"]] = merged["id"]
        for edge in topology.get("edges", []):
            edges.append(
                {
                    **edge,
                    "source_id": ids.get(edge["source_id"], edge["source_id"]),
                    "target_id": ids.get(edge["target_id"], edge["target_id"]),
                }
            )
    return {"nodes": list(nodes.values()), "edges": edges}
