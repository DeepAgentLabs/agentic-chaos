# Changelog

All notable changes to this project are documented here.

## [Unreleased]

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
