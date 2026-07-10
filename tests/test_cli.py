import json
from pathlib import Path

from typer.testing import CliRunner

from agentic_chaos.cli.main import app

runner = CliRunner()

_CAUGHT_FAULT_SCRIPT = """
from agentic_chaos.chaos import chaos_call, TokenTimeoutError


def call_llm():
    return "real answer"


try:
    chaos_call(call_llm, step_id="s1", step_name="Planner", faults=["token_timeout"])
except TokenTimeoutError:
    pass
"""

_UNCAUGHT_FAULT_SCRIPT = """
from agentic_chaos.chaos import chaos_call


def call_llm():
    return "real answer"


chaos_call(call_llm, step_id="s1", step_name="Planner", faults=["token_timeout"])
"""

_NO_CHAOS_CALL_SCRIPT = """
print("plain script, no chaos_call() anywhere")
"""


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "agentic-chaos" in result.output.lower() or "Usage" in result.output


def test_chaos_list_faults() -> None:
    result = runner.invoke(app, ["chaos", "list-faults"])
    assert result.exit_code == 0
    assert "token_timeout" in result.output
    assert "rate_limit_storm" in result.output
    assert "silent_degradation" in result.output


def test_chaos_run_unknown_fault_name(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text("print('hello')")

    result = runner.invoke(app, ["chaos", "run", str(script), "--inject", "not_a_fault"])

    assert result.exit_code == 1
    assert "unknown fault" in result.output.lower()


def test_chaos_run_missing_script() -> None:
    result = runner.invoke(app, ["chaos", "run", "does-not-exist.py", "--inject", "token_timeout"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_chaos_run_script_with_no_chaos_call_reports_no_events(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text(_NO_CHAOS_CALL_SCRIPT)

    result = runner.invoke(app, ["chaos", "run", str(script), "--inject", "token_timeout"])

    assert result.exit_code == 0
    assert "no faults triggered" in result.output.lower()


def test_chaos_run_injects_fault_and_reports_events(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text(_CAUGHT_FAULT_SCRIPT)

    result = runner.invoke(app, ["chaos", "run", str(script), "--inject", "token_timeout"])

    assert result.exit_code == 0
    assert "token_timeout" in result.output
    assert "errored" in result.output


def test_chaos_run_uncaught_fault_exits_nonzero_but_still_reports(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text(_UNCAUGHT_FAULT_SCRIPT)

    result = runner.invoke(app, ["chaos", "run", str(script), "--inject", "token_timeout"])

    assert result.exit_code == 1
    assert "raised under chaos" in result.output.lower()
    assert "token_timeout" in result.output  # events are still reported despite the crash


def test_chaos_run_saves_standalone_chaos_report(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text(_CAUGHT_FAULT_SCRIPT)
    out = tmp_path / "chaos_run.json"

    result = runner.invoke(
        app, ["chaos", "run", str(script), "--inject", "token_timeout", "--save", str(out)]
    )

    assert result.exit_code == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["name"] == "app"
    assert len(data["chaos_events"]) == 1
    assert data["chaos_events"][0]["fault_type"] == "token_timeout"
    assert data["chaos_events"][0]["step_name"] == "Planner"
    # No agenticlens involved -- there's no `steps` field on this package's own report.
    assert "steps" not in data


def test_chaos_run_saves_report_even_when_script_crashes(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text(_UNCAUGHT_FAULT_SCRIPT)
    out = tmp_path / "chaos_run.json"

    result = runner.invoke(
        app, ["chaos", "run", str(script), "--inject", "token_timeout", "--save", str(out)]
    )

    assert result.exit_code == 1
    assert out.exists()
    data = json.loads(out.read_text())
    assert len(data["chaos_events"]) == 1


def test_agent_run_not_implemented() -> None:
    result = runner.invoke(app, ["agent", "run"])
    assert result.exit_code == 1
    assert "v0.2" in result.output


def test_drift_snapshot_not_implemented() -> None:
    result = runner.invoke(app, ["drift", "snapshot"])
    assert result.exit_code == 1
    assert "v0.3" in result.output
