"""Workflow target specs: scripts, file functions and module functions."""

import pytest

from agentic_chaos.workflows import ScriptExitError, check_target, resolve_target


def test_script_targets_run_as_main_and_report_exit_codes(tmp_path):
    (tmp_path / "ok.py").write_text("import sys\nif __name__ == '__main__':\n    sys.exit(0)\n")
    (tmp_path / "bad.py").write_text("import sys\nsys.exit(3)\n")
    assert resolve_target("ok.py", tmp_path)() is None
    with pytest.raises(ScriptExitError) as exc:
        resolve_target("bad.py", tmp_path)()
    assert exc.value.code == 3
    assert resolve_target(str(tmp_path / "ok.py")).__name__ == "ok"


def test_file_function_targets_share_one_module(tmp_path):
    (tmp_path / "app.py").write_text(
        "STATE = []\ndef add(x):\n    STATE.append(x)\n    return STATE\n"
    )
    add = resolve_target("app.py:add", tmp_path)
    assert add(1) == [1]
    assert resolve_target("app.py:add", tmp_path)(2) == [1, 2]
    with pytest.raises(ValueError, match="not a callable"):
        resolve_target("app.py:STATE", tmp_path)
    with pytest.raises(ValueError, match="not found"):
        resolve_target("missing.py:add", tmp_path)


def test_failed_module_import_is_not_cached(tmp_path):
    (tmp_path / "boom.py").write_text("raise RuntimeError('import failed')\ndef f():\n    pass\n")
    for _ in range(2):
        with pytest.raises(RuntimeError, match="import failed"):
            resolve_target("boom.py:f", tmp_path)


def test_module_targets():
    import json

    assert resolve_target("json:dumps") is json.dumps
    with pytest.raises(ValueError, match="need a function"):
        resolve_target("json")
    with pytest.raises(ValueError, match="identifier"):
        resolve_target("json:not-valid")
    with pytest.raises(ValueError, match="non-empty"):
        resolve_target("  ")


def test_check_target_parses_without_importing(tmp_path):
    (tmp_path / "app.py").write_text(
        "import os as runner\nfrom json import dumps\nVALUE: int = 1\nalias = print\n"
        "class Agent:\n    pass\nasync def handle():\n    pass\n"
        "raise SystemExit('must not run')\n"
    )
    for name in ("runner", "dumps", "VALUE", "alias", "Agent", "handle"):
        assert check_target(f"app.py:{name}", tmp_path) is None
    assert "not defined" in check_target("app.py:other", tmp_path)
    assert check_target("app.py", tmp_path) is None
    assert "not found" in check_target("nope.py", tmp_path)
    assert "identifier" in check_target("app.py:1x", tmp_path)
    assert check_target("json:dumps") is None
    assert "not importable" in check_target("definitely_missing_mod:run")
    assert "cannot be located" in check_target("json.missing.deeper:run")
    assert check_target("math:sqrt") is None  # extension module: nothing to parse


def test_windows_style_paths_are_scripts():
    assert "not found" in check_target("C:\\apps\\missing.py")


def test_file_targets_can_import_sibling_modules(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "helpers_sibling_mod.py").write_text("def answer():\n    return 42\n")
    (project / "agent.py").write_text(
        "from helpers_sibling_mod import answer\n"
        "def handle():\n    return answer()\n"
        "if __name__ == '__main__':\n    assert answer() == 42\n"
    )
    assert resolve_target("agent.py:handle", project)() == 42
    resolve_target("agent.py", project)()
