import json

import pytest
from typer.testing import CliRunner

from agentic_chaos import load_profile
from agentic_chaos.cli.main import app


def test_profile_fresh_state_and_parameters(tmp_path):
    path = tmp_path / "chaos.toml"
    path.write_text(
        '[profiles.test]\nfaults = ["rate_limit_storm"]\nprobability = 0.25\nseed = 5\n'
        "[profiles.test.parameters.rate_limit_storm]\nburst_count = 2\n"
    )
    first = load_profile("test", path)[0]
    second = load_profile("test", path)[0]
    assert first is not second
    assert first.probability == 0.25
    assert first.burst_count == 2


@pytest.mark.parametrize(
    "config",
    [
        "faults = []",
        'faults = ["missing"]',
        'faults = ["auth_error", "auth_error"]',
        'faults = ["auth_error"]\nprobability = 2',
        'faults = ["auth_error"]\nseed = "bad"',
        'faults = ["auth_error"]\nunknown = 1',
    ],
)
def test_invalid_profiles(tmp_path, config):
    path = tmp_path / "chaos.toml"
    path.write_text("[profiles.test]\n" + config)
    with pytest.raises(ValueError):
        load_profile("test", path)


@pytest.mark.parametrize("command", ["chaos", "agent"])
def test_cli_profile_and_exclusive_flags(tmp_path, command):
    script = tmp_path / "app.py"
    script.write_text(
        'from agentic_chaos import chaos_call\nassert chaos_call(lambda: "ok") == "ok"\n'
    )
    config = tmp_path / "chaos.toml"
    config.write_text('[profiles.test]\nfaults = ["auth_error"]\nprobability = 0\n')
    report = tmp_path / "report.json"
    runner = CliRunner()
    args = [
        command,
        "run",
        str(script),
        "--profile",
        "test",
        "--profile-file",
        str(config),
        "--save",
        str(report),
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert json.loads(report.read_text())["chaos_events"] == []
    assert runner.invoke(app, args + ["--inject", "auth_error"]).exit_code == 1
    assert runner.invoke(app, [command, "run", str(script)]).exit_code == 1
