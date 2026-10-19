"""v0.8 CLI: experiment validate/run/schedule, chaos workflow, agent fuzz."""

import json
import textwrap

import pytest
from typer.testing import CliRunner

from agentic_chaos.cli.main import EXIT_SUSPENDED, app
from agentic_chaos.models import ChaosReport
from agentic_chaos.workflows import FuzzReport, WorkflowReport

runner = CliRunner(env={"COLUMNS": "240"})

APP = textwrap.dedent(
    """
    from agentic_chaos import chaos_call
    from agentic_chaos.chaos.faults import RateLimitStormError

    def handle():
        for _ in range(8):
            try:
                return chaos_call(lambda: "answer", step_name="llm")
            except RateLimitStormError:
                continue
        raise RuntimeError("gave up")

    def ping():
        return "pong"
    """
)

SUITE = """
name: cli-suite
target: app.py:handle
workflow:
  - step: {name: warm-up, faults: [{type: rate_limit_storm, burst_count: 2}]}
  - health_check: {name: ping, target: "app.py:ping", expect_contains: pong}
  - suspend: {name: gate, reason: next stage is louder}
  - step: {name: blast, faults: [{type: rate_limit_storm, burst_count: 4}]}
schedule: {cron: "0 2 * * *", timezone: Europe/Berlin}
"""


@pytest.fixture
def project(tmp_path):
    (tmp_path / "app.py").write_text(APP)
    (tmp_path / "suite.yaml").write_text(SUITE)
    (tmp_path / "broken.yaml").write_text(
        "name: broken\ntarget: app.py:handle\nfaults: [{type: rate_limt_storm}]\n"
    )
    return tmp_path


def test_validate_ok_and_invalid_files(project):
    ok = runner.invoke(app, ["experiment", "validate", str(project / "suite.yaml")])
    assert ok.exit_code == 0, ok.output
    assert "OK" in ok.output
    bad = runner.invoke(
        app, ["experiment", "validate", str(project / "suite.yaml"), str(project / "broken.yaml")]
    )
    assert bad.exit_code == 1
    assert "INVALID" in bad.output
    assert "did you mean 'rate_limit_storm'" in bad.output


def test_validate_json_strict_and_target_flags(project):
    result = runner.invoke(app, ["experiment", "validate", "--json", str(project / "broken.yaml")])
    data = json.loads(result.output)
    assert data[0]["ok"] is False
    assert data[0]["issues"][0]["location"] == "faults[0].type"

    (project / "warn.yaml").write_text(
        "name: w\ntarget: app.py:handle\nfaults: [rate_limit_storm]\n"
        "templates: {spare: {steps: [{suspend: {name: g}}]}}\n"
    )
    assert runner.invoke(app, ["experiment", "validate", str(project / "warn.yaml")]).exit_code == 0
    strict = runner.invoke(app, ["experiment", "validate", "--strict", str(project / "warn.yaml")])
    assert strict.exit_code == 1

    (project / "missing.yaml").write_text("name: m\ntarget: gone.py\nfaults: [rate_limit_storm]\n")
    path = str(project / "missing.yaml")
    assert runner.invoke(app, ["experiment", "validate", path]).exit_code == 1
    skipped = runner.invoke(app, ["experiment", "validate", "--no-target-check", path])
    assert skipped.exit_code == 0
    other = project / "elsewhere"
    other.mkdir()
    (other / "gone.py").write_text("print('hi')\n")
    based = runner.invoke(app, ["chaos", "workflow", "validate", "--base-dir", str(other), path])
    assert based.exit_code == 0, based.output


def test_run_suspends_resumes_and_saves_reports(project):
    suite = str(project / "suite.yaml")
    workflow_json = project / "workflow.json"
    first = runner.invoke(
        app, ["experiment", "run", suite, "--no-input", "--save", str(workflow_json)]
    )
    assert first.exit_code == EXIT_SUSPENDED, first.output
    assert "suspended" in first.output
    assert WorkflowReport.load(workflow_json).suspended_at == "gate"

    merged = project / "merged.json"
    aios = project / "aios.json"
    resumed = runner.invoke(
        app,
        [
            "chaos",
            "workflow",
            "run",
            suite,
            "--resume-from",
            "gate",
            "--save",
            str(workflow_json),
            "--save-report",
            str(merged),
            "--save-aios",
            str(aios),
        ],
    )
    assert resumed.exit_code == 0, resumed.output
    report = WorkflowReport.load(workflow_json)
    assert report.status == "passed"
    assert report.experiment["schedule"] == {"cron": "0 2 * * *", "timezone": "Europe/Berlin"}
    native = ChaosReport.model_validate_json(merged.read_text())
    assert len(native.chaos_events) == 4
    artifact = json.loads(aios.read_text())
    assert artifact["status"] == "completed"
    assert (
        artifact["extensions"]["io.deepagentlabs.agentic-chaos"]["workflow"]["name"] == "cli-suite"
    )

    approved = runner.invoke(app, ["experiment", "run", suite, "--approve", "gate"])
    assert approved.exit_code == 0
    assert runner.invoke(app, ["experiment", "run", suite, "--approve-all"]).exit_code == 0
    preview = runner.invoke(app, ["experiment", "run", suite, "--dry-run"])
    assert preview.exit_code == 0
    assert "would_suspend" in preview.output


def test_suspended_aios_status_is_running(project):
    aios = project / "aios.json"
    result = runner.invoke(
        app,
        ["experiment", "run", str(project / "suite.yaml"), "--no-input", "--save-aios", str(aios)],
    )
    assert result.exit_code == EXIT_SUSPENDED
    assert json.loads(aios.read_text())["status"] == "running"


def test_interactive_prompt_decides_gates(project, monkeypatch):
    monkeypatch.setattr("agentic_chaos.cli.main._interactive", lambda: True)
    suite = str(project / "suite.yaml")
    approved = runner.invoke(app, ["experiment", "run", suite], input="y\n")
    assert approved.exit_code == 0, approved.output
    assert "Approve gate 'gate' (next stage is louder)?" in approved.output
    rejected = runner.invoke(app, ["experiment", "run", suite], input="n\n")
    assert rejected.exit_code == 1
    assert "rejected" in rejected.output


def test_run_failures_and_invalid_inputs(project):
    (project / "fails.yaml").write_text(
        "name: fails\ntarget: app.py:handle\nfaults: [{type: rate_limit_storm, burst_count: 20}]\n"
    )
    failed = runner.invoke(app, ["experiment", "run", str(project / "fails.yaml")])
    assert failed.exit_code == 1
    assert "gave up" in failed.output
    invalid = runner.invoke(app, ["experiment", "run", str(project / "broken.yaml")])
    assert invalid.exit_code == 1
    assert "INVALID" in invalid.output
    bad_resume = runner.invoke(
        app, ["experiment", "run", str(project / "suite.yaml"), "--resume-from", "nope"]
    )
    assert bad_resume.exit_code == 1
    assert "not a top-level Suspend" in bad_resume.output


def test_schedule_snippets(project):
    suite = str(project / "suite.yaml")
    crontab = runner.invoke(app, ["experiment", "schedule", suite, "--next", "2"])
    assert crontab.exit_code == 0, crontab.output
    lines = crontab.output.splitlines()
    assert lines[0] == "# cli-suite: '0 2 * * *' (Europe/Berlin)"
    assert len([line for line in lines if line.startswith("#   next:")]) == 2
    assert "CRON_TZ=Europe/Berlin" in lines
    assert lines[-1].startswith("0 2 * * * agentic-chaos experiment run")
    actions = runner.invoke(
        app,
        ["experiment", "schedule", suite, "--format", "github-actions", "--command", "make chaos"],
    )
    assert 'cron: "0 2 * * *"' in actions.output
    assert "evaluates this cron in UTC" in actions.output
    assert "- run: make chaos" in actions.output
    bad = runner.invoke(app, ["experiment", "schedule", suite, "--format", "systemd"])
    assert bad.exit_code != 0
    (project / "plain.json").write_text(
        json.dumps({"name": "p", "target": "app.py:handle", "faults": ["rate_limit_storm"]})
    )
    missing = runner.invoke(app, ["experiment", "schedule", str(project / "plain.json")])
    assert missing.exit_code == 1
    assert "no schedule" in missing.output
    broken = runner.invoke(app, ["experiment", "schedule", str(project / "broken.yaml")])
    assert broken.exit_code == 1


GRAPH = textwrap.dedent(
    """
    from agentic_chaos import TopologyTracker, wrap_node, wrap_tool
    from agentic_chaos.agents import ToolCallFailureError

    tracker = TopologyTracker()
    search = wrap_tool(lambda: "docs", tool_name="search", tracker=tracker, caller_node="Hub")
    billing = wrap_tool(lambda: "paid", tool_name="billing", tracker=tracker, caller_node="Hub")

    def hub():
        results = [search()]
        try:
            results.append(billing())
        except ToolCallFailureError as exc:
            raise RuntimeError("billing has no fallback") from exc
        return results

    try:
        wrap_node(hub, node_name="Hub", tracker=tracker)()
    except ToolCallFailureError:
        pass  # search and hub failures are answered with a canned reply
    """
)


def test_agent_fuzz_command(project):
    graph = project / "graph.py"
    graph.write_text(GRAPH)
    saved = project / "fuzz.json"
    result = runner.invoke(
        app,
        [
            "agent",
            "fuzz",
            str(graph),
            "--n",
            "12",
            "--seed",
            "4",
            "--fault",
            "tool_failure",
            "--save",
            str(saved),
        ],  # fmt: skip
    )
    assert result.exit_code == 1, result.output
    assert "Failing nodes" in result.output
    report = FuzzReport.model_validate_json(saved.read_text())
    assert report.failing_nodes == ["billing"]
    safe = runner.invoke(
        app,
        [
            "agent",
            "fuzz",
            str(graph),
            "--n",
            "6",
            "--fault",
            "tool_failure",
            "--exclude-step",
            "billing",
        ],  # fmt: skip
    )
    assert safe.exit_code == 0, safe.output
    assert "Every reached trial recovered" in safe.output
    missing = runner.invoke(app, ["agent", "fuzz", str(project / "nope.py")])
    assert missing.exit_code == 1
    nothing = runner.invoke(app, ["agent", "fuzz", str(graph), "--step", "unknown"])
    assert nothing.exit_code == 1
    assert "no topology node is eligible" in nothing.output
