"""Derived views over a report's call log and topology, shared by contracts.

Definitions (also documented in docs/v0.6.md):

- A call's *step* is its ``(kind, step_name or step_id)``. Calls with neither
  name are unnamed and are never treated as retries of one another.
- A *retry* is a call to a step whose previous call to that same step raised.
  A successful call ends the step's retry streak.
- A node is *visited* when it is an endpoint of a recorded topology edge or the
  step name of an instrumented call. Registering a node alone is not a visit.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from agentic_chaos.models.report import ChaosReport


@dataclass(frozen=True)
class Retry:
    step: str
    started_at: datetime | None
    streak: int


def _step_key(call: dict[str, Any]) -> tuple[str, str] | None:
    name = call.get("step_name") or call.get("step_id")
    if not isinstance(name, str) or not name:
        return None
    kind = call.get("kind")
    return (kind if isinstance(kind, str) else "call", name)


def _started_at(call: dict[str, Any]) -> datetime | None:
    value = call.get("started_at")
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def ordered_calls(report: ChaosReport) -> list[dict[str, Any]]:
    """Calls in the order they started (by sequence number when present)."""

    def key(call: dict[str, Any]) -> int:
        value = call.get("sequence", 0)
        return value if isinstance(value, int) else 0

    return sorted(report.calls, key=key)


def find_retries(report: ChaosReport) -> list[Retry]:
    """Every retry in the call log, with its step and position in the streak."""
    last_failed: dict[tuple[str, str], int] = {}
    retries: list[Retry] = []
    for call in ordered_calls(report):
        step = _step_key(call)
        if step is None:
            continue
        streak = last_failed.get(step, 0)
        if streak:
            retries.append(Retry(step=step[1], started_at=_started_at(call), streak=streak))
        if call.get("status") == "error":
            last_failed[step] = streak + 1
        else:
            last_failed.pop(step, None)
    return retries


def max_retries_by_step(report: ChaosReport) -> dict[str, int]:
    """Longest consecutive retry streak observed for each named step."""
    longest: dict[str, int] = {}
    for retry in find_retries(report):
        longest[retry.step] = max(longest.get(retry.step, 0), retry.streak)
    return longest


def unnamed_call_count(report: ChaosReport) -> int:
    return sum(1 for call in report.calls if _step_key(call) is None)


def visited_nodes(report: ChaosReport) -> set[str]:
    """Names of nodes the run actually reached (see module docstring)."""
    visited: set[str] = set()
    topology = report.agent_topology or {}
    names: dict[str, str] = {}
    for node in topology.get("nodes", []) or []:
        if isinstance(node, dict) and isinstance(node.get("id"), str):
            name = node.get("name")
            if isinstance(name, str):
                names[node["id"]] = name
    for edge in topology.get("edges", []) or []:
        if not isinstance(edge, dict):
            continue
        for end in ("source_id", "target_id"):
            node_id = edge.get(end)
            if isinstance(node_id, str) and node_id in names:
                visited.add(names[node_id])
    for call in report.calls:
        name = call.get("step_name")
        if isinstance(name, str) and name:
            visited.add(name)
    return visited


def injected_failures(report: ChaosReport) -> list[dict[str, Any]]:
    """Fault events whose outcome is ``errored`` -- failures the app had to survive."""
    return [event for event in report.chaos_events if event.get("outcome") == "errored"]
