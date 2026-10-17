"""Chaos tests for support_agent.py.

pytest examples/pytest_chaos            # plain run: markers are inert
pytest examples/pytest_chaos --chaos    # faults injected, contracts checked
"""

from pathlib import Path

import pytest
from support_agent import answer, reviewed_answer

from agentic_chaos import TopologyTracker
from agentic_chaos.contracts import (
    CompletesWithin,
    FullTopologyTraversal,
    MaxCostImpact,
    MaxRetries,
    NoRetryStorm,
    RecoveredAfterFailure,
)

PROFILES = Path(__file__).resolve().parent.parent / "chaos.toml"


@pytest.mark.chaos(faults=["rate_limit_storm"], must_recover=True)
def test_recovers_from_rate_limits():
    assert "ships tomorrow" in answer("Where is my order?")


@pytest.mark.chaos(
    faults=["rate_limit_storm"],
    contracts=[MaxRetries(3), NoRetryStorm(5, window_seconds=10), CompletesWithin(2)],
)
def test_retry_budget_is_bounded():
    assert answer("Where is my order?")


@pytest.mark.chaos(
    faults=["rate_limit_storm"],
    baseline=True,  # run once as a dry run first, then compare
    contracts=[FullTopologyTraversal(), MaxCostImpact(4, metric="calls")],
)
def test_every_node_still_runs_under_chaos(chaos):
    tracker = chaos.attach_topology(TopologyTracker(auto_activate=False))
    assert reviewed_answer("Where is my order?", tracker)


@pytest.mark.xfail(
    "config.getoption('chaos')",  # only fails when faults are injected
    strict=True,
    reason="demonstrates a contract catching a fragile agent",
)
@pytest.mark.chaos(
    faults=["rate_limit_storm"],
    contracts=[RecoveredAfterFailure(require_step_success=True)],
)
def test_fragile_agent_is_caught():
    # One attempt cannot outlast a 3x rate-limit storm. The fallback keeps this
    # assertion green, but the llm step never succeeded again -- the contract
    # fails the test (xfail here, so the example suite stays green).
    assert answer("Where is my order?", attempts=1)


@pytest.mark.chaos(profile="ci", profile_file=PROFILES, contracts=["max_retries:3"])
def test_profile_from_chaos_toml():
    assert answer("Where is my order?")
