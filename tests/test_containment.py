"""Fail-closed native containment assertions, including deliberately unsafe control."""

from copy import deepcopy

import pytest

from agentic_chaos.containment import _assert_observations


def observations():
    return [
        dict(event_id="1", kind="dispatched", correlation_id="running", subject="u", task_id="t"),
        dict(
            event_id="2", kind="stop_acknowledged", outcome="acknowledged", subject="u", task_id="t"
        ),
        dict(event_id="3", kind="completed", correlation_id="running", subject="u", task_id="t"),
        dict(event_id="4", kind="denied", correlation_id="retry", subject="u", task_id="t"),
    ]


def check(records, status="verified"):
    return _assert_observations(
        records,
        acknowledgement_id="2",
        subject="u",
        task_id="t",
        attempted_call_ids={"retry"},
        verification={"status": status, "authenticated": True},
    )


def test_in_flight_effects_are_separate():
    assert check(observations()) == {
        "forbidden_dispatches": 0,
        "in_flight_at_acknowledgement": ["running"],
        "completed_after_acknowledgement": ["running"],
        "attempted_calls": ["retry"],
    }


@pytest.mark.parametrize("status", ["failed", "unknown", "incomplete", None])
def test_unverified_never_passes(status):
    with pytest.raises(AssertionError, match="Verified"):
        check(observations(), status)


@pytest.mark.parametrize("mutation", ["bypass", "missing", "requested", "cross_task", "duplicate"])
def test_negative_controls(mutation):
    records = deepcopy(observations())
    if mutation == "bypass":
        records[-1]["kind"] = "dispatched"
    elif mutation == "missing":
        records.pop()
    elif mutation == "requested":
        records[1]["kind"] = "stop_requested"
    elif mutation == "cross_task":
        records[1]["task_id"] = "other"
    else:
        records[-1]["event_id"] = "1"
    with pytest.raises(AssertionError):
        check(records)
