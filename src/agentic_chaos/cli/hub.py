"""Recipe exchange commands."""

import json
from pathlib import Path

import typer

from agentic_chaos.hub import list_recipes, pull, push
from agentic_chaos.hub.plugins import installed_plugins

app = typer.Typer(help="Discover recipes and stage community contributions.", no_args_is_help=True)


@app.command("list")
def list_command() -> None:
    typer.echo(json.dumps({"recipes": list_recipes(), "installed_plugins": installed_plugins()}))


@app.command("search")
def search_command(query: str) -> None:
    typer.echo(json.dumps(list_recipes(query)))


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
