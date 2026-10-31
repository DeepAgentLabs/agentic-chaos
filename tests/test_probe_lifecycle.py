"""v0.9 probe lifecycle: chaos_run(), ChaosWorkflow probes and experiment probes."""

import json
import textwrap

import pytest

from agentic_chaos import (
    RateLimitStormFault,
    ResilienceHistory,
    chaos_call,
    chaos_run,
    chaos_session,
)
from agentic_chaos.chaos.context import get_active_session
from agentic_chaos.chaos.faults import RateLimitStormError
from agentic_chaos.experiments import load_experiment, validate_experiment
from agentic_chaos.probes import FunctionProbe, LatencyProbe, ResponseQualityProbe
from agentic_chaos.workflows import ChaosWorkflow, Step, Suspend, WorkflowReport


def agent(query: str = "2+2") -> str:
    for _ in range(6):
        try:
            return chaos_call(lambda: f"{query} = 4", step_name="llm")
        except RateLimitStormError:
            continue
    raise RuntimeError("model unavailable")


def storm(burst: int = 2) -> RateLimitStormFault:
    return RateLimitStormFault(burst_count=burst, retry_after=0)


# -- chaos_run ----------------------------------------------------------------


def test_chaos_run_runs_every_phase_in_order() -> None:
    seen: list[tuple[str, bool]] = []

    def watch(phase_hint: str):
        def check() -> str:
            seen.append((phase_hint, get_active_session() is not None))
            return "ok"

        return check

    probes = [
        FunctionProbe(watch("pre"), name="pre", phases="pre"),
        FunctionProbe(watch("during"), name="during", phases="during"),
        FunctionProbe(watch("post"), name="post", phases="post"),
    ]
    report = chaos_run(agent, [storm()], probes=probes, name="ordered")
    assert seen == [("pre", False), ("during", True), ("post", False)]
    assert [p["phase"] for p in report.probes] == ["pre", "during", "post"]
    assert report.name == "ordered" and len(report.chaos_events) == 2


def test_chaos_run_scores_a_recovering_agent() -> None:
    report = chaos_run(
        agent,
        [storm(3)],
        probes=[
            ResponseQualityProbe(agent, "2+2", expect_contains="4"),
            LatencyProbe(agent, "hi", max_ms=1000),
        ],
    )
    assert report.resilience_score == 100
    assert report.resilience is not None and report.resilience["grade"] == "A"
    assert report.resilience["faults"][0]["verdicts"] == {"retried": 3}


def test_failed_pre_probe_skips_chaos_and_is_inconclusive() -> None:
    ran = {"target": False}

    def target() -> None:
        ran["target"] = True

    report = chaos_run(target, [storm()], probes=[FunctionProbe(lambda: 1 / 0, name="health")])
    assert not ran["target"] and report.chaos_events == []
    assert [p["phase"] for p in report.probes] == ["pre"]
    assert report.resilience_score is None
    assert report.resilience["reasons"][-1] == "chaos was not injected"


def test_require_steady_state_false_runs_chaos_anyway() -> None:
    flaky = iter([RuntimeError("cold start"), None, None])

    def warming() -> str:
        error = next(flaky)
        if error:
            raise error
        return "ok"

    report = chaos_run(
        agent, [storm()], probes=[FunctionProbe(warming)], require_steady_state=False
    )
    assert len(report.chaos_events) == 2
    assert report.resilience_score is None  # still no steady state to recover to


def test_chaos_run_records_crashes_and_post_probe_failures() -> None:
    def fragile() -> str:
        return chaos_call(lambda: "x", step_name="llm")

    healthy = {"value": True}

    def degraded_after() -> str:
        if not healthy["value"]:
            raise ConnectionError("still down")
        healthy["value"] = False  # pre passes, post fails
        return "ok"

    report = chaos_run(fragile, [storm(1)], probes=[FunctionProbe(degraded_after)])
    assert report.unhandled_error is not None
    assert report.probes[-1]["status"] == "failed"
    assert report.resilience_score == 0


def test_chaos_run_repeat_history_and_baseline(tmp_path) -> None:
    history = tmp_path / "h.json"
    baseline = chaos_run(agent, [storm(0)], name="nightly")
    first = chaos_run(agent, [storm()], repeat=3, history=history, name="nightly")
    assert first.resilience["trend"] is None
    second = chaos_run(
        agent, [storm()], history=ResilienceHistory(history), name="nightly", baseline=baseline
    )
    assert second.resilience["trend"]["previous"] == first.resilience_score
    assert second.resilience["baseline_report_id"] == baseline.id
    assert len(ResilienceHistory(history).entries("nightly")) == 2


def test_chaos_run_validation() -> None:
    with pytest.raises(ValueError, match="callable"):
        chaos_run("agent", [storm()])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="repeat"):
        chaos_run(agent, [storm()], repeat=0)
    with pytest.raises(ValueError, match="duplicate probe name"):
        chaos_run(agent, [storm()], probes=[FunctionProbe(agent), FunctionProbe(agent)])
    with chaos_session([storm()]), pytest.raises(RuntimeError, match="active chaos_session"):
        chaos_run(agent, [storm()])


def test_chaos_run_dry_run_is_inconclusive() -> None:
    report = chaos_run(agent, [storm()], dry_run=True)
    assert report.dry_run and report.planned_events
    assert report.resilience_score is None


# -- workflows --------------------------------------------------------------------


def test_workflow_probes_wrap_the_stages() -> None:
    workflow = ChaosWorkflow(
        "suite",
        [Step("warm-up", faults=[storm()]), Step("escalate", faults=[storm(4)])],
        target=agent,
        probes=[ResponseQualityProbe(agent, "q", expect_contains="4", phases=PHASES)],
    )
    report = workflow.run()
    assert report.status == "passed"
    assert [(p["phase"], p.get("step")) for p in report.probes] == [
        ("pre", None),
        ("during", "warm-up"),
        ("during", "escalate"),
        ("post", None),
    ]
    assert report.resilience_score == 100
    merged = report.to_chaos_report()
    assert merged.probes == report.probes and merged.resilience == report.resilience
    assert WorkflowReport.model_validate_json(report.model_dump_json()).resilience_score == 100


PHASES = ["pre", "during", "post"]


def test_workflow_halts_before_chaos_when_pre_probes_fail() -> None:
    workflow = ChaosWorkflow(
        "suite",
        [Step("warm-up", faults=[storm()])],
        target=agent,
        probes=[FunctionProbe(lambda: 1 / 0, name="health")],
    )
    report = workflow.run()
    assert report.status == "halted" and "pre-chaos probes failed (health)" in report.message
    assert report.node("warm-up").status == "skipped"
    assert report.chaos_events == [] and report.resilience_score is None


def test_workflow_scores_without_probes_and_records_history(tmp_path) -> None:
    workflow = ChaosWorkflow("plain", [Step("s", faults=[storm()])], target=agent)
    report = workflow.run(history=tmp_path / "h.json")
    assert report.resilience_score == 100
    assert ResilienceHistory(tmp_path / "h.json").latest("plain")["score"] == 100


def test_suspended_workflows_are_not_recorded_and_skip_post_probes(tmp_path) -> None:
    workflow = ChaosWorkflow(
        "gated",
        [Step("s", faults=[storm()]), Suspend("gate"), Step("t", faults=[storm()])],
        target=agent,
        probes=[FunctionProbe(agent, name="ping")],
    )
    report = workflow.run(history=tmp_path / "h.json")
    assert report.status == "suspended"
    assert [p["phase"] for p in report.probes] == ["pre"]
    assert not (tmp_path / "h.json").exists()


def test_workflow_validates_probes_and_weights() -> None:
    with pytest.raises(ValueError, match="Probe instances"):
        ChaosWorkflow("w", [Step("s")], probes=[agent])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="unknown resilience component"):
        ChaosWorkflow("w", [Step("s")], weights={"speed": 1})
    custom = ChaosWorkflow("w", [Step("s", faults=[storm()])], target=agent, weights={"cost": 1})
    assert custom.run().resilience["components"][4]["weight"] == 1.0


# -- experiments ------------------------------------------------------------------

APP = textwrap.dedent(
    """
    from agentic_chaos import chaos_call
    from agentic_chaos.chaos.faults import RateLimitStormError

    def handle(query="2+2"):
        for _ in range(6):
            try:
                return chaos_call(lambda: f"{query} = 4", step_name="llm")
            except RateLimitStormError:
                continue
        raise RuntimeError("down")

    def ping():
        return "pong"
    """
)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "app.py").write_text(APP)
    return tmp_path


def write(project, data) -> object:
    path = project / "experiment.json"
    path.write_text(json.dumps(data))
    return path


def test_experiment_probes_and_resilience_compile_and_run(project) -> None:
    path = write(
        project,
        {
            "name": "probed",
            "target": "app.py:handle",
            "faults": [{"type": "rate_limit_storm", "burst_count": 2, "retry_after": 0}],
            "probes": [
                {"type": "response_quality", "query": "2+2", "expect_contains": "4"},
                {"type": "latency", "name": "fast", "max_ms": 2000, "samples": 2},
                {"type": "function", "target": "app.py:ping", "phases": ["pre", "during", "post"]},
            ],
            "resilience": {
                "min_score": 80,
                "weights": {"cost": 0},
                "history": {"path": str(project / "h.json"), "max_runs": 5},
            },
        },
    )
    experiment = load_experiment(path)
    assert experiment.min_score == 80 and experiment.history is not None
    assert experiment.metadata()["min_score"] == 80
    assert [p.name for p in experiment.workflow.probes] == ["handle quality", "fast", "ping"]
    report = experiment.run()
    assert report.status == "passed" and report.resilience_score == 100
    assert len(report.probes) == 7
    assert ResilienceHistory(project / "h.json").latest("probed")["score"] == 100


def test_experiment_history_accepts_a_plain_path(project) -> None:
    path = write(
        project,
        {
            "name": "p",
            "target": "app.py:handle",
            "faults": ["rate_limit_storm"],
            "resilience": {"history": str(project / "plain.json")},
        },
    )
    assert load_experiment(path).history.path == project / "plain.json"


def test_experiment_probe_validation_is_located(project) -> None:
    path = write(
        project,
        {
            "name": "bad",
            "target": "app.py:handle",
            "faults": ["rate_limit_storm"],
            "probes": [
                {"type": "htp", "url": "http://x"},
                {"type": "http", "url": "ftp://x"},
                {"type": "http", "url": "http://x", "bogus": 1},
                {"type": "latency"},
                {"type": "response_quality", "target": "app.py", "expect_contains": "x"},
                {"type": "response_quality", "expect_regex": "("},
                {"type": "function", "target": "app.py:missing"},
                "http://x",
            ],
            "resilience": {
                "min_score": 101,
                "weights": {"speed": 1},
                "history": {"path": "h.json", "max_age_days": -1, "extra": 1},
                "gate": True,
            },
        },
    )
    messages = {str(issue) for issue in validate_experiment(path).issues}
    expected = [
        "probes[0].type: unknown probe type 'htp'; did you mean 'http'?",
        "probes[1]: invalid http probe: url must be an absolute",
        "probes[2].bogus: unknown field",
        "probes[3]: invalid latency probe:",
        "probes[4].target: needs a function target",
        "probes[5].expect_regex: is not a valid regex",
        "probes[6].target: 'missing' is not defined",
        "probes[7]: must be a mapping with a 'type'",
        "resilience.min_score: must be a number between 0 and 100",
        "resilience.weights: unknown resilience component 'speed'",
        "resilience.history.extra: unknown field",
        "resilience.history: max_age_days must be a finite number > 0",
        "resilience.gate: unknown field",
    ]
    for prefix in expected:
        assert any(message.startswith(prefix) for message in messages), (prefix, messages)


def test_experiment_probes_need_a_target(project) -> None:
    path = write(
        project,
        {
            "name": "w",
            "workflow": [{"step": {"name": "s", "target": "app.py:handle"}}],
            "probes": [{"type": "function"}, {"type": "function", "name": "a"}],
            "resilience": "strict",
        },
    )
    messages = [str(issue) for issue in validate_experiment(path).issues]
    assert any(m.startswith("probes[0]: has no target") for m in messages)
    assert any(m.startswith("resilience: must be a mapping") for m in messages)


def test_experiment_rejects_duplicate_probe_names(project) -> None:
    path = write(
        project,
        {
            "name": "dup",
            "target": "app.py:handle",
            "faults": ["rate_limit_storm"],
            "probes": [{"type": "function"}, {"type": "function"}],
        },
    )
    messages = [str(issue) for issue in validate_experiment(path).issues]
    assert "probes: duplicate probe name 'handle'; give each probe a 'name'" in messages


def test_chaos_run_validates_weights_before_injecting() -> None:
    ran = {"target": False}

    def target() -> None:
        ran["target"] = True

    with pytest.raises(ValueError, match="unknown resilience component 'speed'"):
        chaos_run(target, [storm()], weights={"speed": 1})
    assert not ran["target"]


def test_experiment_http_probes_accept_a_body(project) -> None:
    path = write(
        project,
        {
            "name": "post",
            "target": "app.py:handle",
            "faults": ["rate_limit_storm"],
            "probes": [{"type": "http", "url": "http://x/h", "method": "POST", "body": "{}"}],
        },
    )
    (probe,) = load_experiment(path).workflow.probes
    assert probe.method == "POST" and probe.body == b"{}"
