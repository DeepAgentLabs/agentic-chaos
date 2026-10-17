"""Keep the v0.6 examples runnable and their documented output true."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_contracts_demo_output() -> None:
    output = subprocess.check_output(
        [sys.executable, "examples/chaos_contracts_demo.py"], cwd=ROOT, text=True
    )
    assert "5/5 chaos contracts passed for 'resilient'" in output
    assert "3/5 chaos contracts passed for 'fragile'" in output
    assert "expected nodes never visited under chaos: Reviewer" in output


@pytest.mark.parametrize(
    ("args", "summary"),
    [((), "5 passed"), (("--chaos",), "4 passed, 1 xfailed")],
)
def test_pytest_example_suite(args: tuple[str, ...], summary: str) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "examples/pytest_chaos",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            *args,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert summary in result.stdout


def test_github_actions_example_uses_plugin_and_contracts() -> None:
    text = (ROOT / "examples/github-actions-chaos.yml").read_text()
    assert "pytest --chaos" in text
    assert "--contract no_unhandled_error" in text
