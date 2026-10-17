import json
from pathlib import Path

from typer.testing import CliRunner

from agentic_chaos.cli.main import app

runner = CliRunner()

RETRYING_SCRIPT = """
from agentic_chaos import chaos_call
from agentic_chaos.chaos.faults import RateLimitStormError

for _ in range(5):
    try:
        chaos_call(lambda: "ok", step_name="llm")
        break
    except RateLimitStormError:
        pass
"""

CRASHING_SCRIPT = """
from agentic_chaos import chaos_call

chaos_call(lambda: "ok", step_name="llm")
"""


def write(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "app.py"
    script.write_text(body)
    return script


def test_chaos_run_contracts_pass_and_are_saved(tmp_path: Path) -> None:
    script = write(tmp_path, RETRYING_SCRIPT)
    out = tmp_path / "contracts.json"
    result = runner.invoke(
        app,
        [
            "chaos",
            "run",
            str(script),
            "--inject",
            "rate_limit_storm",
            "--contract",
            "max_retries:3",
            "--contract",
            "recovered_after_failure:require_step_success=true",
            "--save-contracts",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Chaos Contracts" in result.output
    assert "2/2 contracts passed" in result.output
    data = json.loads(out.read_text())
    assert data["passed"] is True
    assert [r["contract"] for r in data["results"]] == ["max_retries", "recovered_after_failure"]


def test_chaos_run_exits_1_on_contract_failure(tmp_path: Path) -> None:
    script = write(tmp_path, RETRYING_SCRIPT)
    result = runner.invoke(
        app,
        [
            "chaos",
            "run",
            str(script),
            "--inject",
            "rate_limit_storm",
            "--contract",
            "max_retries:1",
        ],
    )
    assert result.exit_code == 1
    assert "0/1 contracts passed" in result.output


def test_unhandled_fault_fails_no_unhandled_error(tmp_path: Path) -> None:
    script = write(tmp_path, CRASHING_SCRIPT)
    result = runner.invoke(
        app,
        ["chaos", "run", str(script), "--inject", "rate_limit_storm"]
        + ["--contract", "no_unhandled_error"],
    )
    assert result.exit_code == 1
    assert "no_unhandled_error" in result.output
    assert "RateLimitStormError" in result.output


def test_script_exit_code_wins_over_contract_failure(tmp_path: Path) -> None:
    script = write(tmp_path, RETRYING_SCRIPT + "\nimport sys\nsys.exit(3)\n")
    result = runner.invoke(
        app,
        ["chaos", "run", str(script), "--inject", "rate_limit_storm"]
        + ["--contract", "max_retries:0"],
    )
    assert result.exit_code == 3
    assert "0/1 contracts passed" in result.output


def test_contracts_check_against_saved_reports(tmp_path: Path) -> None:
    script = write(tmp_path, RETRYING_SCRIPT)
    chaos_report = tmp_path / "chaos.json"
    baseline_report = tmp_path / "baseline.json"
    common = ["chaos", "run", str(script), "--inject", "rate_limit_storm"]
    assert runner.invoke(app, [*common, "--dry-run", "--save", str(baseline_report)]).exit_code == 0
    assert runner.invoke(app, [*common, "--save", str(chaos_report)]).exit_code == 0

    ok = runner.invoke(
        app,
        [
            "contracts",
            "check",
            str(chaos_report),
            "--baseline",
            str(baseline_report),
            "--contract",
            "max_cost_impact:4,metric=calls",
            "--contract",
            "full_topology_traversal",
        ],
    )
    assert ok.exit_code == 0, ok.output

    saved = tmp_path / "results.json"
    bad = runner.invoke(
        app,
        [
            "contracts",
            "check",
            str(chaos_report),
            "--baseline",
            str(baseline_report),
            "--contract",
            "max_cost_impact:2,metric=calls",
            "--save",
            str(saved),
        ],
    )
    assert bad.exit_code == 1
    assert json.loads(saved.read_text())["results"][0]["observed"]["ratio"] == 4.0


def test_agent_run_accepts_contracts(tmp_path: Path) -> None:
    script = write(
        tmp_path,
        """
from agentic_chaos import TopologyTracker, wrap_tool

tracker = TopologyTracker()
search = wrap_tool(lambda q: q, tool_name="search", tracker=tracker, caller_node="Agent")
try:
    search("q")
except Exception:
    pass
""",
    )
    result = runner.invoke(
        app,
        [
            "agent",
            "run",
            str(script),
            "--inject",
            "tool_failure",
            "--contract",
            "full_topology_traversal:expected_nodes=Agent|search|Reviewer",
        ],
    )
    assert result.exit_code == 1
    assert "full_topology_traversal" in result.output
    assert "Reviewer" in result.output


def test_invalid_contract_or_baseline_fail_before_running(tmp_path: Path) -> None:
    script = write(tmp_path, "raise SystemExit('script must not run')\n")
    bad_spec = runner.invoke(
        app, ["chaos", "run", str(script), "--inject", "rate_limit_storm", "--contract", "nope"]
    )
    assert bad_spec.exit_code == 1
    assert "Unknown contract 'nope'" in bad_spec.output

    broken = tmp_path / "broken.json"
    broken.write_text("{}")
    bad_baseline = runner.invoke(
        app,
        ["chaos", "run", str(script), "--inject", "rate_limit_storm", "--baseline", str(broken)],
    )
    assert bad_baseline.exit_code == 1
    assert "script must not run" not in bad_baseline.output


def test_contracts_check_errors(tmp_path: Path) -> None:
    missing = runner.invoke(
        app, ["contracts", "check", str(tmp_path / "x.json"), "--contract", "no_unhandled_error"]
    )
    assert missing.exit_code == 1
    not_json = tmp_path / "bad.json"
    not_json.write_text("not json")
    assert (
        runner.invoke(
            app, ["contracts", "check", str(not_json), "--contract", "no_unhandled_error"]
        ).exit_code
        == 1
    )


def test_contracts_list() -> None:
    result = runner.invoke(app, ["contracts", "list"])
    assert result.exit_code == 0
    for name in ("completes_within", "no_retry_storm", "full_topology_traversal"):
        assert name in result.output


def test_module_entry_point_registers_contract_commands() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "agentic_chaos.cli.main", "contracts", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "max_retries" in result.stdout
