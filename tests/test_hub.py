"""Registry boundaries: offline, no execution, identity and plugin collisions."""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from typer.testing import CliRunner

from agentic_chaos.cli.main import app
from agentic_chaos.experiments import validate_experiment
from agentic_chaos.hub import list_recipes, pull, push, recipe
from agentic_chaos.hub.plugins import installed_plugins, load_plugins


def test_bundled_recipes_validate_without_target_imports(tmp_path: Path) -> None:
    assert len(list_recipes()) >= 6
    assert len(list_recipes("rag")) == 2
    for row in list_recipes():
        data = recipe(row["name"])
        assert validate_experiment(data, check_targets=False).ok
        target = pull(row["name"], tmp_path / (row["name"] + ".json"))
        assert json.loads(target.read_text()) == data
        with pytest.raises(FileExistsError):
            pull(row["name"], target)
    assert list_recipes("absent") == []


@pytest.mark.parametrize("name", ["../escape", "/absolute", "UPPER", "x/y", "a..b", ""])
def test_reject_paths(name: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        pull(name, tmp_path / "recipe.json")


def test_contribution_validation_and_no_overwrite(tmp_path: Path) -> None:
    source = pull("react-loop-resilience", tmp_path / "source.json")
    destination = push(source, tmp_path / "registry")
    assert destination.name == "react-loop-resilience.json"
    with pytest.raises(FileExistsError):
        push(source, tmp_path / "registry")
    source.write_text('{"name":"broken", "faults":[{"type":"not-a-fault"}]}')
    with pytest.raises(ValueError):
        push(source, tmp_path / "registry")


def test_remote_requires_pinned_commit_and_checks_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import agentic_chaos.hub as hub

    network = MagicMock()
    monkeypatch.setattr(hub, "urlopen", network)
    for repo, ref in [("bad", "a" * 40), ("owner/repo", "main"), ("owner/repo", None)]:
        with pytest.raises(ValueError):
            pull("react-loop-resilience", tmp_path / "out.json", repository=repo, ref=ref)
    network.assert_not_called()
    response = network.return_value.__enter__.return_value
    response.read.return_value = json.dumps(recipe("rag-context-poisoning")).encode()
    with pytest.raises(ValueError, match="identity"):
        pull("react-loop-resilience", tmp_path / "out.json", repository="owner/repo", ref="a" * 40)
    assert not (tmp_path / "out.json").exists()
    response.read.return_value = b"x" * 1_048_577
    with pytest.raises(ValueError, match="1 MiB"):
        pull("react-loop-resilience", tmp_path / "out.json", repository="owner/repo", ref="a" * 40)


def test_plugin_listing_never_loads_and_registration_is_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agentic_chaos.chaos.faults import FAULT_REGISTRY, TokenTimeoutFault
    from agentic_chaos.hub import plugins

    class CustomFault(TokenTimeoutFault):
        name = "custom_timeout"

    first = Mock(name="entry")
    first.name = "custom_timeout"
    first.load.return_value = CustomFault
    second = Mock()
    second.name = "invalid"
    second.load.return_value = object
    monkeypatch.setattr(plugins, "entry_points", lambda **kwargs: [first, second])
    assert installed_plugins() == ["custom_timeout", "invalid"]
    first.load.assert_not_called()
    with pytest.raises(ValueError, match="BaseFault"):
        load_plugins()
    assert "custom_timeout" not in FAULT_REGISTRY
    monkeypatch.setattr(plugins, "entry_points", lambda **kwargs: [first])
    try:
        assert load_plugins() == ["custom_timeout"]
        assert isinstance(FAULT_REGISTRY["custom_timeout"](), CustomFault)
        with pytest.raises(ValueError, match="Duplicate"):
            load_plugins()
    finally:
        FAULT_REGISTRY.pop("custom_timeout", None)


def test_cli_and_recipe_script_binding(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["hub", "list"])
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.output)["recipes"]) >= 6
    assert runner.invoke(app, ["hub", "search", "rag"]).exit_code == 0
    assert (
        runner.invoke(
            app, ["hub", "pull", "react-loop-resilience", str(tmp_path / "recipe.json")]
        ).exit_code
        == 0
    )
    script = tmp_path / "app.py"
    script.write_text("from agentic_chaos import chaos_call\nchaos_call(lambda: 'answer')\n")
    report = tmp_path / "report.json"
    result = runner.invoke(
        app,
        [
            "chaos",
            "run",
            str(script),
            "--experiment",
            "rag-context-poisoning",
            "--save",
            str(report),
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(report.read_text())
    assert data["chaos_events"]
    assert data["chaos_events"][0]["detail"]["hub"]["name"] == "rag-context-poisoning"
    assert len(data["chaos_events"][0]["detail"]["hub"]["sha256"]) == 64
    result = runner.invoke(
        app,
        [
            "chaos",
            "run",
            str(script),
            "--experiment",
            "rag-context-poisoning",
            "--inject",
            "token_timeout",
        ],
    )
    assert result.exit_code != 0


def test_registry_catalog_matches_valid_documents() -> None:
    registry = Path(__file__).resolve().parents[1] / "hub"
    catalog = json.loads((registry / "index.json").read_text())
    assert len({row["name"] for row in catalog}) == len(catalog)
    assert {source.stem for source in (registry / "recipes").glob("*.json")} == {
        row["name"] for row in catalog
    }
    for row in catalog:
        document = json.loads((registry / "recipes" / (row["name"] + ".json")).read_text())
        assert document["name"] == row["name"]
        assert document["description"] == row["description"]
        assert validate_experiment(document, check_targets=False).ok
        if row["name"] in {item["name"] for item in list_recipes()}:
            assert document == recipe(row["name"])


def test_remote_catalog_and_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from agentic_chaos import hub

    network = MagicMock()
    monkeypatch.setattr(hub, "urlopen", network)
    response = network.return_value.__enter__.return_value
    row = {"name": "react-loop-resilience", "description": "ReAct tools"}
    response.read.return_value = json.dumps([row]).encode()
    assert hub.remote_recipes("owner/repo", "a" * 40, "tools")[0]["source"].startswith("github:")
    assert hub.remote_recipes("owner/repo", "a" * 40, "absent") == []
    response.read.return_value = json.dumps([row, row]).encode()
    with pytest.raises(ValueError, match="Duplicate"):
        hub.remote_recipes("owner/repo", "a" * 40)
    response.read.return_value = json.dumps(recipe(row["name"])).encode()
    assert pull(
        row["name"], tmp_path / "remote.json", repository="owner/repo", ref="a" * 40
    ).exists()


def test_binding_preserves_fault_options_and_ignores_placeholder_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from agentic_chaos import hub

    data = recipe("rag-context-poisoning")
    data["faults"][0]["payload"] = "CUSTOM_SYNTHETIC_VALUE"
    data["target"] = "never_import_this_module:main"
    monkeypatch.setattr(hub, "recipe", lambda name: data)
    script = tmp_path / "app.py"
    script.write_text(
        "from agentic_chaos import chaos_call\nprint(chaos_call(lambda: 'original'))\n"
    )
    result = CliRunner().invoke(
        app, ["chaos", "run", str(script), "--experiment", "rag-context-poisoning"]
    )
    assert result.exit_code == 0, result.output
    assert "CUSTOM_SYNTHETIC_VALUE" in result.output
    assert "1/1 contracts passed" in result.output
