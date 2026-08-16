## agentic-chaos Development Reference

## Ecosystem Context

### Role in DeepAgentLabs

`agentic-chaos` is the resilience and failure-validation package in the
DeepAgentLabs ecosystem. It deliberately injects faults into LLM and agent
workflows so teams can measure degraded behavior, recovery quality, and failure
impact before those issues appear in production.

### Owns

- Fault models, injection primitives, chaos sessions, and experiment-oriented
  resilience evidence
- Chaos-specific artifacts that can be exported as AI Operations Specification
  objects
- Adapters that let external systems observe or consume chaos events without
  taking ownership of the chaos logic itself

### Does Not Own

- The canonical schema or shared runtime contract — that belongs in
  `ai-operations-spec`
- General observability, profiling, or evaluation workflows — those belong in
  `agenticlens`
- Agent supervision/governance or pre-action intervention logic — that belongs
  in `agentic-sidecar`
- A broad orchestration or control-plane surface — that belongs in
  `deep-agentic-core-mcp`

### Integrates With

- `ai-operations-spec` for shared object shapes, evidence compatibility, and
  export boundaries
- `agenticlens` for analyzing chaos outcomes as part of operational evidence
- `deep-agentic-core-mcp` when chaos capabilities need to be exposed through an
  MCP-native interface
- `agentic-sidecar` only at explicit coordination boundaries, such as evaluating
  how an agent responds to induced failure

### Current Roadmap Focus

The next major step is structured experiment reports with provenance and
synthetic resilience scenarios. Changes in this repo should move the package
toward reproducible resilience evidence, not just ad hoc fault injection.

### Before You Build Here

- Put new shared concepts or cross-package object definitions in
  `ai-operations-spec` first if they are meant to be ecosystem-wide
- Reuse `agenticlens` for analysis and reporting patterns instead of rebuilding
  a second observability layer here
- Keep integrations thin: this package should generate and describe failure,
  not become the dashboard, policy engine, or universal runtime abstraction

## Build and Run

- Install: `make install` (runs `uv sync --extra dev`)
- Test: `make test` or `make check` (lint + format + typecheck + test)
- Lint: `make lint`
- Type check: `make typecheck`
- CLI: `uv run agentic-chaos <command>`

## Code Style

- Strict typing (mypy strict mode, Python 3.10+)
- Line length: 100
- Ruff rules: E, F, I, UP, B, SIM, N
- One purpose per file (separation of concerns)
- Chaos artifacts must be exportable as AI Operations Specification objects

## Repo Map

| Path | Purpose |
|------|---------|
| `src/agentic_chaos/chaos/` | LLM-level fault injection — `TokenTimeoutFault`, `RateLimitStormFault`, `SilentDegradationFault` |
| `src/agentic_chaos/chaos/faults.py` | Fault class definitions |
| `src/agentic_chaos/chaos/inject.py` | `chaos_call()` — the core injection wrapper |
| `src/agentic_chaos/chaos/context.py` | `ChaosSession` context manager |
| `src/agentic_chaos/agents/` | Agent-level faults — `ToolCallFailureFault`, `MemoryCorruptionFault`, `InfiniteLoopFault` |
| `src/agentic_chaos/agents/langgraph.py` | LangGraph adapter (`wrap_tool()`, `wrap_node()`) |
| `src/agentic_chaos/agents/topology.py` | `TopologyTracker`, `AgentTopology` |
| `src/agentic_chaos/drift/` | Prompt/model drift detection (planned) |
| `src/agentic_chaos/integrations/` | Optional adapters (AgenticLens: `attach_events()`, `step_kwargs()`) |
| `src/agentic_chaos/cli/` | CLI entry point and subcommands |
| `src/agentic_chaos/models/` | `ChaosReport`, `ChaosEvent`, schema extensions |
| `tests/` | Pytest test suite |
| `Makefile` | Local dev automation |

## Entry Points

- Console script: `agentic-chaos` → `cli/`
- Injection API: `from agentic_chaos import chaos_call, chaos_session`
- Agent API: `from agentic_chaos.agents import wrap_tool, wrap_node`

## Package Boundaries

- This package is **standalone** — `pip install agentic-chaos` works with zero
  other dependencies from DeepAgentLabs
- AgenticLens integration is optional (`agentic_chaos.integrations.agenticlens`)
  and auto-skips if agenticlens is not installed
- `models/` must not import from `integrations/`
- `agents/` imports from `chaos/` (base classes, registry, `chaos_call`) but
  `chaos/` must not import from `agents/`
- All faults inherit from a common base in their respective module

## Adding a New Fault

1. Add fault class in `chaos/faults.py` (LLM-level) or `agents/faults.py` (agent-level)
2. Register in the fault catalog (CLI discovery)
3. Emit `ChaosEvent` with proper fields
4. Add test in `tests/`
5. Update README with usage example

## Feature Completion Expectations

- Every behavior change must include tests.
- User-facing features must include or update examples in `README.md`, CLI
  usage text, or test fixtures that demonstrate expected usage.
- When a roadmap item or milestone meaningfully changes status, update
  `README.md` and the roadmap document in the same change.
- If that milestone or release changes the public ecosystem story, also update
  the shared org-profile docs in the `.github` repository:
  `profile/README.md` and, when relevant, `profile/ROADMAP.md`.
- When work is packaged as a release-ready change, also update
  `pyproject.toml`, `src/agentic_chaos/__init__.py`, and `CHANGELOG.md`.

## AgenticLens Integration

The integration is a thin adapter in `integrations/agenticlens.py`. It converts
`ChaosEvent` objects into AgenticLens step kwargs. Tests for this use
`pytest.importorskip("agenticlens")` and skip automatically without it.

## Pre-push Checklist

Run `make check` before every push. It runs: lint → format-check → typecheck → test.

If you also have agenticlens checked out as a sibling, run the full suite:
```bash
uv sync --extra dev --extra agenticlens
uv run pytest
```

## Release

Two phases, split by the merge to `main` — bumping happens before, and the
tag-driven release automation happens after.

**1. Pre-release (on the feature branch, before merge):** Bump version in
`pyproject.toml`, `src/agentic_chaos/__init__.py`, and `CHANGELOG.md` (a
dated release section under `[Unreleased]`). Commit as part of the
branch's normal history; goes in with the rest of the PR.

**2. Release (on `main`, once that branch has merged):** plain `git`, no
manual `gh release` step required.

1. Pull the merge commit on `main`.
2. Tag: create an annotated `vX.Y.Z` tag pointing at the merge commit,
   using the `CHANGELOG.md` release section for that version as the tag
   message:
   `git tag -a vX.Y.Z -F <file-with-that-section> --cleanup=verbatim`.
   `--cleanup=verbatim` is required — git's default cleanup silently strips
   lines starting with `#`, which would eat the changelog's `###` headers.
3. Push the tag: `git push origin vX.Y.Z`.

That tag push is the release trigger. `release-pypi.yml` runs automatically
and does both of the following from the same tag:

- publishes the package to PyPI via Trusted Publishing (OIDC)
- creates the GitHub Release object for `vX.Y.Z`

The GitHub Release title is the tag name, and its body is copied from the
matching `CHANGELOG.md` section so the changelog, tag, PyPI release, and
GitHub Releases page stay aligned.
