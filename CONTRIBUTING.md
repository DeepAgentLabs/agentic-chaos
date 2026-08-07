# Contributing

Thanks for helping make `agentic-chaos` better for everyone building resilient AI agent systems.

## Local setup

```bash
git clone https://github.com/DeepAgentLabs/agentic-chaos.git
cd agentic-chaos
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Or with `uv`:

```bash
uv sync --extra dev
```

## Development workflow

1. Create a focused branch from `main`.
2. Add or update tests with every behavior change.
3. Run:

```bash
ruff check .
ruff format --check .
mypy
pytest
```

4. Keep PRs focused — one concern per pull request.
5. Write clear commit messages describing *why*, not just *what*.

## Adding a fault type

1. Create a class in `src/agentic_chaos/chaos/faults/`
2. Register it in `FAULT_REGISTRY`
3. Add tests in `tests/`
4. Document in README if user-facing

## Releases

Releases are automated via GitHub Actions when a version tag is pushed.

### Release checklist

1. Update the version string in all three locations:
   - `pyproject.toml` → `version = "X.Y.Z"`
   - `src/agentic_chaos/__init__.py` → `__version__ = "X.Y.Z"`
   - `CHANGELOG.md` → add a `## [X.Y.Z] - YYYY-MM-DD` section
2. Commit: `git commit -am "release: vX.Y.Z"`
3. Tag: `git tag vX.Y.Z`
4. Push: `git push origin main --tags`

The `release-pypi.yml` workflow triggers on the tag push and publishes to PyPI via Trusted Publishing (OIDC).
