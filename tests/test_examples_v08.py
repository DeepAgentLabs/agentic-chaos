"""Keep the v0.8 examples runnable and their documented output true."""

import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentic_chaos.cli.main import app
from agentic_chaos.experiments import load_experiment, validate_experiment

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "examples" / "workflows"
runner = CliRunner(env={"COLUMNS": "240"})


def test_workflow_demo_output() -> None:
    output = subprocess.check_output(
        [sys.executable, "examples/chaos_workflow_demo.py"], cwd=ROOT, text=True
    )
    assert "workflow passed: 12 chaos events" in output
    assert "status=suspended suspended_at=approve-escalation" in output
    assert "resumed status=passed" in output
    assert "faults[0].type: unknown fault 'rate_limt_storm'; did you mean" in output
    assert "schedule.cron: hour value 25 is outside 0-23" in output
    assert "failing nodes: planner" in output


@pytest.mark.parametrize("name", ["rate-limit-recovery.yaml", "resilience-suite.yaml"])
def test_yaml_examples_validate(name: str) -> None:
    result = validate_experiment(WORKFLOWS / name)
    assert result.ok and not result.warnings, result.issues
    assert result.experiment.schedule is not None


def test_rate_limit_experiment_runs() -> None:
    report = load_experiment(WORKFLOWS / "rate-limit-recovery.yaml").run()
    assert report.status == "passed"
    assert report.nodes[0].contracts["passed"] is True
    assert len(report.chaos_events) == 3


def test_resilience_suite_gates_and_scopes() -> None:
    experiment = load_experiment(WORKFLOWS / "resilience-suite.yaml")
    paused = experiment.run()
    assert paused.status == "suspended"
    report = experiment.run(approve=["approve-escalation"])
    assert report.status == "passed", [(n.name, n.message) for n in report.walk()]
    assert len(report.chaos_events) == 12
    # Explosion radius: the guard is never the target of an injected fault.
    assert "safety_check" not in {event["step_name"] for event in report.chaos_events}


def test_cli_runs_the_suite_with_approval(tmp_path: Path) -> None:
    suite = str(WORKFLOWS / "resilience-suite.yaml")
    assert runner.invoke(app, ["chaos", "workflow", "validate", suite]).exit_code == 0
    result = runner.invoke(
        app,
        [
            "chaos",
            "workflow",
            "run",
            suite,
            "--approve",
            "approve-escalation",
            "--save",
            str(tmp_path / "suite.json"),
        ],  # fmt: skip
    )
    assert result.exit_code == 0, result.output
    schedule = runner.invoke(app, ["experiment", "schedule", suite, "--next", "1"])
    assert "30 3 * * 1-5 agentic-chaos experiment run" in schedule.output
