"""Offline recipe discovery. Pull and push never execute target code."""

import json
import re
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from agentic_chaos.experiments import validate_experiment
from agentic_chaos.experiments.loader import read_document


def _name(name: str) -> str:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("Expected lowercase recipe words separated by hyphens")
    return name


def list_recipes(query: str = "") -> list[dict[str, str]]:
    """Search bundled names and descriptions without network access."""
    rows = []
    for source in files(__package__).joinpath("recipes").iterdir():
        if source.name.endswith(".json"):
            data = json.loads(source.read_text(encoding="utf-8"))
            row = {"name": data["name"], "description": data["description"], "source": "bundled"}
            if query.casefold() in (row["name"] + row["description"]).casefold():
                rows.append(row)
    return sorted(rows, key=lambda row: row["name"])


def recipe(name: str) -> dict[str, Any]:
    """Return a fresh recipe document without importing its target."""
    source = files(__package__).joinpath("recipes").joinpath(_name(name) + ".json")
    if not source.is_file():
        raise ValueError(f"Unknown bundled recipe: {name}")
    data: dict[str, Any] = json.loads(source.read_text(encoding="utf-8"))
    return data


def _validate(data: Any) -> dict[str, Any]:
    result = validate_experiment(data, check_targets=False)
    if not result.ok:
        raise ValueError(str([issue.as_json() for issue in result.errors]))
    if not isinstance(data, dict):
        raise ValueError("Expected experiment object")
    _name(data["name"])
    return data


def _write(data: dict[str, Any], destination: Path) -> Path:
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(data, indent=2) + "\n")
    return destination


def pull(
    name: str, destination: Path, *, repository: str | None = None, ref: str | None = None
) -> Path:
    """Download without overwriting; remote reads require an immutable GitHub SHA.

    Review all target/probe/workflow paths before executing downloaded recipes.
    """
    _name(name)
    if repository is None:
        data = recipe(name)
    else:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("Expected GitHub owner/repository")
        if ref is None or not re.fullmatch(r"[0-9a-f]{40}", ref):
            raise ValueError("Remote pull requires a full lowercase commit SHA")
        url = f"https://raw.githubusercontent.com/{repository}/{ref}/hub/recipes/{name}.json"
        with urlopen(url, timeout=15) as response:
            payload = response.read(1_048_577)
        if len(payload) > 1_048_576:
            raise ValueError("Recipe exceeds 1 MiB")
        data = json.loads(payload)
    data = _validate(data)
    if data["name"] != name:
        raise ValueError("Recipe identity mismatch")
    return _write(data, destination)


def push(source: Path, checkout: Path) -> Path:
    """Stage a contribution in a GitHub checkout; publication uses an ordinary PR."""
    data = _validate(read_document(source))
    directory = checkout / "hub" / "recipes"
    directory.mkdir(parents=True, exist_ok=True)
    return _write(data, directory / (_name(data["name"]) + ".json"))
