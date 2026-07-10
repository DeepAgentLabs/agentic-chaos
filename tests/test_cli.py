import json
from pathlib import Path

from typer.testing import CliRunner

from agentic_chaos.cli.main import app

runner = CliRunner()

_CHAOS_SCRIPT = """
from agenticlens import profile, step
from agentic_chaos.chaos import chaos_call, TokenTimeoutError


class Usage:
    prompt_tokens = 100
    completion_tokens = 50


class Response:
    usage = Usage()


def call_llm():
    return Response()


with profile("Chaos CLI Demo"):
    with step("Planner", type="planner", provider="openai", model="gpt-4o-mini") as s:
        try:
            response = chaos_call(call_llm, step=s, faults=["token_timeout"])
            s.record(response)
        except TokenTimeoutError:
            pass
"""

_NO_CHAOS_SCRIPT = """
print("no agenticlens workflow here")
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


def test_chaos_run_script_without_profile_call_errors(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text(_NO_CHAOS_SCRIPT)

    result = runner.invoke(app, ["chaos", "run", str(script), "--inject", "token_timeout"])

    assert result.exit_code == 1
    assert "no workflow was profiled" in result.output.lower()


def test_chaos_run_injects_fault_and_reports_events(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text(_CHAOS_SCRIPT)

    result = runner.invoke(app, ["chaos", "run", str(script), "--inject", "token_timeout"])

    assert result.exit_code == 0
    assert "token_timeout" in result.output
    assert "errored" in result.output


def test_chaos_run_saves_workflow_with_chaos_events(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text(_CHAOS_SCRIPT)
    out = tmp_path / "chaos_run.json"

    result = runner.invoke(
        app, ["chaos", "run", str(script), "--inject", "token_timeout", "--save", str(out)]
    )

    assert result.exit_code == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["name"] == "Chaos CLI Demo"
    assert len(data["chaos_events"]) == 1
    assert data["chaos_events"][0]["fault_type"] == "token_timeout"
    assert data["chaos_events"][0]["step_name"] == "Planner"


def test_agent_run_not_implemented() -> None:
    result = runner.invoke(app, ["agent", "run"])
    assert result.exit_code == 1
    assert "v0.2" in result.output


def test_drift_snapshot_not_implemented() -> None:
    result = runner.invoke(app, ["drift", "snapshot"])
    assert result.exit_code == 1
    assert "v0.3" in result.output
