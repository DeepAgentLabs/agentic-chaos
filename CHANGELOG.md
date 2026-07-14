# Changelog

All notable changes to this project are documented here.

## [Unreleased]

## [0.2.0] - 2026-07-13

### Added

- **Agent Failure Injector (v0.2)** — three new agent-level fault types:
  - `ToolCallFailureFault` — force tool calls to error, timeout, or return
    empty data. Supports `tool_name` filtering to target specific tools.
    Modes: `"error"`, `"timeout"`, `"empty"`.
  - `MemoryCorruptionFault` — corrupt shared agent state by truncating,
    injecting garbage, or garbling text content. Modes: `"truncate"`,
    `"inject"`, `"garble"`.
  - `InfiniteLoopFault` — force agents to loop past their normal termination
    point for a configurable number of extra turns, then pass through.
- **Agent topology tracking** — `TopologyTracker` class and `AgentTopology` /
  `AgentNode` / `AgentEdge` models for recording which agents, tools, and
  memory stores communicated during a chaos run.
- **LangGraph adapter** — `wrap_tool()` and `wrap_node()` helpers that
  transparently inject chaos into tool/node functions with optional topology
  tracking. No LangGraph dependency required.
- **`agentic-chaos agent run` CLI command** — run agent scripts with
  agent-level faults active. Accepts `--inject`, `--framework`, and `--save`.
- `ChaosReport.agent_topology` field (schema v1.2) — optional topology data
  embedded in chaos reports.
- New `"looped"` outcome type for `ChaosEvent`.
- All v0.2 faults registered in the global `FAULT_REGISTRY` — discoverable
  via `agentic-chaos chaos list-faults` and `resolve_faults()`.
- New example: `examples/chaos_agent_failure_demo.py` — demonstrates all
  three agent faults, `wrap_tool()`, and `TopologyTracker`.
- 38 new tests covering agent faults, topology, and integration with
  `chaos_session` / `chaos_call`.

## [0.1.1] - 2026-07-10

### Changed

- Testing release; version bump to 0.1.1.

## [0.1.0] - 2026-07-10

Initial release.

### Added

- `.github/workflows/release-pypi.yml`: publishes to PyPI on a `v*` tag push
  or a published GitHub Release, via Trusted Publishing (OIDC) against the
  `pypi` environment -- no stored API token.

### Fixed

- `uv sync --extra dev` (and CI) failed outright for anyone without a sibling
  `agenticlens` checkout: `[tool.uv.sources]`'s local path override for the
  optional `agenticlens` extra made `uv` try to validate/refresh that extra
  on *every* sync, even when it wasn't requested. Fixed by using `--frozen`
  wherever the sibling checkout isn't guaranteed (README's plain install
  instructions, CI's `test-core` and `package` jobs) -- see README's
  Installation/Development sections.

### Changed

- **`agenticlens` is no longer a required dependency.** `agentic_chaos.chaos`
  (`chaos_call`, `chaos_session`, the fault types) and the CLI now work
  standalone against any Python callable, no other package needed.
  `chaos_call()` takes plain `step_id`/`step_name` strings instead of an
  AgenticLens `StepHandle`.
- `agentic-chaos chaos run --save` now writes this package's own standalone
  `ChaosReport` (`id`, `name`, `start_time`, `end_time`, `chaos_events`)
  instead of requiring the target script to build an AgenticLens `Workflow`
  via `profile()`. A `ChaosReport`'s JSON is still valid AgenticLens
  `Workflow` JSON (same field names, no `steps`), so `agenticlens analyze`
  still works on it directly if you have AgenticLens installed -- interop
  through a shared JSON shape, not a code dependency.
- `agentic-chaos chaos run` now catches an uncaught exception from the target
  script, still renders/saves whatever chaos events were recorded, and exits
  non-zero -- previously an unhandled fault would crash the CLI before
  `--save` ran.

### Added

- `examples/chaos_advanced_faults_demo.py`: `TokenTimeoutFault(mode="delay")`
  and a custom `SilentDegradationFault(degrade_fn=...)`, the two fault
  options that weren't demonstrated anywhere outside the tests. README's
  Fault Types section links to it and the other examples now have an index
  table.
- `agentic_chaos.integrations.agenticlens` (optional, `pip install
  agentic-chaos[agenticlens]`): `attach_events()` merges a chaos session's
  events onto an AgenticLens `Workflow`; `step_kwargs()` extracts
  `step_id`/`step_name` from a `StepHandle`. Neither `agentic_chaos`'s core
  nor its CLI imports this module or `agenticlens`.
  `examples/chaos_with_agenticlens_demo.py` shows the full round trip.
- `agentic_chaos.chaos` — the LLM Chaos Toolkit (v0.1 milestone):
  - `chaos_session()` / `chaos_call()` — explicit, contextvar-based fault
    injection API.
  - Three fault types: `TokenTimeoutFault`, `RateLimitStormFault`,
    `SilentDegradationFault`.
  - `agentic-chaos chaos run` CLI command.
  - `chaos_events` schema (v1.1), documented in agenticlens's
    `docs/workflow-schema-spec.md`.
- `agenticlens.recommenders.ChaosImpactRecommender` — thin adapter (in the
  agenticlens repo) that reads `chaos_events` and reports resilience findings
  alongside AgenticLens's existing cost/latency recommendations.
- Placeholder `agentic_chaos.agents` (v0.2) and `agentic_chaos.drift` (v0.3)
  modules — not yet implemented.
