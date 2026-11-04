"""Recipe exchange commands."""

import json
from pathlib import Path

import typer

from agentic_chaos.hub import list_recipes, pull, push, remote_recipes
from agentic_chaos.hub.plugins import installed_plugins

app = typer.Typer(help="Discover recipes and stage community contributions.", no_args_is_help=True)


@app.command("list")
def list_command(repository: str | None = None, ref: str | None = None) -> None:
    typer.echo(
        json.dumps(
            {"recipes": _catalog("", repository, ref), "installed_plugins": installed_plugins()}
        )
    )


@app.command("search")
def search_command(query: str, repository: str | None = None, ref: str | None = None) -> None:
    typer.echo(json.dumps(_catalog(query, repository, ref)))


@app.command("pull")
def pull_command(
    name: str, output: Path, repository: str | None = None, ref: str | None = None
) -> None:
    try:
        typer.echo(str(pull(name, output, repository=repository, ref=ref)))
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command("push")
def push_command(source: Path, checkout: Path) -> None:
    try:
        typer.echo(str(push(source, checkout)))
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc


def _catalog(query: str, repository: str | None, ref: str | None) -> list[dict[str, str]]:
    try:
        if repository is None:
            if ref is not None:
                raise ValueError("--ref requires --repository")
            return list_recipes(query)
        if ref is None:
            raise ValueError("--repository requires --ref COMMIT_SHA")
        return remote_recipes(repository, ref, query)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
