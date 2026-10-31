"""Keep the v0.9 examples runnable and their documented output true."""

import subprocess
import sys
from pathlib import Path

import yaml
from typer.testing import CliRunner

from agentic_chaos.cli.main import app
from agentic_chaos.experiments import load_experiment, validate_experiment
from agentic_chaos.resilience import ResilienceHistory

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "examples" / "workflows"
runner = CliRunner(env={"COLUMNS": "240"})


def test_resilience_demo_output() -> None:
    output = subprocess.check_output(
        [sys.executable, "examples/chaos_resilience_demo.py"], cwd=ROOT, text=True
    )
    assert "unscoped storm: score=72 grade=C" in output
    assert "escaped fault: rate_limit_storm" in output
    assert "scoped storm: score=100 grade=A" in output
    assert "silent degradation: score=86 grade=B" in output
    assert "2 unverified (attach a fidelity judge)" in output
    assert "trend: -14 from last run (was 100)" in output
    assert "history runs kept: 3" in output
    assert "Resilience Report: support-agent" in output
    assert "x the baseline duration" in output


def test_probed_experiment_validates_and_runs(tmp_path) -> None:
    result = validate_experiment(WORKFLOWS / "resilience-probes.yaml")
    assert result.ok and not result.warnings, result.issues
    experiment = load_experiment(WORKFLOWS / "resilience-probes.yaml")
    assert experiment.min_score == 80
    assert experiment.history is not None and experiment.history.max_runs == 30
    history = ResilienceHistory(tmp_path / "h.json")
    report = experiment.run(history=history)
    assert report.status == "passed" and report.resilience_score == 100
    assert [p["probe"] for p in report.probes if p["phase"] == "during"] == ["answers"]
    assert history.latest("resilience-probes")["score"] == 100


def test_probed_experiment_cli_gate(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = str(WORKFLOWS / "resilience-probes.yaml")
    first = runner.invoke(app, ["experiment", "run", path, "--no-input"])
    assert first.exit_code == 0, first.output
    assert "Resilience score 100 meets --min-score 80" in first.output
    assert "Trend: first recorded run" in first.output
    assert (tmp_path / ".agentic-chaos" / "resilience-history.json").exists()
    second = runner.invoke(app, ["experiment", "run", path, "--no-input"])
    assert "Trend: → +0 from last run (was 100)" in second.output


def test_resilience_ci_example_is_valid_yaml() -> None:
    workflow = yaml.safe_load((ROOT / "examples" / "github-actions-resilience.yml").read_text())
    steps = workflow["jobs"]["resilience"]["steps"]
    commands = " ".join(step.get("run", "") for step in steps)
    assert "--min-score 80" in commands and "--history-max-runs 30" in commands
    assert "agentic-chaos score history" in commands
