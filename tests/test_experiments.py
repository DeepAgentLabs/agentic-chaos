"""v0.8 declarative experiments: loading, located validation, templates and runs."""

import json
import textwrap

import pytest

from agentic_chaos import RateLimitStormFault, Scope
from agentic_chaos.chaos.advanced import FaultCascade
from agentic_chaos.contracts import CompletesWithin, MaxRetries, RecoveredAfterFailure
from agentic_chaos.experiments import (
    ExperimentError,
    LazyTarget,
    compile_document,
    load_experiment,
    read_document,
    validate_experiment,
)
from agentic_chaos.workflows import HealthCheck, Parallel, Step, Suspend

APP = textwrap.dedent(
    """
    from agentic_chaos import chaos_call
    from agentic_chaos.chaos.faults import RateLimitStormError

    CALLS = []

    def handle():
        for _ in range(8):
            try:
                return chaos_call(lambda: "answer", step_name="llm")
            except RateLimitStormError:
                continue
        raise RuntimeError("gave up")

    def ping(query="ping"):
        CALLS.append(query)
        return f"pong {query}"

    if __name__ == "__main__":
        handle()
    """
)


@pytest.fixture
def app(tmp_path):
    (tmp_path / "app.py").write_text(APP)
    return tmp_path


def write(directory, name, content):
    path = directory / name
    path.write_text(textwrap.dedent(content) if isinstance(content, str) else json.dumps(content))
    return path


def messages(result):
    return {issue.location: issue.message for issue in result.issues}


def test_single_step_yaml_experiment_compiles_and_runs(app):
    path = write(
        app,
        "rate-limit.yaml",
        """
        name: rate-limit-recovery
        description: retries absorb a 429 storm
        target: app.py:handle
        faults:
          - type: rate_limit_storm
            burst_count: 5
            retry_after: 1.0
          - type: token_timeout
            hang_seconds: 0
            probability: 0.3
            seed: 4
        assertions:
          - completes_within: 30
          - max_retries: {n: 5, step: llm}
          - recovered_after_failure: true
          - no_unhandled_error
        schedule:
          cron: "0 2 * * *"
        """,
    )
    result = validate_experiment(path)
    assert result.ok, result.issues
    experiment = result.experiment
    assert experiment.name == "rate-limit-recovery"
    assert experiment.kind == "experiment"
    assert experiment.schedule.expression == "0 2 * * *"
    (step,) = experiment.workflow.nodes
    assert isinstance(step, Step)
    assert [type(f).__name__ for f in step.faults] == ["RateLimitStormFault", "TokenTimeoutFault"]
    assert step.faults[1].probability == 0.3
    contracts = step.contracts
    assert [type(c) for c in contracts[:3]] == [CompletesWithin, MaxRetries, RecoveredAfterFailure]
    assert contracts[1].step == "llm"

    single = write(
        app,
        "single.yaml",
        """
        name: storm
        target: app.py:handle
        faults: [{type: rate_limit_storm, burst_count: 3}]
        assertions: [recovered_after_failure, {max_retries: 3}]
        """,
    )
    report = load_experiment(single).run()
    assert report.status == "passed"
    assert report.experiment["name"] == "storm"
    assert report.experiment["kind"] == "experiment"
    assert len(report.chaos_events) == 3


def test_script_targets_run_as_main(app):
    path = write(
        app,
        "script.json",
        {"name": "script", "target": "app.py", "faults": ["rate_limit_storm"], "repeat": 2},
    )
    report = load_experiment(path).run()
    assert report.status == "passed"
    assert len(report.node("script").report["calls"]) == 5  # 3 rejected + 2 answered


def test_workflow_experiment_with_templates_parallel_and_suspend(app):
    path = write(
        app,
        "suite.yaml",
        """
        name: resilience-suite
        target: app.py:handle
        scope: {exclude_steps: [safety_check]}
        safety: {max_injections: 50}
        templates:
          escalate:
            params: {burst: 2}
            steps:
              - step:
                  name: storm
                  faults: [{type: rate_limit_storm, burst_count: "${burst}"}]
                  assertions: [{max_retries: "${burst}"}]
              - health_check: {name: "ping-${burst}", target: "app.py:ping", query: "up?"}
        workflow:
          - use: {template: escalate, name: warm-up}
          - parallel:
              name: fan-out
              branches:
                - step: {name: tools, faults: [{type: tool_failure, tool_name: search}]}
                - - step: {name: memory, faults: [{type: silent_degradation, seed: 1}]}
                  - health_check: {target: "app.py:ping"}
          - suspend: {name: approve-blast, reason: shared staging}
          - use: {template: escalate, name: full-blast, with: {burst: 6}}
          - step:
              name: cascade
              faults:
                - type: cascade
                  first: {type: rate_limit_storm, burst_count: 1}
                  then: {type: token_timeout, hang_seconds: 0, mode: delay}
                  delay_between: 0
        """,
    )
    experiment = load_experiment(path)
    assert experiment.kind == "workflow"
    workflow = experiment.workflow
    assert workflow.node_names == [
        "warm-up/storm",
        "warm-up/ping-2",
        "fan-out",
        "tools",
        "memory",
        "health-check-1",
        "approve-blast",
        "full-blast/storm",
        "full-blast/ping-6",
        "cascade",
    ]
    assert workflow.scope == Scope(exclude_steps=["safety_check"])
    assert workflow.breaker.max_injections == 50
    storm = workflow.nodes[0]
    assert storm.faults[0].burst_count == 2  # "${burst}" keeps the integer type
    assert storm.contracts[0].n == 2
    assert isinstance(workflow.nodes[2], Parallel)
    assert isinstance(workflow.nodes[3], Suspend)
    assert isinstance(workflow.nodes[-1].faults[0], FaultCascade)
    health = workflow.nodes[1]
    assert isinstance(health, HealthCheck) and isinstance(health.fn, LazyTarget)

    first = experiment.run()
    assert first.status == "suspended"
    assert first.suspended_at == "approve-blast"
    assert first.node("warm-up/ping-2").output == "'pong up?'"
    resumed = experiment.run(resume_from="approve-blast")
    assert resumed.status == "passed", [(n.name, n.message) for n in resumed.walk()]
    assert len(resumed.node("full-blast/storm").report["chaos_events"]) == 6
    approved = experiment.run(approve=["approve-blast"])
    assert approved.status == "passed"
    preview = experiment.run(dry_run=True)
    assert preview.status == "passed" and preview.chaos_events == []


def test_validation_reports_every_problem_with_locations(app):
    path = write(
        app,
        "broken.yaml",
        """
        name: broken
        target: app.py:missing_fn
        unknown_top: 1
        faults:
          - type: rate_limt_storm
          - type: rate_limit_storm
            burst_count: -1
            retry_afterr: 2
          - type: token_timeout
            probability: 1.5
          - type: silent_degradation
            degrade_fn: x
          - type: tool_failure
            mode: explode
          - type: tool_failure
            scope: {step: [a]}
          - 42
        assertions:
          - max_retrys: 3
          - completes_within: false
          - full_topology_traversal: 3
          - max_retries: {n: 1, foo: 2}
          - completes_within: -5
        schedule: {cron: "61 * * * *", timezone: Mars/Base}
        """,
    )
    result = validate_experiment(path)
    assert not result.ok
    found = messages(result)
    assert "did you mean 'faults'" not in found.get("unknown_top", "")
    assert found["unknown_top"] == "unknown field"
    assert "is not defined at the top level" in found["target"]
    assert (
        found["faults[0].type"]
        == "unknown fault 'rate_limt_storm'; did you mean 'rate_limit_storm'?"
    )
    assert "out of range" in found["faults[1].burst_count"]
    assert "did you mean 'retry_after'" in found["faults[1].retry_afterr"]
    assert "between 0 and 1" in found["faults[2].probability"]
    assert "Python callable" in found["faults[3].degrade_fn"]
    assert "mode must be" in found["faults[4]"]
    assert "unknown scope field" in found["faults[5].scope"]
    assert "fault name or a mapping" in found["faults[6]"]
    assert "did you mean 'max_retries'" in found["assertions[0]"]
    assert "remove it to disable" in found["assertions[1].completes_within"]
    assert "takes no value" in found["assertions[2].full_topology_traversal"]
    assert "unknown parameter" in found["assertions[3].max_retries.foo"]
    assert "positive" in found["assertions[4].completes_within"]
    assert "outside 0-59" in found["schedule.cron"]
    assert "unknown time zone" in found["schedule.timezone"]
    assert result.experiment is None
    with pytest.raises(ExperimentError) as raised:
        load_experiment(path)
    assert "faults[0].type" in str(raised.value)


def test_workflow_node_validation(app):
    document = {
        "name": "nodes",
        "target": "app.py:handle",
        "faults": ["rate_limit_storm"],
        "assertions": [],
        "templates": {"unused": {"steps": [{"suspend": {"name": "x"}}]}, "bad": []},
        "workflow": [
            {"step": {"faults": ["rate_limit_storm"]}},
            {"stepp": {}},
            {"step": {"name": "a"}, "suspend": {}},
            {"parallel": {"branches": [{"step": {"name": "only"}}]}},
            {"health_check": {"target": "app.py", "query": "hi"}},
            {"use": {"template": "missing"}},
            {"use": {"template": "unused", "with": {"nope": 1}}},
            {"step": {"name": "t", "target": "nowhere.py"}},
            {"suspend": {"name": "s", "reason": 3}},
            {"health_check": {"retries": -1, "expect_success": "yes"}},
        ],
    }
    result = validate_experiment(document, base_dir=app)
    found = messages(result)
    assert found["faults"] == "belongs to a step in workflow experiments"
    assert found["assertions"] == "belongs to a step in workflow experiments"
    assert found["templates.bad"].startswith("must be a mapping")
    assert found["workflow[0].step.name"] == "must be a non-empty string"
    assert "did you mean 'step'" in found["workflow[1]"]
    assert "one-key mapping" in found["workflow[2]"]
    assert "at least two branches" in found["workflow[3].parallel.branches"]
    assert "function target" in found["workflow[4].health_check.query"]
    assert "unknown template 'missing'" in found["workflow[5].use.template"]
    assert found["workflow[6].use.with.nope"] == "unknown parameter"
    assert "target file not found" in found["workflow[7].step.target"]
    assert found["workflow[8].suspend.reason"] == "must be a string"
    assert ">= 0" in found["workflow[9].health_check.retries"]
    assert found["workflow[9].health_check.expect_success"] == "must be true or false"


def test_template_parameter_errors_and_recursion(app):
    document = {
        "name": "templates",
        "target": "app.py:handle",
        "templates": {
            "uses_missing": {"steps": [{"step": {"name": "s", "faults": ["${fault}"]}}]},
            "loop": {"steps": [{"use": {"template": "loop"}}]},
            "literal": {"steps": [{"step": {"name": "cost $${not_a_param}", "faults": []}}]},
        },
        "workflow": [
            {"use": {"template": "uses_missing"}},
            {"use": {"template": "loop"}},
            {"use": {"template": "literal"}},
        ],
    }
    result = validate_experiment(document, base_dir=app)
    found = messages(result)
    assert "undefined ${fault}" in found["workflow[0].use"]
    assert (
        "recursive template use: loop -> loop"
        in found["workflow[1].use<loop>.steps[0].use.template"]
    )
    ok = {**document, "workflow": [{"use": {"template": "literal"}}]}
    del ok["templates"]["uses_missing"], ok["templates"]["loop"]
    compiled = load_experiment(ok, base_dir=app)
    assert compiled.workflow.node_names == ["literal/cost ${not_a_param}"]


def test_unused_templates_and_impossible_schedules_are_warnings(app):
    document = {
        "name": "warn",
        "target": "app.py:handle",
        "faults": ["rate_limit_storm"],
        "templates": {"spare": {"steps": [{"suspend": {"name": "gate"}}]}},
        "schedule": "0 0 31 2 *",
    }
    result = validate_experiment(document, base_dir=app)
    assert result.ok
    assert {str(w) for w in result.warnings} == {
        "templates.spare: warning: is defined but never used",
        "schedule.cron: warning: this schedule never fires",
    }
    assert result.experiment.warnings == result.warnings


def test_missing_requirements(app):
    found = messages(validate_experiment({"faults": []}, base_dir=app))
    assert found["name"] == "must be a non-empty string"
    assert found["target"] == "is required"
    assert found["faults"] == "must list at least one fault"
    found = messages(validate_experiment({"name": "x", "target": "app.py"}, base_dir=app))
    assert found["<document>"] == "needs either 'faults' or a 'workflow'"
    found = messages(
        validate_experiment({"name": "x", "version": 2, "faults": ["a"]}, base_dir=app)
    )
    assert "unsupported experiment version" in found["version"]
    found = messages(validate_experiment(["not", "a", "mapping"]))
    assert "mapping at the top level" in found["<document>"]
    found = messages(validate_experiment({"name": "x", "workflow": [{"step": {"name": "s"}}]}))
    assert "has no target" in found["workflow[0].step"]


def test_duplicate_node_names_are_reported(app):
    document = {
        "name": "dup",
        "target": "app.py:handle",
        "workflow": [{"step": {"name": "a"}}, {"step": {"name": "a"}}],
    }
    found = messages(validate_experiment(document, base_dir=app))
    assert "duplicate workflow node name 'a'" in found["workflow"]


def test_target_checks_can_be_skipped_and_never_execute(app):
    (app / "explode.py").write_text("raise SystemExit('executed!')\ndef handle():\n    return 1\n")
    document = {"name": "x", "target": "explode.py:handle", "faults": ["rate_limit_storm"]}
    assert validate_experiment(document, base_dir=app).ok  # parsed, not imported
    (app / "syntax.py").write_text("def broken(:\n")
    broken = {**document, "target": "syntax.py:broken"}
    assert "syntax error" in messages(validate_experiment(broken, base_dir=app))["target"]
    assert validate_experiment(broken, base_dir=app, check_targets=False).ok
    module = {**document, "target": "json:dumps"}
    assert validate_experiment(module, base_dir=app).ok
    missing = {**document, "target": "no_such_module_xyz:run"}
    assert "not importable" in messages(validate_experiment(missing, base_dir=app))["target"]
    bare = {**document, "target": "json"}
    assert "need a function" in messages(validate_experiment(bare, base_dir=app))["target"]


def test_file_formats(app):
    toml = write(
        app,
        "exp.toml",
        """
        name = "toml-experiment"
        target = "app.py:handle"

        [[faults]]
        type = "rate_limit_storm"
        burst_count = 2

        [schedule]
        cron = "@nightly"
        """,
    )
    found = messages(validate_experiment(toml))
    assert "@nightly" in found["schedule.cron"]
    toml.write_text(toml.read_text().replace("@nightly", "@daily"))
    assert load_experiment(toml).workflow.nodes[0].faults[0].burst_count == 2
    bad_yaml = write(app, "bad.yaml", "name: [unclosed\n")
    assert "invalid YAML" in str(validate_experiment(bad_yaml).issues[0])
    bad_json = write(app, "bad.json", "{")
    assert "invalid JSON" in str(validate_experiment(bad_json).issues[0])
    bad_toml = write(app, "bad.toml", "name = \n")
    assert "invalid TOML" in str(validate_experiment(bad_toml).issues[0])
    other = write(app, "exp.ini", "x")
    assert "unsupported file type" in str(validate_experiment(other).issues[0])
    assert "No such file" in str(validate_experiment(app / "missing.yaml").issues[0])
    with pytest.raises(ExperimentError):
        read_document(other)


def test_yaml_without_pyyaml_explains_the_extra(app, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_yaml(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("no yaml")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_yaml)
    path = write(app, "x.yaml", "name: x\n")
    assert "agentic-chaos[yaml]" in str(validate_experiment(path).issues[0])


def test_scoped_faults_and_safety_in_documents(app):
    document = {
        "name": "scoped",
        "target": "app.py:handle",
        "faults": [{"type": "rate_limit_storm", "scope": {"exclude_steps": ["llm"]}}],
        "safety": {"max_injections": 1, "failure_window": 5, "min_calls": 2, "bogus": 1},
    }
    found = messages(validate_experiment(document, base_dir=app))
    assert found == {"safety.bogus": "unknown field"}
    del document["safety"]["bogus"]
    experiment = load_experiment(document, base_dir=app)
    assert experiment.workflow.nodes[0].faults[0].scope == Scope(exclude_steps=["llm"])
    assert experiment.workflow.breaker.window_size == 5
    report = experiment.run()
    assert report.status == "passed"
    assert report.chaos_events == []  # every call was outside the fault's scope
    bad = {**document, "safety": {"max_injections": 0}}
    assert "positive integer" in messages(validate_experiment(bad, base_dir=app))["safety"]


def test_compile_document_returns_issues_without_raising():
    experiment, issues = compile_document({"name": 5})
    assert experiment is None
    assert any(issue.location == "name" for issue in issues)
    assert str(issues[0]).startswith(issues[0].location)


def test_lazy_target_resolves_once(app):
    target = LazyTarget("app.py:ping", app)
    assert not target.is_script
    assert target("a") == "pong a"
    assert target.resolve() is target.resolve()
    assert "app.py:ping" in repr(target)
    assert LazyTarget("app.py", app).is_script


def test_python_fault_instances_are_untouched_by_documents():
    fault = RateLimitStormFault()
    assert fault.scope is None
