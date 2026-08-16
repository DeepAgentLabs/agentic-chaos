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
    assert "handoff_corruption" in result.output


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


def test_agent_run_requires_inject_option() -> None:
    result = runner.invoke(app, ["agent", "run", "dummy.py"])
    assert result.exit_code == 2  # missing required --inject


def test_agent_run_missing_script() -> None:
    result = runner.invoke(app, ["agent", "run", "does-not-exist.py", "--inject", "tool_failure"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


_AGENT_WITH_TOPOLOGY_SCRIPT = """
from agentic_chaos import ToolCallFailureFault, TopologyTracker, chaos_call, wrap_tool
from agentic_chaos.agents.faults import ToolCallFailureError


def search(query):
    return f"result for {query}"


tracker = TopologyTracker()
tracker.register_node("Agent", type="agent")
wrapped_search = wrap_tool(search, tool_name="search", tracker=tracker, caller_node="Agent")

try:
    wrapped_search("hello")
except ToolCallFailureError:
    pass
"""


def test_agent_run_includes_topology_in_report(tmp_path: Path) -> None:
    script = tmp_path / "agent_topo.py"
    script.write_text(_AGENT_WITH_TOPOLOGY_SCRIPT)
    out = tmp_path / "report.json"

    result = runner.invoke(
        app, ["agent", "run", str(script), "--inject", "tool_failure", "--save", str(out)]
    )

    assert result.exit_code == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["agent_topology"] is not None
    assert len(data["agent_topology"]["nodes"]) == 2  # Agent + search
    assert len(data["agent_topology"]["edges"]) == 1  # Agent -> search


def test_agent_run_renders_topology_output(tmp_path: Path) -> None:
    script = tmp_path / "agent_topo.py"
    script.write_text(_AGENT_WITH_TOPOLOGY_SCRIPT)

    result = runner.invoke(app, ["agent", "run", str(script), "--inject", "tool_failure"])

    assert result.exit_code == 0
    assert "Agent" in result.output
    assert "search" in result.output
    assert "tool_call" in result.output


_PLAIN_SCRIPT_NO_TOPOLOGY = """
from agentic_chaos.chaos import chaos_call
from agentic_chaos.agents.faults import ToolCallFailureError

def my_fn():
    return "ok"

try:
    chaos_call(my_fn, faults=["tool_failure"], step_name="plain")
except ToolCallFailureError:
    pass
"""

_HANDOFF_SCRIPT = """
from agentic_chaos import TopologyTracker, wrap_node

tracker = TopologyTracker()
tracker.register_node("Planner", type="agent")

def executor(payload):
    return payload

wrapped = wrap_node(executor, node_name="Executor", tracker=tracker, caller_node="Planner")
wrapped("handoff payload")
"""


def test_agent_run_no_topology_leak_across_invocations(tmp_path: Path) -> None:
    """Bug fix: a TopologyTracker from one invocation must NOT leak into
    the next invocation's report."""
    script1 = tmp_path / "with_topo.py"
    script1.write_text(_AGENT_WITH_TOPOLOGY_SCRIPT)
    script2 = tmp_path / "no_topo.py"
    script2.write_text(_PLAIN_SCRIPT_NO_TOPOLOGY)
    out1 = tmp_path / "report1.json"
    out2 = tmp_path / "report2.json"

    # First run — has topology
    runner.invoke(
        app, ["agent", "run", str(script1), "--inject", "tool_failure", "--save", str(out1)]
    )
    # Second run — no topology in this script
    runner.invoke(
        app, ["agent", "run", str(script2), "--inject", "tool_failure", "--save", str(out2)]
    )

    data1 = json.loads(out1.read_text())
    data2 = json.loads(out2.read_text())
    assert data1["agent_topology"] is not None  # first has topology
    assert data2["agent_topology"] is None  # second must NOT have leaked topology


def test_agent_run_saves_handoff_edge_metadata(tmp_path: Path) -> None:
    script = tmp_path / "handoff.py"
    script.write_text(_HANDOFF_SCRIPT)
    out = tmp_path / "handoff_report.json"

    result = runner.invoke(
        app,
        [
            "agent",
            "run",
            str(script),
            "--inject",
            "handoff_corruption",
            "--save",
            str(out),
        ],
    )

    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert data["chaos_events"][0]["fault_type"] == "handoff_corruption"
    assert data["chaos_events"][0]["edge_id"] is not None
    assert data["chaos_events"][0]["from_node"] == "Planner"
    assert data["chaos_events"][0]["to_node"] == "Executor"


def test_drift_snapshot_saves_json(tmp_path: Path) -> None:
    out = tmp_path / "baseline.json"

    result = runner.invoke(
        app,
        [
            "drift",
            "snapshot",
            "--name",
            "support-agent",
            "--save",
            str(out),
            "--prompt-text",
            "You are a careful support agent.",
            "--model",
            "gpt-5-mini",
            "--model-fingerprint",
            "fp-a",
            "--output-text",
            "Refund approved.",
            "--retrieval-item",
            "doc-1",
            "--retrieval-item",
            "doc-2",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert data["name"] == "support-agent"
    assert data["prompt_hash"]
    assert data["retrieval_items"] == ["doc-1", "doc-2"]


def test_drift_compare_detects_drift_and_saves_report(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    out = tmp_path / "drift_report.json"

    baseline_result = runner.invoke(
        app,
        [
            "drift",
            "snapshot",
            "--name",
            "support-agent",
            "--save",
            str(baseline),
            "--prompt-text",
            "You are a careful support agent.",
            "--model",
            "gpt-5-mini",
            "--model-fingerprint",
            "fp-a",
            "--output-text",
            "Refund approved.",
            "--retrieval-item",
            "doc-1",
        ],
    )
    assert baseline_result.exit_code == 0

    result = runner.invoke(
        app,
        [
            "drift",
            "compare",
            str(baseline),
            "--prompt-text",
            "You are a fast support agent.",
            "--model",
            "gpt-5-mini",
            "--model-fingerprint",
            "fp-b",
            "--output-text",
            "Please contact support.",
            "--retrieval-item",
            "doc-9",
            "--save",
            str(out),
        ],
    )

    assert result.exit_code == 2
    assert "drift detected: yes" in result.output.lower()
    data = json.loads(out.read_text())
    assert data["has_drift"] is True
    assert any(finding["kind"] == "model" for finding in data["findings"])


def test_drift_compare_suppresses_repeated_unchanged_report(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    report = tmp_path / "drift_report.json"
    state = tmp_path / "state.json"

    baseline_result = runner.invoke(
        app,
        [
            "drift",
            "snapshot",
            "--name",
            "retriever",
            "--save",
            str(baseline),
            "--prompt-text",
            "baseline",
        ],
    )
    assert baseline_result.exit_code == 0

    first = runner.invoke(
        app,
        [
            "drift",
            "compare",
            str(baseline),
            "--prompt-text",
            "current",
            "--save",
            str(report),
            "--state-path",
            str(state),
        ],
    )
    second = runner.invoke(
        app,
        [
            "drift",
            "compare",
            str(baseline),
            "--prompt-text",
            "current",
            "--save",
            str(report),
            "--state-path",
            str(state),
        ],
    )

    assert first.exit_code == 2
    assert second.exit_code == 2
    assert "suppressed unchanged drift report" in second.output.lower()
