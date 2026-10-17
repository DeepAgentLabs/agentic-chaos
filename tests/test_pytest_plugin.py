"""End-to-end tests of the pytest plugin, run in isolated pytester sessions."""

import json

import pytest

pytest_plugins = ["pytester"]

AGENT = """
from agentic_chaos import chaos_call
from agentic_chaos.chaos.faults import RateLimitStormError


def weather_agent(question, attempts=5):
    for _ in range(attempts):
        try:
            return chaos_call(lambda: "sunny", step_name="llm", faults=["rate_limit_storm"])
        except RateLimitStormError:
            continue
    raise RuntimeError("gave up")
"""


def artifact(directory, stem: str, kind: str):
    """The one `<stem>-<digest>.<kind>.json` artifact the plugin wrote for a test."""
    (path,) = directory.glob(f"{stem}-*.{kind}.json")
    return path


@pytest.fixture
def project(pytester: pytest.Pytester) -> pytest.Pytester:
    pytester.makepyfile(agent=AGENT)
    pytester.syspathinsert()
    return pytester


def test_markers_are_inert_without_chaos_flag(project: pytest.Pytester) -> None:
    project.makepyfile(
        test_weather="""
        import pytest
        from agentic_chaos.chaos.context import get_active_session
        from agent import weather_agent

        @pytest.mark.chaos(faults=["rate_limit_storm"], contracts=["max_retries:0"])
        def test_weather(chaos):
            assert get_active_session() is None
            assert chaos.session is None and not chaos.enabled
            chaos.record_cost(1.0)  # no-op
            assert weather_agent("?") == "sunny"
        """
    )
    result = project.runpytest("--strict-markers")
    result.assert_outcomes(passed=1)
    assert "chaos markers enabled" not in result.stdout.str()
    assert "chaos test(s)" not in result.stdout.str()


def test_chaos_flag_injects_and_must_recover_passes(project: pytest.Pytester) -> None:
    project.makepyfile(
        test_weather="""
        import pytest
        from agent import weather_agent

        @pytest.mark.chaos(faults=["rate_limit_storm"], must_recover=True)
        def test_weather(chaos):
            assert chaos.active
            assert weather_agent("?") == "sunny"
            assert len(chaos.session.events) == 3
        """
    )
    result = project.runpytest("--chaos")
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(
        [
            "agentic-chaos: chaos markers enabled",
            "*agentic-chaos*",
            "1 chaos test(s), 3 fault event(s), 1/1 passed their contracts",
        ]
    )


def test_contract_failure_fails_the_test(project: pytest.Pytester) -> None:
    project.makepyfile(
        test_weather="""
        import pytest
        from agentic_chaos.contracts import MaxRetries
        from agent import weather_agent

        @pytest.mark.chaos("rate_limit_storm", contracts=[MaxRetries(1)])
        def test_weather():
            assert weather_agent("?") == "sunny"
        """
    )
    result = project.runpytest("--chaos")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(
        [
            "*ContractViolationError*",
            "*[[]failed[]] max_retries: step 'llm' was retried 3 times in a row (limit 1)*",
        ]
    )


def test_unrecovered_test_error_is_reraised_with_contract_section(
    project: pytest.Pytester,
) -> None:
    project.makepyfile(
        test_weather="""
        import pytest
        from agent import weather_agent

        @pytest.mark.chaos(faults=["rate_limit_storm"], must_recover=True)
        def test_weather():
            weather_agent("?", attempts=2)
        """
    )
    result = project.runpytest("--chaos")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(
        [
            "*RuntimeError: gave up*",
            "*chaos contracts*",
            "*[[]failed[]] recovered_after_failure: RuntimeError escaped*",
        ]
    )


def test_profile_and_report_dir(project: pytest.Pytester) -> None:
    project.makefile(
        ".toml",
        chaos="""
        [profiles.ci]
        faults = ["rate_limit_storm"]

        [profiles.ci.parameters.rate_limit_storm]
        burst_count = 1
        """,
    )
    project.makepyfile(
        test_weather="""
        import pytest
        from agent import weather_agent

        @pytest.mark.chaos(profile="ci", contracts=["no_unhandled_error", "max_retries:1"])
        def test_weather():
            assert weather_agent("?") == "sunny"
        """
    )
    result = project.runpytest("--chaos", "--chaos-report-dir", "out")
    result.assert_outcomes(passed=1)
    out = project.path / "out"
    report = json.loads(artifact(out, "test_weather.py_test_weather", "chaos").read_text())
    assert len(report["chaos_events"]) == 1
    assert [call["status"] for call in report["calls"]] == ["error", "ok"]
    assert report["unhandled_error"] is None
    contracts = json.loads(artifact(out, "test_weather.py_test_weather", "contracts").read_text())
    assert contracts["passed"] is True
    assert contracts["nodeid"] == "test_weather.py::test_weather"
    assert [r["contract"] for r in contracts["results"]] == ["no_unhandled_error", "max_retries"]


def test_baseline_run_enables_comparative_contracts(project: pytest.Pytester) -> None:
    project.makepyfile(
        test_weather="""
        import pytest
        from agentic_chaos.contracts import MaxCostImpact
        from agent import weather_agent

        RUNS = []

        @pytest.mark.chaos(
            faults=["rate_limit_storm"],
            baseline=True,
            contracts=[MaxCostImpact(2, metric="calls")],
        )
        def test_weather(chaos):
            RUNS.append(chaos.session.dry_run)
            assert weather_agent("?") == "sunny"

        def test_ran_baseline_then_chaos():
            assert RUNS == [True, False]
        """
    )
    result = project.runpytest("--chaos", "--chaos-report-dir", "out", "-p", "no:randomly")
    result.assert_outcomes(passed=1, failed=1)
    result.stdout.fnmatch_lines(["*max_cost_impact: calls was 4.00x baseline, over 2x*"])
    assert artifact(project.path / "out", "test_weather.py_test_weather", "baseline").exists()


def test_failing_baseline_fails_with_clear_message(project: pytest.Pytester) -> None:
    project.makepyfile(
        test_weather="""
        import pytest

        @pytest.mark.chaos(faults=["rate_limit_storm"], baseline=True)
        def test_weather():
            raise ValueError("broken even without chaos")
        """
    )
    result = project.runpytest("--chaos")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(
        ["*chaos baseline run (no faults injected) failed: ValueError: broken even*"]
    )


def test_topology_from_auto_activated_tracker(project: pytest.Pytester) -> None:
    project.makepyfile(
        test_graph="""
        import pytest
        from agentic_chaos import TopologyTracker, wrap_node
        from agentic_chaos.agents.topology import get_active_tracker
        from agentic_chaos.contracts import FullTopologyTraversal

        @pytest.mark.chaos(
            faults=["tool_failure"],
            baseline=True,
            contracts=[FullTopologyTraversal()],
        )
        def test_graph(chaos):
            tracker = TopologyTracker()
            planner = wrap_node(lambda q: q, node_name="Planner", tracker=tracker,
                                caller_node="Router", faults=[])
            reviewer = wrap_node(lambda q: q, node_name="Reviewer", tracker=tracker,
                                 caller_node="Planner", faults=[])
            draft = planner("q")
            if chaos.session.dry_run:  # the "agent" skips review under chaos
                reviewer(draft)

        def test_tracker_was_reset():
            assert get_active_tracker() is None
        """
    )
    result = project.runpytest("--chaos", "-p", "no:randomly")
    result.assert_outcomes(passed=1, failed=1)
    result.stdout.fnmatch_lines(
        ["*full_topology_traversal: expected nodes never visited under chaos: Reviewer*"]
    )


def test_attach_topology_and_global_contract(project: pytest.Pytester) -> None:
    project.makepyfile(
        test_graph="""
        import pytest
        from agentic_chaos import TopologyTracker, wrap_tool

        @pytest.mark.chaos(faults=["tool_failure"])
        def test_graph(chaos):
            tracker = chaos.attach_topology(TopologyTracker(auto_activate=False))
            search = wrap_tool(lambda q: q, tool_name="search", tracker=tracker,
                               caller_node="Agent")
            try:
                search("q")
            except Exception:
                pass
            chaos.record_cost(0.01)
        """
    )
    result = project.runpytest(
        "--chaos",
        "--chaos-contract",
        "full_topology_traversal:expected_nodes=Agent|search",
        "--chaos-contract",
        "no_retry_storm:0",
        "--chaos-report-dir",
        "out",
    )
    result.assert_outcomes(passed=1)
    report = json.loads(
        artifact(project.path / "out", "test_graph.py_test_graph", "chaos").read_text()
    )
    assert {node["name"] for node in report["agent_topology"]["nodes"]} == {"Agent", "search"}
    assert report["cost_usd"] == 0.01


def test_ini_option_enables_chaos(project: pytest.Pytester) -> None:
    project.makeini("[pytest]\nchaos = true\n")
    project.makepyfile(
        test_weather="""
        import pytest
        from agentic_chaos.chaos.context import get_active_session

        @pytest.mark.chaos(faults="rate_limit_storm")
        def test_weather():
            assert get_active_session() is not None
        """
    )
    project.runpytest().assert_outcomes(passed=1)


def test_unmarked_tests_never_get_a_session(project: pytest.Pytester) -> None:
    project.makepyfile(
        test_plain="""
        from agentic_chaos.chaos.context import get_active_session

        def test_plain(chaos):
            assert get_active_session() is None
            assert not chaos.enabled
        """
    )
    project.runpytest("--chaos").assert_outcomes(passed=1)


def test_skip_and_xfail_pass_through(project: pytest.Pytester) -> None:
    project.makepyfile(
        test_flow="""
        import pytest

        @pytest.mark.chaos(faults=["rate_limit_storm"], must_recover=True)
        def test_skip():
            pytest.skip("not today")

        @pytest.mark.chaos(faults=["rate_limit_storm"], must_recover=True)
        @pytest.mark.xfail(strict=True)
        def test_xfail():
            raise RuntimeError("expected")
        """
    )
    project.runpytest("--chaos").assert_outcomes(skipped=1, xfailed=1)


def test_fault_instances_get_fresh_state_per_test(project: pytest.Pytester) -> None:
    project.makepyfile(
        test_weather="""
        import pytest
        from agentic_chaos import RateLimitStormFault
        from agent import weather_agent

        FAULT = RateLimitStormFault(burst_count=2)

        @pytest.mark.parametrize("n", [1, 2])
        @pytest.mark.chaos(faults=[FAULT], contracts=["recovered_after_failure"])
        def test_weather(n, chaos):
            assert weather_agent("?") == "sunny"
            assert len(chaos.session.events) == 2

        def test_original_untouched():
            assert FAULT._fired == 0
        """
    )
    project.runpytest("--chaos").assert_outcomes(passed=3)


@pytest.mark.parametrize(
    ("marker", "message"),
    [
        ("chaos()", "give exactly one of faults"),
        ("chaos(faults=['x'], profile='p')", "give exactly one of faults"),
        ("chaos(faults=['nope'])", "Unknown fault 'nope'"),
        ("chaos(faults='')", "at least one fault"),
        ("chaos('a', 'b')", "only positional"),
        ("chaos('rate_limit_storm', faults=['token_timeout'])", "both positionally"),
        ("chaos(faults=['rate_limit_storm'], colour='red')", "unknown argument"),
        ("chaos(faults=['rate_limit_storm'], contracts=['bogus'])", "Unknown contract"),
        ("chaos(faults=['rate_limit_storm'], contracts=[1])", "Contract instances"),
        ("chaos(faults=['rate_limit_storm'], baseline=True, dry_run=True)", "drop dry_run"),
        ("chaos(profile='missing', profile_file='nope.toml')", "nope.toml"),
    ],
)
def test_invalid_markers_fail_the_test(project: pytest.Pytester, marker: str, message: str) -> None:
    project.makepyfile(
        test_bad=f"""
        import pytest

        @pytest.mark.{marker}
        def test_bad():
            pass
        """
    )
    result = project.runpytest("--chaos")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([f"*invalid @pytest.mark.chaos*{message}*"])


def test_single_contract_instance_and_dry_run(project: pytest.Pytester) -> None:
    project.makepyfile(
        test_weather="""
        import pytest
        from agentic_chaos.contracts import NoUnhandledError
        from agent import weather_agent

        @pytest.mark.chaos(faults=["rate_limit_storm"], dry_run=True,
                           contracts=NoUnhandledError())
        def test_weather(chaos):
            assert weather_agent("?") == "sunny"
            assert chaos.session.events == []
            assert len(chaos.session.planned_events) == 1
        """
    )
    project.runpytest("--chaos").assert_outcomes(passed=1)


def test_plugin_can_be_disabled(project: pytest.Pytester) -> None:
    project.makepyfile(test_plain="def test_plain():\n    pass\n")
    result = project.runpytest("-p", "no:agentic_chaos", "--chaos")
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*unrecognized arguments: --chaos*"])


ISOLATED_ASYNC_RUNNER = """
import asyncio
import contextvars
import inspect

import pytest

# Like pytest-asyncio and anyio, run test coroutines in a context captured
# before any chaos session exists.
LOOP_CONTEXT = contextvars.copy_context()


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    if not inspect.iscoroutinefunction(pyfuncitem.obj):
        return None
    kwargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
    LOOP_CONTEXT.run(asyncio.run, pyfuncitem.obj(**kwargs))
    return True
"""


def test_async_tests_see_the_session_inside_their_event_loop(project: pytest.Pytester) -> None:
    project.makeconftest(ISOLATED_ASYNC_RUNNER)
    project.makepyfile(
        test_async="""
        import pytest
        from agentic_chaos import TopologyTracker, chaos_acall
        from agentic_chaos.chaos.faults import RateLimitStormError

        @pytest.mark.chaos(faults=["rate_limit_storm"], baseline=True, must_recover=True,
                           contracts=["max_retries:3", "full_topology_traversal"])
        async def test_async(chaos):
            async def llm():
                return "ok"

            tracker = TopologyTracker()
            tracker.record_edge("Agent", "llm")
            for _ in range(5):
                try:
                    assert await chaos_acall(llm, step_name="llm") == "ok"
                    break
                except RateLimitStormError:
                    pass
            assert len(chaos.session.events) == (0 if chaos.session.dry_run else 3)
        """
    )
    result = project.runpytest("--chaos", "--chaos-report-dir", "out")
    result.assert_outcomes(passed=1)
    report = json.loads(
        artifact(project.path / "out", "test_async.py_test_async", "chaos").read_text()
    )
    assert len(report["chaos_events"]) == 3
    assert {node["name"] for node in report["agent_topology"]["nodes"]} == {"Agent", "llm"}


def test_artifact_names_stay_unique_after_sanitizing(project: pytest.Pytester) -> None:
    project.makepyfile(
        test_ids="""
        import pytest

        @pytest.mark.parametrize("value", ["a/b", "a:b", "a_b"])
        @pytest.mark.chaos(faults=["rate_limit_storm"])
        def test_ids(value):
            pass
        """
    )
    project.runpytest("--chaos", "--chaos-report-dir", "out").assert_outcomes(passed=3)
    names = sorted(path.name for path in (project.path / "out").glob("*.chaos.json"))
    assert len(names) == 3
    assert all(name.startswith("test_ids.py_test_ids_a_b-") for name in names)


@pytest.mark.parametrize("entry", ["None", "1", "['rate_limit_storm', 2]"])
def test_non_string_fault_entries_are_validation_errors(
    project: pytest.Pytester, entry: str
) -> None:
    faults = entry if entry.startswith("[") else f"[{entry}]"
    project.makepyfile(
        test_bad=f"""
        import pytest

        @pytest.mark.chaos(faults={faults})
        def test_bad():
            pass
        """
    )
    result = project.runpytest("--chaos")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*invalid @pytest.mark.chaos: faults entries must be*"])


SHARED_CONTEXT_RUNNER = """
import contextvars
import inspect

import pytest

# A context that outlives each test, like a module- or session-scoped event
# loop. Coroutines are driven in it directly, so whatever they leave set stays.
SHARED = contextvars.copy_context()


def drive(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as stop:
        return stop.value


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    if not inspect.iscoroutinefunction(pyfuncitem.obj):
        return None
    kwargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
    SHARED.run(drive, pyfuncitem.obj(**kwargs))
    return True
"""


def test_async_tracker_is_deactivated_in_a_shared_loop_context(
    project: pytest.Pytester,
) -> None:
    project.makeconftest(SHARED_CONTEXT_RUNNER)
    project.makepyfile(
        test_async="""
        import pytest
        from agentic_chaos import TopologyTracker
        from agentic_chaos.agents.topology import get_active_tracker

        @pytest.mark.chaos(faults=["rate_limit_storm"])
        async def test_creates_tracker():
            TopologyTracker().record_edge("A", "B")

        async def test_loop_context_is_clean():
            assert get_active_tracker() is None
        """
    )
    project.runpytest("--chaos", "-p", "no:randomly").assert_outcomes(passed=2)
