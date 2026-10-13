"""Export a `ChaosReport` as an AI Operations Specification v0.4-draft Run artifact.

The native `ChaosReport` stays this package's own report format. This module
derives an AIOS `run` artifact from it, following the reviewed mapping in
ai-operations-spec's `reviews/framework-mappings/agentic-chaos.md`:

- the report becomes the Run (plus one Request for the experiment invocation)
- each correlated step (`step_id`, else `step_name`) becomes a Step contained
  by the Run
- each chaos event becomes one runtime occurrence (the wrapped call it hit),
  observed in its Step, plus one `reliability_event` evidence object that
  `signals-on` that occurrence
- run, failure, and reliability lifecycle points become canonical `aiops.*`
  events

The export only states what the report records. It does not claim recovery,
retry chains, or step outcomes the native events cannot show: steps carry no
status, every reliability event is `detected`, and no `follows`/`caused`
retry edges are invented. Package-specific fields (topology, drift, raw event
detail) ride in the reverse-domain `io.deepagentlabs.agentic-chaos` extension
or in `attributes`, which AIOS consumers must preserve.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agentic_chaos.models.report import ChaosReport

SPEC_VERSION = "0.4-draft"
EXTENSION_NAME = "io.deepagentlabs.agentic-chaos"

_RUN_STATUSES = {"created", "running", "completed", "failed", "cancelled"}

# Which kind of wrapped call a fault fires on. Faults not listed here act on a
# model/provider call (timeouts, rate limits, degraded output, streams, auth,
# context length), which is the AIOS `model_interaction` occurrence type.
_OCCURRENCE_TYPE_BY_FAULT = {
    "tool_failure": "tool_invocation",
    "memory_corruption": "memory_operation",
    "handoff_corruption": "context",
}

_STEP_CATEGORY_BY_OCCURRENCE = {
    "model_interaction": "model",
    "tool_invocation": "tool",
    "memory_operation": "memory",
    "rag_retrieval": "retrieval",
    "context": "handoff",
}

_FAILED_EVENT_BY_OCCURRENCE = {
    "model_interaction": "aiops.model.failed",
    "tool_invocation": "aiops.tool.failed",
    "memory_operation": "aiops.memory.failed",
    "rag_retrieval": "aiops.retrieval.failed",
}

_UNATTRIBUTED_STEP = "unattributed"


def to_aios_run(
    report: ChaosReport | dict[str, Any],
    *,
    status: str = "completed",
    workflow_id: str | None = None,
    producer_version: str | None = None,
) -> dict[str, Any]:
    """Return an AIOS v0.4-draft `run` artifact derived from a chaos report.

    `status` is the Run's outcome as the caller observed it (for example
    `"failed"` when the target script crashed or timed out); the native report
    does not record it. `workflow_id`, when given, adds a `run-of` link to an
    external Workflow definition.
    """
    if status not in _RUN_STATUSES:
        raise ValueError(f"status must be one of {sorted(_RUN_STATUSES)}, got {status!r}")
    if not isinstance(report, ChaosReport):
        report = ChaosReport.model_validate(report)

    if not report.id.strip():
        raise ValueError("report.id must be a non-blank string to become an AIOS Run id")
    run_id = report.id
    started_at = _timestamp(report.start_time)
    ended_at = _timestamp(report.end_time) if report.end_time is not None else None

    steps: dict[str, dict[str, Any]] = {}
    occurrences: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = [
        _event(f"{run_id}:event:run-started", "aiops.run.started", started_at, run_id, "run")
    ]

    if workflow_id is not None:
        relationships.append(
            _relationship(
                f"{run_id}:rel:run-of",
                "run-of",
                (run_id, "run"),
                (workflow_id, "workflow", True),
            )
        )

    for index, raw_event in enumerate(report.chaos_events, start=1):
        fault_type = str(raw_event.get("fault_type", "unknown_fault"))
        outcome = str(raw_event.get("outcome", "unknown"))
        occurrence_type = _OCCURRENCE_TYPE_BY_FAULT.get(fault_type, "model_interaction")
        occurred_at = _event_time(raw_event.get("timestamp"), started_at)
        source_event_id = str(raw_event.get("id") or index)

        step, created = _step_for(raw_event, run_id, occurrence_type, steps)
        if created:
            relationships.append(
                _relationship(
                    f"{run_id}:rel:contains:{len(steps)}",
                    "contains",
                    (run_id, "run"),
                    (step["id"], "step"),
                )
            )

        occurrence_id = f"{run_id}:occurrence:{index}"
        occurrences.append(
            {
                "id": occurrence_id,
                "type": occurrence_type,
                "name": f"{step.get('name', step['id'])} call",
                "status": "failed" if outcome == "errored" else outcome,
                "attributes": {"fault_type": fault_type, "source_event_id": source_event_id},
            }
        )
        relationships.append(
            _relationship(
                f"{run_id}:rel:observed-in:{index}",
                "observed-in",
                (occurrence_id, occurrence_type),
                (step["id"], "step"),
            )
        )

        evidence_id = f"{run_id}:reliability:{index}"
        evidence.append(
            {
                "id": evidence_id,
                "type": "reliability_event",
                "name": f"{fault_type} on {step.get('name', step['id'])}",
                "status": "detected",
                "attributes": _evidence_attributes(raw_event, fault_type, outcome, source_event_id),
            }
        )
        relationships.append(
            _relationship(
                f"{run_id}:rel:signals-on:{index}",
                "signals-on",
                (evidence_id, "reliability_event"),
                (occurrence_id, occurrence_type),
            )
        )

        failed_event = _FAILED_EVENT_BY_OCCURRENCE.get(occurrence_type)
        if outcome == "errored" and failed_event is not None:
            events.append(
                _event(
                    f"{run_id}:event:occurrence-failed:{index}",
                    failed_event,
                    occurred_at,
                    occurrence_id,
                    occurrence_type,
                )
            )
        events.append(
            _event(
                f"{run_id}:event:reliability-detected:{index}",
                "aiops.reliability.detected",
                occurred_at,
                evidence_id,
                "reliability_event",
            )
        )

    if ended_at is not None and status in {"completed", "failed", "cancelled"}:
        events.append(
            _event(f"{run_id}:event:run-{status}", f"aiops.run.{status}", ended_at, run_id, "run")
        )

    artifact: dict[str, Any] = {
        "spec_version": SPEC_VERSION,
        "artifact_type": "run",
        "id": run_id,
        "started_at": started_at,
        "status": status,
        "requests": [
            {
                "id": f"{run_id}:request",
                "name": f"chaos experiment {report.name}",
                "status": status,
            }
        ],
        "steps": list(steps.values()),
        "occurrences": occurrences,
        "evidence": evidence,
        "relationships": relationships,
        "events": events,
        "measurements": _measurements(report),
        "extensions": {EXTENSION_NAME: _extension(report, producer_version)},
    }
    if workflow_id is not None:
        artifact["workflow_id"] = workflow_id
    if ended_at is not None:
        artifact["ended_at"] = ended_at
    return artifact


def _step_for(
    raw_event: dict[str, Any],
    run_id: str,
    occurrence_type: str,
    steps: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Return the Step this event correlates to, and whether it was just created.

    AIOS step IDs are generated per run (`<run>:step:<n>`) so they are always
    valid and can never collide with each other or with the run's own objects;
    the producer's native `step_id`/`step_name` are kept in `attributes`.
    """
    step_id = _clean(raw_event.get("step_id"))
    step_name = _clean(raw_event.get("step_name"))
    if step_id is not None:
        key = f"id:{step_id}"
    elif step_name is not None:
        key = f"name:{step_name}"
    else:
        key = _UNATTRIBUTED_STEP
    if key in steps:
        return steps[key], False
    attributes: dict[str, Any] = {}
    if step_id is not None:
        attributes["native_step_id"] = step_id
    if step_name is not None:
        attributes["native_step_name"] = step_name
    if key == _UNATTRIBUTED_STEP:
        attributes["reason"] = "chaos event carried no step_id or step_name"
    step: dict[str, Any] = {
        "id": f"{run_id}:step:{len(steps) + 1}",
        "category": _STEP_CATEGORY_BY_OCCURRENCE[occurrence_type],
        "name": step_name or step_id or "unattributed",
        "attributes": attributes,
    }
    steps[key] = step
    return step, True


def _clean(value: Any) -> str | None:
    """A usable correlation value, or None for missing/blank ones."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _evidence_attributes(
    raw_event: dict[str, Any], fault_type: str, outcome: str, source_event_id: str
) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        "fault_type": fault_type,
        "outcome": outcome,
        "source_event_id": source_event_id,
    }
    for field in ("message", "fidelity_score", "edge_id", "from_node", "to_node"):
        if raw_event.get(field) is not None:
            attributes[field] = raw_event[field]
    if raw_event.get("detail"):
        attributes["detail"] = raw_event["detail"]
    return attributes


def _measurements(report: ChaosReport) -> list[dict[str, Any]]:
    measurements: list[dict[str, Any]] = []
    if report.end_time is not None:
        duration_ms = (report.end_time - report.start_time).total_seconds() * 1000
        measurements.append(
            {"name": "duration", "value": max(duration_ms, 0.0), "unit": "ms", "kind": "observed"}
        )
    measurements.append(
        {
            "name": "chaos_event_count",
            "value": len(report.chaos_events),
            "unit": "events",
            "kind": "derived",
        }
    )
    return measurements


def _extension(report: ChaosReport, producer_version: str | None) -> dict[str, Any]:
    if producer_version is None:
        from agentic_chaos import __version__ as producer_version
    extension: dict[str, Any] = {
        "producer": "agentic-chaos",
        "producer_version": producer_version,
        "report_id": report.id,
        "report_name": report.name,
    }
    if report.agent_topology is not None:
        extension["agent_topology"] = report.agent_topology
    if report.drift_report is not None:
        extension["drift_report"] = report.drift_report
    return extension


def _relationship(
    relationship_id: str,
    relationship_type: str,
    source: tuple[str, str],
    target: tuple[str, str] | tuple[str, str, bool],
) -> dict[str, Any]:
    target_ref: dict[str, Any] = {"id": target[0], "type": target[1]}
    if len(target) == 3 and target[2]:
        target_ref["external"] = True
    return {
        "id": relationship_id,
        "type": relationship_type,
        "source": {"id": source[0], "type": source[1]},
        "target": target_ref,
    }


def _event(
    event_id: str, event_name: str, occurred_at: str, object_id: str, object_type: str
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "event_name": event_name,
        "occurred_at": occurred_at,
        "object_id": object_id,
        "object_type": object_type,
    }


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _event_time(value: Any, fallback: str) -> str:
    if isinstance(value, datetime):
        return _timestamp(value)
    if isinstance(value, str):
        try:
            return _timestamp(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return fallback
    return fallback
