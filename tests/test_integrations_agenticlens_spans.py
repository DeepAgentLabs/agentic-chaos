"""Span markers for AgenticLens structured traces (`span_attributes`, `mark_span`).

The helpers themselves never import AgenticLens; the end-to-end check runs
only when an AgenticLens with the diagnosis package (>= 0.7.0) is installed.
"""

from types import SimpleNamespace

import pytest

from agentic_chaos.integrations.agenticlens import (
    CHAOS_EVENT_ID_KEY,
    CHAOS_FAULT_TYPE_KEY,
    CHAOS_INJECTED_KEY,
    CHAOS_OUTCOME_KEY,
    mark_span,
    span_attributes,
)
from agentic_chaos.models.chaos_event import ChaosEvent


def _event() -> ChaosEvent:
    return ChaosEvent(
        id="evt-1", fault_type="token_timeout", outcome="errored", message="hung then timed out"
    )


def test_span_attributes_from_event_and_json_entry() -> None:
    expected = {
        CHAOS_INJECTED_KEY: True,
        CHAOS_FAULT_TYPE_KEY: "token_timeout",
        CHAOS_EVENT_ID_KEY: "evt-1",
        CHAOS_OUTCOME_KEY: "errored",
    }
    assert span_attributes(_event()) == expected
    assert span_attributes(_event().model_dump(mode="json")) == expected


def test_span_attributes_requires_a_fault_type() -> None:
    with pytest.raises(ValueError, match="fault_type"):
        span_attributes({"id": "x"})


def test_mark_span_merges_into_existing_attributes() -> None:
    span = SimpleNamespace(attributes={"tool_args": {"q": "refund"}})
    mark_span(span, _event())
    assert span.attributes["tool_args"] == {"q": "refund"}
    assert span.attributes[CHAOS_INJECTED_KEY] is True


def test_agenticlens_diagnoses_marked_span_as_injected_fault() -> None:
    diagnosis = pytest.importorskip("agenticlens.diagnosis")
    from agenticlens.models.trace import Run, RunStatus, Span, SpanType

    span = Span(
        span_id="s1", name="kb_search", span_type=SpanType.RETRIEVAL, status=RunStatus.SUCCEEDED
    )
    mark_span(span, _event())
    run = Run(application_name="demo", spans=[span], status=RunStatus.FAILED, task_success=False)
    report = diagnosis.diagnose_run(run)
    assert report.attribution.faulty_span_id == "s1"
    assert report.attribution.category.value == "injected_fault"
    case = diagnosis.controlled_failure_from_run(run)
    assert case.expected_span_id == "s1"
