"""v0.8 topology fuzzer: fan-out weighting, scoping, reproducibility and outcomes."""

import pytest

from agentic_chaos import (
    RateLimitStormFault,
    Scope,
    TopologyTracker,
    chaos_call,
    chaos_session,
    wrap_node,
    wrap_tool,
)
from agentic_chaos.agents import ToolCallFailureError
from agentic_chaos.chaos.faults import RateLimitStormError
from agentic_chaos.contracts import NoUnhandledError
from agentic_chaos.models import AgentTopology, ChaosReport
from agentic_chaos.workflows import DEFAULT_FAULTS, FuzzReport, fuzz_topology, topology_weights


def support_graph(fragile=("billing",)):
    """Coordinator fans out to three tools; tools named in `fragile` have no fallback."""

    def app():
        tracker = TopologyTracker()
        tools = {
            name: wrap_tool(
                lambda name=name: f"{name} ok",
                tool_name=name,
                tracker=tracker,
                caller_node="Coordinator",
            )
            for name in ("search", "billing", "safety_check")
        }

        def coordinate():
            answers = []
            for name, tool in tools.items():
                try:
                    answers.append(tool())
                except ToolCallFailureError:
                    if name in fragile:
                        raise
                    answers.append(f"{name} fallback")
            return answers

        coordinator = wrap_node(coordinate, node_name="Coordinator", tracker=tracker)
        for _ in range(4):
            try:
                return coordinator()
            except RateLimitStormError:
                continue  # the coordinator's own LLM call is retried on a 429
        raise RuntimeError("coordinator gave up")

    return app


def test_topology_weights_follow_fan_out():
    tracker = TopologyTracker(auto_activate=False)
    for tool in ("a", "b", "c"):
        tracker.record_edge("hub", tool, target_type="tool")
    tracker.record_edge("hub", "a", target_type="tool")  # repeated edge counts once
    tracker.record_edge("a", "a")  # self-loops are ignored
    assert topology_weights(tracker.topology) == {"hub": 4.0, "a": 1.0, "b": 1.0, "c": 1.0}


def test_fuzz_discovers_topology_and_finds_the_fragile_node():
    report = fuzz_topology(support_graph(), n=30, seed=7)
    assert isinstance(report, FuzzReport)
    assert len(report.trials) == 30
    by_node = {node.node: node for node in report.nodes}
    assert set(by_node) == {"Coordinator", "search", "billing", "safety_check"}
    assert by_node["Coordinator"].weight == 4.0
    # The coordinator is weighted 4x a leaf, so it is chosen most often.
    assert by_node["Coordinator"].trials == max(n.trials for n in report.nodes)
    assert report.failing_nodes == ["billing"]
    assert all(t.node == "billing" for t in report.failures)
    tool_trials = [t for t in report.trials if t.node_type == "tool"]
    assert {t.fault_type for t in tool_trials} == {"tool_failure"}
    for trial in report.trials:
        assert trial.reached
        events = trial.report["chaos_events"]
        assert {event["step_name"] for event in events} == {trial.node}


def test_same_seed_same_placements():
    first = fuzz_topology(support_graph(), n=12, seed=3)
    second = fuzz_topology(support_graph(), n=12, seed=3)
    assert [(t.node, t.fault_type) for t in first.trials] == [
        (t.node, t.fault_type) for t in second.trials
    ]


def test_scope_excludes_nodes_from_placement():
    report = fuzz_topology(
        support_graph(), n=15, seed=1, scope=Scope(exclude_steps=["safety_check", "billing"])
    )
    assert {t.node for t in report.trials} <= {"Coordinator", "search"}
    assert report.scope == {"exclude_steps": ["billing", "safety_check"]}
    assert report.failing_nodes == []
    only = fuzz_topology(support_graph(), n=5, seed=1, scope=Scope(steps=["search"]))
    assert {t.node for t in only.trials} == {"search"}


def test_custom_fault_pool_by_node_type_and_recovered_predicate():
    pool = {"tool": [lambda: RateLimitStormFault(burst_count=1)], "*": []}
    report = fuzz_topology(
        support_graph(fragile=()),
        n=6,
        seed=2,
        faults=pool,
        recovered=lambda output: all("ok" in answer for answer in output),
    )
    assert {t.node_type for t in report.trials} == {"tool"}
    assert {t.fault_type for t in report.trials} == {"rate_limit_storm"}
    # A 429 on a tool aborts that coordinator pass; its retry then succeeds.
    assert all(t.passed for t in report.trials)


def test_contracts_are_checked_per_trial():
    report = fuzz_topology(
        support_graph(), n=8, seed=5, faults=["tool_failure"], contracts=[NoUnhandledError()]
    )
    assert all(trial.contracts is not None for trial in report.trials)
    failing = [t for t in report.trials if t.node == "billing" and t.reached]
    assert failing and all(not t.passed for t in failing)


def test_explicit_topology_and_unreached_nodes(tmp_path):
    tracker = TopologyTracker(auto_activate=False)
    tracker.record_edge("Planner", "lookup", target_type="tool")

    def app():
        return chaos_call(lambda: "ok", step_name="lookup")

    report = fuzz_topology(app, n=10, seed=0, topology=tracker, faults=["tool_failure"])
    planner = [t for t in report.trials if t.node == "Planner"]
    assert planner and all(not t.reached for t in planner)
    assert all("never fired" in t.message for t in planner)
    lookup = next(n for n in report.nodes if n.node == "lookup")
    assert lookup.failures == lookup.trials > 0

    saved = ChaosReport(
        name="baseline",
        start_time=report.start_time,
        agent_topology=tracker.topology.as_json(),
    )
    path = tmp_path / "baseline.json"
    path.write_text(saved.model_dump_json())
    for source in (path, str(path), saved, saved.model_dump(mode="json"), tracker.topology):
        assert fuzz_topology(app, n=1, topology=source, faults=["tool_failure"]).n == 1
    report.save(tmp_path / "fuzz.json")
    assert FuzzReport.model_validate_json((tmp_path / "fuzz.json").read_text()).n == 10


def test_baseline_without_tracker_uses_called_steps():
    def app():
        chaos_call(lambda: "a", step_name="retrieve")
        return chaos_call(lambda: "b", step_name="generate")

    report = fuzz_topology(app, n=4, seed=0)
    assert {n.node for n in report.nodes} == {"retrieve", "generate"}
    assert {n.node_type for n in report.nodes} == {"step"}
    assert {t.fault_type for t in report.trials} == set(DEFAULT_FAULTS["*"])


def test_fault_scope_that_excludes_the_node_is_not_run():
    pool = [lambda: RateLimitStormFault(scope=Scope(exclude_steps=["search"]))]

    def app():
        return chaos_call(lambda: "ok", step_name="search")

    report = fuzz_topology(app, n=2, faults=pool)
    assert all(not t.reached and t.report is None for t in report.trials)


def test_fuzz_errors():
    with pytest.raises(ValueError, match="positive"):
        fuzz_topology(lambda: None, n=0)
    with pytest.raises(ValueError, match="baseline run failed"):
        fuzz_topology(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(ValueError, match="no topology node is eligible"):
        fuzz_topology(lambda: None)
    with pytest.raises(ValueError, match="no agent_topology"):
        fuzz_topology(lambda: None, topology={"agent_topology": None})
    with pytest.raises(ValueError, match="Unknown fault"):
        fuzz_topology(lambda: chaos_call(lambda: 1, step_name="x"), faults=["nope"])
    with pytest.raises(ValueError, match="did not return"):
        fuzz_topology(lambda: chaos_call(lambda: 1, step_name="x"), faults=[lambda: object()])
    with pytest.raises(RuntimeError, match="active chaos_session"), chaos_session([]):
        fuzz_topology(lambda: None, topology=AgentTopology())


def test_provider_scopes_keep_nodes_eligible_and_limit_injection():
    def app():
        chaos_call(lambda: "a", step_name="retrieve", chaos_provider="anthropic")
        return chaos_call(lambda: "b", step_name="generate", chaos_provider="openai")

    report = fuzz_topology(
        app, n=6, seed=0, faults=["tool_failure"], scope=Scope(providers=["openai"])
    )
    retrieve = [t for t in report.trials if t.node == "retrieve"]
    generate = [t for t in report.trials if t.node == "generate"]
    assert retrieve and generate
    assert all(not t.reached for t in retrieve)  # anthropic calls are out of scope
    assert all(t.reached for t in generate)
