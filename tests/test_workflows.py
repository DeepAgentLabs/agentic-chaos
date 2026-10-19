"""v0.8 chaos workflows: stages, gates, parallel branches, suspends and templates."""

import threading
import time

import pytest

from agentic_chaos import (
    RateLimitStormFault,
    Scope,
    TokenTimeoutFault,
    ToolCallFailureFault,
    TopologyTracker,
    cascade,
    chaos_call,
    chaos_session,
    wrap_node,
    wrap_tool,
)
from agentic_chaos.chaos.faults import RateLimitStormError
from agentic_chaos.contracts import MaxRetries, NoUnhandledError, RecoveredAfterFailure
from agentic_chaos.export import to_aios_run
from agentic_chaos.models import ChaosReport
from agentic_chaos.safety import CircuitBreaker
from agentic_chaos.workflows import (
    ChaosWorkflow,
    HealthCheck,
    Parallel,
    Step,
    Suspend,
    Template,
    WorkflowReport,
)


def retrying_app(attempts: int = 8):
    """Retries rate limits up to `attempts` times, like a resilient client."""

    def app():
        for _ in range(attempts):
            try:
                return chaos_call(lambda: "answer", step_name="llm")
            except RateLimitStormError:
                continue
        raise RuntimeError("gave up after rate limits")

    return app


def ping(query=None):
    return f"pong: {query}"


def test_serial_workflow_runs_steps_and_gates_in_order():
    workflow = ChaosWorkflow(
        "suite",
        steps=[
            Step("warm-up", faults=[RateLimitStormFault(burst_count=2)]),
            HealthCheck(fn=ping, query="Are you working?", expect_contains="pong"),
            Step("escalate", faults=[RateLimitStormFault(burst_count=5)]),
            HealthCheck(fn=ping),
        ],
    )
    report = workflow.run(retrying_app())
    assert report.status == "passed"
    assert report.passed
    assert [n.name for n in report.nodes] == [
        "warm-up",
        "health-check-1",
        "escalate",
        "health-check-2",
    ]
    assert [n.status for n in report.nodes] == ["passed"] * 4
    assert report.node("health-check-1").output == "'pong: Are you working?'"
    assert len(report.chaos_events) == 7
    steps = {event["detail"]["workflow"]["step"] for event in report.chaos_events}
    assert steps == {"warm-up", "escalate"}
    assert all(e["detail"]["workflow"]["id"] == report.id for e in report.chaos_events)


def test_failing_step_stops_and_skips_the_rest_by_default():
    workflow = ChaosWorkflow(
        "escalation",
        steps=[
            Step("mild", faults=[RateLimitStormFault(burst_count=2)]),
            Step("severe", faults=[RateLimitStormFault(burst_count=20)]),
            HealthCheck(fn=ping, name="after"),
            Step("never", faults=["rate_limit_storm"]),
        ],
    )
    report = workflow.run(retrying_app(attempts=5))
    assert report.status == "failed"
    assert [n.status for n in report.nodes] == ["passed", "failed", "skipped", "skipped"]
    assert "gave up" in report.node("severe").message
    unhandled = report.node("severe").report["unhandled_error"]
    assert unhandled["type"] == "RuntimeError"


def test_continue_on_failure_runs_every_step_but_reports_failed():
    workflow = ChaosWorkflow(
        "sweep",
        steps=[
            Step("severe", faults=[RateLimitStormFault(burst_count=20)]),
            Step("mild", faults=[RateLimitStormFault(burst_count=1)]),
        ],
        stop_on_failure=False,
    )
    report = workflow.run(retrying_app(attempts=3))
    assert [n.status for n in report.nodes] == ["failed", "passed"]
    assert report.status == "failed"


def test_failed_health_check_halts_unless_configured_to_continue():
    broken = HealthCheck(fn=lambda: (_ for _ in ()).throw(ConnectionError("down")), name="probe")
    report = ChaosWorkflow("halt", [Step("s", faults=[]), broken, Step("t", faults=[])]).run(
        lambda: None
    )
    assert report.status == "halted"
    assert report.node("probe").message == "raised ConnectionError: down"
    assert report.node("t").status == "skipped"

    soft = HealthCheck(fn=lambda: "degraded", expect_contains="ok", halt_on_failure=False)
    report = ChaosWorkflow("soft", [soft, Step("t", faults=[])]).run(lambda: None)
    assert report.node("t").status == "passed"
    assert report.status == "failed"


def test_health_check_expectations_and_retries():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise TimeoutError("warming up")
        return {"status": "ok"}

    check = HealthCheck(
        fn=flaky, expect=lambda out: out["status"] == "ok", retries=3, retry_delay_seconds=0
    )
    report = ChaosWorkflow("retry", [check]).run()
    node = report.nodes[0]
    assert node.status == "passed"
    assert node.attempts == 3

    expect_failure = HealthCheck(fn=lambda: "allowed", expect_success=False, name="guard")
    report = ChaosWorkflow("guard", [expect_failure]).run()
    assert report.node("guard").message == "returned normally; expected it to fail"

    def deny():
        raise PermissionError("blocked")

    report = ChaosWorkflow("guard", [HealthCheck(fn=deny, expect_success=False)]).run()
    assert report.status == "passed"

    bad_predicate = HealthCheck(fn=lambda: 1, expect=lambda out: out["missing"])
    report = ChaosWorkflow("p", [bad_predicate]).run()
    assert "predicate raised" in report.nodes[0].message


def test_health_checks_run_outside_any_chaos_session():
    seen = []

    def probe():
        from agentic_chaos.chaos.context import get_active_session

        seen.append(get_active_session())
        return "ok"

    ChaosWorkflow("w", [Step("s", faults=["rate_limit_storm"]), HealthCheck(fn=probe)]).run(
        retrying_app()
    )
    assert seen == [None]


def test_step_contracts_and_repeat():
    step = Step(
        "contracted",
        faults=[RateLimitStormFault(burst_count=3)],
        repeat=2,
        contracts=[NoUnhandledError(), MaxRetries(1, step="llm")],
    )
    report = ChaosWorkflow("c", [step]).run(retrying_app())
    node = report.nodes[0]
    assert node.status == "failed"
    assert node.repeat == 2
    assert node.contracts["passed"] is False
    assert len(node.report["calls"]) == 5  # 3 rate-limited + 2 successes

    ok = Step(
        "ok", faults=[RateLimitStormFault(burst_count=1)], contracts=[RecoveredAfterFailure()]
    )
    assert ChaosWorkflow("c", [ok]).run(retrying_app()).status == "passed"


def test_fault_instances_are_fresh_for_each_run_and_step():
    fault = RateLimitStormFault(burst_count=2)
    workflow = ChaosWorkflow("fresh", [Step("a", faults=[fault]), Step("b", faults=[fault])])
    first = workflow.run(retrying_app())
    second = workflow.run(retrying_app())
    assert len(first.chaos_events) == len(second.chaos_events) == 4
    assert fault._fired == 0


def test_circuit_breaker_aborts_the_workflow():
    workflow = ChaosWorkflow(
        "budget",
        steps=[
            Step("storm", faults=[RateLimitStormFault(burst_count=5)]),
            Step("next", faults=[]),
        ],
        breaker=CircuitBreaker(max_injections=2),
    )
    report = workflow.run(retrying_app())
    assert report.status == "aborted"
    assert report.node("storm").status == "aborted"
    assert report.node("next").status == "skipped"
    merged = report.to_chaos_report()
    assert merged.aborted is True
    assert merged.abort_reason["threshold"] == "max_injections"


def test_workflow_and_step_scopes_narrow_faults():
    def app():
        guard = wrap_tool(lambda: "allowed", tool_name="safety_check")
        search = wrap_tool(lambda: "results", tool_name="search")
        guard()
        try:
            search()
        except Exception:
            return "fallback"
        return "results"

    workflow = ChaosWorkflow(
        "scoped",
        [Step("tools", faults=[ToolCallFailureFault()], scope=Scope(steps=["search", "x"]))],
        scope=Scope(exclude_steps=["safety_check"]),
    )
    report = workflow.run(app)
    events = report.chaos_events
    assert [event["step_name"] for event in events] == ["search"]


def test_parallel_branches_run_concurrently_with_isolated_sessions():
    barrier = threading.Barrier(2, timeout=5)

    def concurrent_app():
        barrier.wait()  # deadlocks unless both branches run at the same time
        return chaos_call(lambda: "ok", step_name="llm")

    workflow = ChaosWorkflow(
        "fanout",
        [
            Parallel(
                Step("tool-chaos", faults=[TokenTimeoutFault(hang_seconds=0, mode="delay")]),
                [Step("memory-chaos", faults=["silent_degradation"]), HealthCheck(fn=ping)],
                name="both",
            ),
            HealthCheck(fn=ping, name="after"),
        ],
    )
    report = workflow.run(concurrent_app)
    assert report.status == "passed"
    parallel = report.node("both")
    assert parallel.kind == "parallel"
    assert [[n.name for n in branch] for branch in parallel.branches] == [
        ["tool-chaos"],
        ["memory-chaos", "health-check-1"],
    ]
    assert {e["fault_type"] for e in report.chaos_events} == {
        "token_timeout",
        "silent_degradation",
    }
    assert report.node("memory-chaos").status == "passed"


def test_parallel_failure_propagates_and_skips_later_nodes():
    def app():
        return chaos_call(lambda: "ok")

    workflow = ChaosWorkflow(
        "fanout",
        [
            Parallel(
                Step("fails", faults=[RateLimitStormFault(burst_count=1)]),
                Step("passes", faults=[]),
            ),
            Step("later", faults=[]),
        ],
    )
    report = workflow.run(app)
    assert report.status == "failed"
    assert report.node("parallel-1").status == "failed"
    assert report.node("later").status == "skipped"


def test_parallel_rejects_suspend_and_single_branch():
    with pytest.raises(ValueError, match="Suspend"):
        Parallel(Step("a", faults=[]), [Step("b", faults=[]), Suspend("gate")])
    with pytest.raises(ValueError, match="two branches"):
        Parallel(Step("a", faults=[]))


def test_suspend_without_decision_stops_and_resume_continues():
    workflow = ChaosWorkflow(
        "gated",
        [
            Step("warm-up", faults=[RateLimitStormFault(burst_count=1)]),
            Suspend("approve-blast", reason="hits shared staging"),
            Step("full-blast", faults=[RateLimitStormFault(burst_count=3)]),
        ],
    )
    report = workflow.run(retrying_app())
    assert report.status == "suspended"
    assert report.suspended_at == "approve-blast"
    assert "resume_from='approve-blast'" in report.message
    assert report.node("approve-blast").message == "hits shared staging"
    assert report.node("full-blast").status == "skipped"

    resumed = workflow.run(retrying_app(), resume_from="approve-blast")
    assert resumed.status == "passed"
    assert resumed.resumed_from == "approve-blast"
    assert [n.status for n in resumed.nodes] == ["skipped", "resumed", "passed"]
    with pytest.raises(ValueError, match="not a top-level Suspend"):
        workflow.run(retrying_app(), resume_from="warm-up")


def test_suspend_approvers():
    nodes = [Suspend("gate"), Step("after", faults=[])]
    workflow = ChaosWorkflow("gated", nodes)
    assert workflow.run(lambda: None, approve=True).status == "passed"
    assert workflow.run(lambda: None, approve={"gate"}).status == "passed"
    assert workflow.run(lambda: None, approve="other").status == "suspended"
    rejected = workflow.run(lambda: None, approve=False)
    assert rejected.status == "rejected"
    assert rejected.node("after").status == "skipped"

    seen = []

    def approver(gate, report):
        seen.append((gate.name, [n.name for n in report.nodes]))
        return True

    gated = ChaosWorkflow("g", [Step("s", faults=[]), Suspend("gate", approve=approver)])
    assert gated.run(lambda: None, approve=False).status == "passed"  # node approver wins
    assert seen == [("gate", ["s"])]


def test_dry_run_previews_steps_and_passes_suspends():
    calls = []

    def app():
        calls.append(1)
        return chaos_call(lambda: "ok")

    workflow = ChaosWorkflow(
        "preview", [Step("a", faults=["rate_limit_storm"]), Suspend("gate"), Step("b", faults=[])]
    )
    report = workflow.run(app, dry_run=True)
    assert report.status == "passed"
    assert report.dry_run
    assert report.node("gate").status == "would_suspend"
    assert report.chaos_events == []
    assert report.node("a").report["planned_events"][0]["outcome"] == "would_inject"
    assert len(calls) == 2


def test_templates_expand_with_parameters_and_prefixes():
    escalate = Template(
        "escalate",
        lambda burst=2: [
            Step("storm", faults=[RateLimitStormFault(burst_count=burst)]),
            HealthCheck(fn=ping, name="ping"),
        ],
    )
    static = Template("baseline", [Step("clean", faults=[])])
    workflow = ChaosWorkflow(
        "templated",
        [static.use(), escalate.use(name="mild"), escalate.use(name="hard", burst=6)],
    )
    assert workflow.node_names == [
        "baseline/clean",
        "mild/storm",
        "mild/ping",
        "hard/storm",
        "hard/ping",
    ]
    report = workflow.run(retrying_app())
    assert report.status == "passed"
    assert len(report.node("hard/storm").report["chaos_events"]) == 6
    with pytest.raises(ValueError, match="takes no parameters"):
        static.expand(x=1)
    with pytest.raises(ValueError, match="duplicate"):
        ChaosWorkflow("dup", [escalate.use(), escalate.use()])


def test_template_inside_parallel_and_nested_templates():
    inner = Template("inner", [Step("s", faults=[])])
    outer = Template("outer", lambda: [inner.use(), HealthCheck(fn=ping)])
    workflow = ChaosWorkflow("nested", [Parallel(outer.use(name="left"), outer.use(name="right"))])
    assert workflow.node_names == [
        "parallel-1",
        "left/inner/s",
        "health-check-1",
        "right/inner/s",
        "health-check-2",
    ]
    assert workflow.run(lambda: None).status == "passed"


def test_workflow_definition_errors():
    with pytest.raises(ValueError, match="Unknown fault"):
        Step("x", faults=["nope"])
    with pytest.raises(ValueError, match="repeat"):
        Step("x", repeat=0)
    with pytest.raises(ValueError, match="name"):
        Step(" padded ", faults=[])
    with pytest.raises(ValueError, match="at least one node"):
        ChaosWorkflow("empty", [])
    with pytest.raises(ValueError, match="unsupported workflow node"):
        ChaosWorkflow("bad", ["step"])
    with pytest.raises(ValueError, match="retries"):
        HealthCheck(retries=-1)
    with pytest.raises(ValueError, match="expect"):
        HealthCheck(expect_success=False, expect_contains="x")
    with pytest.raises(ValueError, match="no target"):
        ChaosWorkflow("w", [Step("s", faults=[])]).run()
    with pytest.raises(RuntimeError, match="active chaos_session"), chaos_session([]):
        ChaosWorkflow("w", [Step("s", faults=[])]).run(lambda: None)
    recursive = Template("r", lambda: [recursive.use()])
    with pytest.raises(ValueError, match="nested too deeply"):
        ChaosWorkflow("w", [recursive.use()])


def test_step_level_target_overrides_workflow_target():
    workflow = ChaosWorkflow(
        "targets",
        [Step("own", faults=[], target=lambda: None), Step("default", faults=[])],
        target=lambda: (_ for _ in ()).throw(ValueError("default target")),
    )
    report = workflow.run()
    assert report.node("own").status == "passed"
    assert report.node("default").status == "failed"


def test_merged_report_combines_steps_for_contracts_and_aios():
    def app():
        tracker = TopologyTracker()
        planner = wrap_node(lambda: "plan", node_name="Planner", tracker=tracker)
        search = wrap_tool(
            lambda: "docs", tool_name="search", tracker=tracker, caller_node="Planner"
        )
        planner()
        for _ in range(4):
            try:
                return search()
            except RateLimitStormError:
                continue
        return None

    workflow = ChaosWorkflow(
        "merge",
        [
            Step("one", faults=[RateLimitStormFault(burst_count=1)]),
            Step(
                "two",
                faults=[
                    cascade(
                        first=RateLimitStormFault(burst_count=1),
                        then=TokenTimeoutFault(hang_seconds=0, mode="delay"),
                    )
                ],
            ),
        ],
        scope=Scope(steps=["search"]),
    )
    report = workflow.run(app)
    merged = report.to_chaos_report()
    assert isinstance(merged, ChaosReport)
    assert merged.id == report.id
    assert len(merged.chaos_events) == len(report.chaos_events) == 3
    assert [c["sequence"] for c in merged.calls] == list(range(1, len(merged.calls) + 1))
    assert {c["workflow_step"] for c in merged.calls} == {"one", "two"}
    assert merged.injections == 3
    names = sorted(node["name"] for node in merged.agent_topology["nodes"])
    assert names == ["Planner", "search"]
    assert merged.workflow["status"] == "passed"
    assert [n["name"] for n in merged.workflow["nodes"]] == ["one", "two"]
    run = to_aios_run(merged)
    extension = run["extensions"]["io.deepagentlabs.agentic-chaos"]
    assert extension["workflow"]["name"] == "merge"
    reloaded = ChaosReport.model_validate_json(merged.model_dump_json())
    assert reloaded.workflow == merged.workflow


def test_report_round_trip_and_lookup(tmp_path):
    report = ChaosWorkflow("io", [Step("s", faults=["rate_limit_storm"])]).run(retrying_app())
    path = report.save(tmp_path / "workflow.json")
    loaded = WorkflowReport.load(path)
    assert loaded == report
    assert loaded.kind == "chaos_workflow"
    assert loaded.schema_version == "1.0"
    assert [name for name, _ in loaded.step_reports()] == ["s"]
    with pytest.raises(KeyError):
        loaded.node("missing")
    # Top-level chaos_events keep the file loadable as a native ChaosReport.
    native = ChaosReport.model_validate_json(path.read_text())
    assert len(native.chaos_events) == 3


def test_step_durations_are_recorded():
    def slow():
        time.sleep(0.01)

    report = ChaosWorkflow("t", [Step("s", faults=[])]).run(slow)
    assert report.nodes[0].duration_s >= 0.01
    assert report.end_time >= report.start_time


def test_recursive_template_inside_parallel_is_a_clean_error():
    loop = Template("loop", lambda: [loop.use()])
    with pytest.raises(ValueError, match="nested too deeply"):
        Parallel(loop.use(), Step("b", faults=[]))
