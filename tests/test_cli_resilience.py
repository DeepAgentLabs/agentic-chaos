"""v0.9 CLI: --probe, --min-score and --history on run commands; the score group."""

import json
import textwrap

import pytest
from typer.testing import CliRunner

from agentic_chaos.cli.main import app
from agentic_chaos.cli.render import bar
from agentic_chaos.models import ChaosReport
from agentic_chaos.resilience import ResilienceHistory
from agentic_chaos.workflows import WorkflowReport

runner = CliRunner(env={"COLUMNS": "200"})

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

    def down():
        raise ConnectionError("offline")

    if __name__ == "__main__":
        handle()
    """
)
FRAGILE = textwrap.dedent(
    """
    from agentic_chaos import chaos_call
    chaos_call(lambda: "answer", step_name="llm")
    """
)


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text(APP)
    (tmp_path / "fragile.py").write_text(FRAGILE)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run(*args: str):
    return runner.invoke(app, list(args))


def test_bar() -> None:
    assert bar(1.0) == "█" * 12
    assert bar(0.5, width=4) == "██░░"
    assert bar(None, width=3) == "···"
    assert bar(7.0, width=2) == "██"


def test_chaos_run_scores_and_gates(project) -> None:
    result = run(
        "chaos", "run", "app.py", "--inject", "rate_limit_storm",
        "--probe", "app.py:ping", "--min-score", "90", "--save", "r.json",
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "Resilience Report: app" in result.output
    assert "Overall Score: 100/100 (A)" in result.output
    assert "Resilience score 100 meets --min-score 90" in result.output
    saved = ChaosReport.model_validate_json((project / "r.json").read_text())
    assert saved.resilience_score == 100
    assert [p["phase"] for p in saved.probes] == ["pre", "post"]


def test_chaos_run_fails_below_min_score(project) -> None:
    result = run(
        "chaos", "run", "app.py", "--inject", "rate_limit_storm",
        "--probe", "app.py:ping", "--min-score", "90", "--weight-free",
    )  # fmt: skip
    assert result.exit_code != 0  # unknown option guards against silent typos
    low = run(
        "chaos", "run", "fragile.py", "--inject", "rate_limit_storm", "--min-score", "50",
    )  # fmt: skip
    assert low.exit_code == 1
    assert "1 escaped" in low.output


def test_min_score_gate_runs_after_a_clean_run(project) -> None:
    # A probe that degrades only after chaos: run is clean, the score is not.
    (project / "probe_state.py").write_text(
        textwrap.dedent(
            """
            calls = {"n": 0}

            def settles():
                calls["n"] += 1
                if calls["n"] > 1:
                    raise RuntimeError("not recovered")
                return "ok"
            """
        )
    )
    result = run(
        "chaos", "run", "app.py", "--inject", "rate_limit_storm",
        "--probe", "probe_state.py:settles", "--min-score", "95",
    )  # fmt: skip
    assert result.exit_code == 1
    assert "is below --min-score 95" in result.output


def test_failed_pre_probe_exits_before_chaos_and_saves_why(project) -> None:
    result = run(
        "agent", "run", "app.py", "--inject", "rate_limit_storm",
        "--probe", "app.py:down", "--save", "r.json", "--save-aios", "aios.json",
    )  # fmt: skip
    assert result.exit_code == 1
    assert "no fault was injected" in result.output
    saved = ChaosReport.model_validate_json((project / "r.json").read_text())
    assert saved.chaos_events == [] and saved.resilience["status"] == "inconclusive"
    assert json.loads((project / "aios.json").read_text())["status"] == "failed"


def test_run_history_records_trend_and_retention(project) -> None:
    args = [
        "chaos", "run", "app.py", "--inject", "rate_limit_storm",
        "--history", "h.json", "--history-max-runs", "2",
    ]  # fmt: skip
    first = run(*args)
    assert first.exit_code == 0 and "Trend: first recorded run" in first.output
    second = run(*args)
    assert "Trend: → +0 from last run (was 100)" in second.output
    run(*args)
    assert len(ResilienceHistory(project / "h.json").entries("app")) == 2


@pytest.mark.parametrize(
    "extra, message",
    [
        (["--min-score", "120"], "--min-score must be between 0 and 100"),
        (["--history-max-runs", "3"], "need --history"),
        (["--probe", "ftp://nope"], "must use http:// or https://"),
        (["--probe", "missing_module:fn"], "No module named"),
    ],
)
def test_run_option_errors(project, extra, message) -> None:
    result = run("chaos", "run", "app.py", "--inject", "rate_limit_storm", *extra)
    assert result.exit_code == 1
    assert message in result.output


def test_http_probe_from_the_cli(project) -> None:
    result = run(
        "chaos", "run", "app.py", "--inject", "rate_limit_storm",
        "--probe", "http://127.0.0.1:9/health",
    )  # fmt: skip
    assert result.exit_code == 1
    assert "request failed" in result.output


# -- score group ------------------------------------------------------------------


def saved_report(project) -> str:
    assert run("chaos", "run", "app.py", "--inject", "rate_limit_storm", "--save", "r.json")
    return "r.json"


def test_score_show_recomputes_offline(project) -> None:
    path = saved_report(project)
    result = run("score", "show", path, "--min-score", "90", "--save", "score.json")
    assert result.exit_code == 0, result.output
    assert "Overall Score: 100/100" in result.output
    assert json.loads((project / "score.json").read_text())["score"] == 100


def test_score_show_json_weights_and_history(project) -> None:
    path = saved_report(project)
    result = run(
        "score", "show", path, "--json", "--weight", "recovery=0", "--weight", "retry_efficiency=1",
        "--history", "h.json", "--baseline", path,
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["components"][0]["weight"] == 0.0 and data["baseline_report_id"]
    assert ResilienceHistory(project / "h.json").latest("app")["score"] == data["score"]


@pytest.mark.parametrize(
    "extra, message",
    [
        (["--weight", "recovery"], "must look like 'name=value'"),
        (["--weight", "speed=1"], "unknown resilience component"),
        (["--min-score", "-1"], "between 0 and 100"),
    ],
)
def test_score_show_errors(project, extra, message) -> None:
    result = run("score", "show", saved_report(project), *extra)
    assert result.exit_code == 1 and message in result.output


def test_score_show_gates_inconclusive_scores(project) -> None:
    result = run(
        "chaos", "run", "app.py", "--inject", "rate_limit_storm", "--dry-run", "--save", "d.json"
    )
    assert result.exit_code == 0
    gated = run("score", "show", "d.json", "--min-score", "1")
    assert gated.exit_code == 1 and "inconclusive is below --min-score 1" in gated.output


def test_score_show_reads_workflow_reports(project) -> None:
    (project / "exp.json").write_text(
        json.dumps(
            {
                "name": "exp",
                "target": "app.py:handle",
                "faults": [{"type": "rate_limit_storm", "burst_count": 2}],
            }
        )
    )
    assert run("experiment", "run", "exp.json", "--save", "wf.json").exit_code == 0
    assert WorkflowReport.load(project / "wf.json").resilience_score == 100
    result = run("score", "show", "wf.json")
    assert result.exit_code == 0 and "Resilience Report: exp" in result.output


def test_score_history_and_prune(project) -> None:
    for _ in range(3):
        run("chaos", "run", "app.py", "--inject", "rate_limit_storm", "--history", "h.json")
    listed = run("score", "history", "--history", "h.json")
    assert listed.exit_code == 0 and "+0" in listed.output
    as_json = json.loads(
        run("score", "history", "--history", "h.json", "--json", "--name", "app").stdout
    )
    assert len(as_json) == 3
    pruned = run("score", "prune", "--history", "h.json", "--max-runs", "1")
    assert "Removed 2 entries" in pruned.output
    assert (
        "Removed 0 entries"
        in run("score", "prune", "--history", "h.json", "--max-age-days", "30").output
    )
    assert run("score", "prune", "--history", "h.json").exit_code == 1
    assert "No resilience history" in run("score", "history", "--history", "none.json").output
    (project / "bad.json").write_text("{")
    assert run("score", "history", "--history", "bad.json").exit_code == 1


# -- experiment run ---------------------------------------------------------------


def experiment(project, **extra) -> str:
    data = {
        "name": "exp",
        "target": "app.py:handle",
        "faults": [{"type": "rate_limit_storm", "burst_count": 2}],
        "probes": [{"type": "function", "target": "app.py:ping"}],
        **extra,
    }
    (project / "exp.json").write_text(json.dumps(data))
    return "exp.json"


def test_experiment_run_renders_probes_and_score(project) -> None:
    result = run(
        "experiment", "run", experiment(project), "--min-score", "80", "--history", "h.json"
    )
    assert result.exit_code == 0, result.output
    assert "Resilience Probes" in result.output and "Overall Score: 100/100" in result.output
    assert ResilienceHistory(project / "h.json").latest("exp")["score"] == 100


def test_experiment_min_score_from_the_file_and_override(project) -> None:
    path = experiment(
        project,
        probes=[{"type": "function", "target": "app.py:down", "phases": ["post"]}],
        resilience={"min_score": 95},
    )
    failed = run("experiment", "run", path)
    assert failed.exit_code == 1 and "below --min-score 95" in failed.output
    assert run("experiment", "run", path, "--min-score", "10").exit_code == 0


def test_experiment_run_option_errors(project) -> None:
    path = experiment(project)
    assert run("chaos", "workflow", "run", path, "--min-score", "500").exit_code == 1
    missing = run("experiment", "run", path, "--baseline", "nope.json")
    assert missing.exit_code == 1


def test_module_entry_point_includes_the_score_group(project) -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "agentic_chaos.cli.main", "score", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "show" in result.stdout and "prune" in result.stdout
