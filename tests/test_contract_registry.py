import pytest

from agentic_chaos.contracts import (
    CONTRACT_REGISTRY,
    CompletesWithin,
    FullTopologyTraversal,
    MaxCostImpact,
    MaxRetries,
    NoRetryStorm,
    NoUnhandledError,
    RecoveredAfterFailure,
    describe_contracts,
    parse_contract,
)


def test_registry_has_the_seven_roadmap_contracts():
    assert set(CONTRACT_REGISTRY) == {
        "completes_within",
        "no_unhandled_error",
        "max_retries",
        "recovered_after_failure",
        "max_cost_impact",
        "no_retry_storm",
        "full_topology_traversal",
    }


@pytest.mark.parametrize(
    ("spec", "cls", "params"),
    [
        ("completes_within:30", CompletesWithin, {"timeout_s": 30.0}),
        ("no_unhandled_error", NoUnhandledError, {}),
        ("max_retries:3,step=search", MaxRetries, {"n": 3, "step": "search"}),
        (
            "recovered_after_failure:require_step_success=yes",
            RecoveredAfterFailure,
            {"require_step_success": True},
        ),
        ("max_cost_impact:2,metric=calls", MaxCostImpact, {"factor": 2.0, "metric": "calls"}),
        (
            "no_retry_storm:5, window_seconds=10",
            NoRetryStorm,
            {"max_retries_per_window": 5, "window_seconds": 10.0},
        ),
        (
            "full_topology_traversal:expected_nodes=Planner|Reviewer,ignore=Cache",
            FullTopologyTraversal,
            {"expected_nodes": ["Planner", "Reviewer"], "ignore": ["Cache"]},
        ),
        ("max_retries:3,", MaxRetries, {"n": 3}),
    ],
)
def test_parse_contract(spec, cls, params):
    contract = parse_contract(spec)
    assert isinstance(contract, cls)
    assert contract.parameters() == params


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ("nope", "Unknown contract"),
        ("max_retries:1,2", "Too many positional"),
        ("max_retries:1,colour=red", "Unknown parameter"),
        ("max_retries:1,n=2", "given twice"),
        ("max_retries:many", "Invalid value"),
        ("recovered_after_failure:require_step_success=maybe", "Invalid value"),
        ("completes_within", "Invalid parameters"),
        ("completes_within:-1", "positive"),
        ("no_unhandled_error:1", "Too many positional"),
    ],
)
def test_parse_contract_errors(spec, message):
    with pytest.raises(ValueError, match=message):
        parse_contract(spec)


def test_describe_contracts():
    entries = {entry["name"]: entry for entry in describe_contracts()}
    assert entries["max_retries"]["class"] == "MaxRetries"
    assert entries["max_retries"]["positional"] == ["n"]
    assert entries["no_retry_storm"]["summary"].startswith("At most")
    assert all(entry["summary"] for entry in entries.values())
