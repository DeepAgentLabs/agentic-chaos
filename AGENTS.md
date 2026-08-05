## agentic-chaos Development Reference

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
