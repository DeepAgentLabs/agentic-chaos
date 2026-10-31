# Changelog

All notable changes to this project are documented here.

## [Unreleased]

## [0.9.0] - 2026-10-31

### Added

- `agentic_chaos.probes`: reusable steady-state probes, separate from faults.
  - `HttpProbe` checks an endpoint's status and body using only the standard
    library.
  - `ResponseQualityProbe` checks an answer: `expect_contains`,
    `expect_not_contains`, `expect_regex`, an `expect` predicate, and a
    `reference` with `min_similarity` scored by `HeuristicJudge` or any v0.3
    judge.
  - `LatencyProbe` checks the max or median of `samples` calls against
    `max_ms`.
  - `FunctionProbe` runs any Python check.
  - The `Probe` base class is for custom probes.
  - Every probe takes `phases` (`pre`, `during`, `post`), `retries`,
    `retry_delay_seconds` and a `weight`. Running a probe never raises for an
    unhealthy system.
- `chaos_run()` runs the pre/during/post lifecycle:
  - Pre-chaos probes must pass before any fault is injected
    (`require_steady_state`).
  - `during` probes run with faults still active.
  - `post` probes check recovery.
  - Probe time is kept out of the measured run duration.
- `agentic_chaos.resilience`:
  - `compute_resilience()` gives a 0-100 score (graded A-F) from five
    weighted components: recovery, probes, latency, retry efficiency and
    cost. A component the run cannot show is left out and the weights are
    renormalized.
  - Per-event verdicts: `retried`, `fallback`, `tolerated`, `judged`,
    `unrecovered`, `escaped` and `unverified`, with a per-fault breakdown.
  - The score is inconclusive (`None`) after a failed pre-chaos probe, for
    dry runs, when no fault fired and when nothing can be computed.
  - It reads the report only, so saved reports can be rescored.
- `ResilienceHistory`: a local JSON trend store holding one compact entry per
  run.
  - Trends compare against the latest scored run with the same name.
  - Retention: `max_runs` per name and `max_age_days`.
  - Writes are atomic.
- `ChaosWorkflow(probes=..., weights=...)` and
  `run(baseline=..., history=...)`:
  - Pre-chaos probes gate the whole workflow.
  - `during` probes run in every step and are tagged with the step name.
  - `post` probes are skipped for suspended runs.
  - Every run is scored.
- Experiment files gain `probes:` (`http`, `response_quality`, `latency`,
  `function`) and `resilience:` (`min_score`, `weights`, `history`).
  Validation is located, with did-you-mean suggestions, and never executes
  targets.
- `@pytest.mark.chaos(probes=[...], min_score=N)`. Every chaos test is scored
  and the terminal summary shows the lowest score.
- CLI:
  - `--probe`, `--min-score`, `--history`, `--history-max-runs` and
    `--history-max-age-days` on `chaos run` and `agent run`.
  - `--min-score`, `--baseline` and the history options on `experiment run`
    and `chaos workflow run`.
  - Every run prints a probe table and a Rich resilience report with
    per-component and per-fault bars and the trend.
  - The new `score show` (offline rescoring, `--weight`, `--json`), `score
    history` and `score prune` commands.
- Supporting material:
  - the v0.9 guide
  - an offline resilience demo
  - a probed experiment gated on the score
  - a nightly GitHub Actions resilience gate
  - a reproducible demo GIF
  - Lens/Tower/MCP compatibility tests for scored reports

### Changed

- Package version is `0.9.0`; v0.9 is complete.
- `ChaosReport` and `WorkflowReport` gain the optional `probes` and
  `resilience` fields and a `resilience_score` property. Older reports still
  load.
- AIOS exports add a derived `resilience_score` measurement when a score was
  computed. Probe results and the breakdown ride in the producer extension.
  Native event shapes and IDs are unchanged.
- Sibling runtimes need no change. Agentic Sidecar 0.9.1 widens its optional
  `agentic-chaos` extra to admit 0.9, and MCP 0.4.4 pins hosted images to
  0.9.0.

## [0.8.0] - 2026-10-18

### Added

- `Scope` explosion-radius control (`steps`, `providers`, `exclude_steps`,
  `exclude_providers`) on every built-in fault and on `cascade()`. Scope is
  checked before probability sampling, so out-of-scope calls consume no random
  draws, burst counts or preview state and never appear in dry-run plans.
  Exclusions win and include lists fail closed for unlabelled calls.
  `chaos_call`, `chaos_acall` and the stream wrappers accept a
  `chaos_provider` label, set automatically by the provider patches.
  `chaos.toml` profiles accept per-fault `scope` tables.
- `agentic_chaos.workflows`: `ChaosWorkflow` with `Step`, `HealthCheck`,
  `Parallel`, `Suspend` and reusable, parameterized `Template` nodes.
  - Steps run in fresh sessions with fresh fault copies, their own contracts,
    breaker and scope.
  - Health checks gate stages with no session active.
  - Parallel branches run in isolated contexts.
  - Suspend gates take approvers and resume with `resume_from`.
  - Workflow-level scopes and breakers apply to every step.
- `WorkflowReport` (`kind: chaos_workflow`, `schema_version: "1.0"`) records
  each node's result and every step's native report. Top-level `chaos_events`
  carry `detail.workflow` provenance. `to_chaos_report()` merges all steps for
  contracts and AIOS export.
- `fuzz_topology()` places one node-scoped fault per trial, weighted by fan-out
  (coordinators are hit more often than leaf tools), with type-aware default
  pools. The topology comes from a fault-free baseline run or is passed in.
  Results are reproducible by seed and report unreached trials separately.
- `agentic_chaos.experiments`: declarative YAML, JSON and TOML experiments.
  - A single-stage form (`faults`, `assertions`, `repeat`) and a `workflow`
    form with templates and `${param}` substitution.
  - Fields for `safety`, `scope`, `dry_run` and `schedule`.
  - `validate_experiment()` reports every issue with its location and a
    did-you-mean suggestion: unknown fields, faults, parameters and contracts;
    out-of-range values; scopes; cron fields and time zones; recursive
    templates; duplicate node names.
  - Validation never executes targets: files are parsed with `ast`, and
    modules are located with `find_spec`.
- A five-field cron parser with names, steps, macros, Vixie day-of-month/
  day-of-week semantics and `next_runs()` previews.
- CLI:
  - `experiment validate` (`--strict`, `--json`, `--no-target-check`,
    `--base-dir`)
  - `experiment run` / `chaos workflow run` (`--save`, `--save-report`,
    `--save-aios`, `--dry-run`, `--approve`, `--approve-all`, `--resume-from`,
    `--no-input`). Exit code 3 means a run is waiting at a gate.
  - `chaos workflow validate`
  - `experiment schedule` (crontab or GitHub Actions snippets)
  - `agent fuzz`
- Optional `yaml` extra (`pyyaml>=6.0`).
- Supporting material:
  - the v0.8 guide
  - an offline support agent with single-stage and multi-stage experiment
    files
  - a Python workflow/lint/fuzz demo
  - a scheduled GitHub Actions example
  - a reproducible demo GIF
  - Lens/Tower/MCP/AIOS-schema compatibility tests
  - a CI smoke test of experiments from the installed wheel

### Changed

- Package version is `0.8.0`; v0.8 is complete.
- `ChaosReport` gains the optional `workflow` summary, which the AIOS export
  carries in the producer extension. Native event shapes and IDs are
  unchanged, and older reports still load.
- Sibling runtimes need no change. Agentic Sidecar 0.8.5 widens its optional
  `agentic-chaos` extra to admit 0.8, and MCP 0.3.13 pins hosted images to
  0.8.0.

## [0.7.0] - 2026-10-17

### Added

- Sequential fault cascades with native child events and cascade provenance.
- Bounded binary search for deterministic, monotonic recovery thresholds.
- Response poisoning with three output strategies and two synthetic instruction attacks.
- Explicit-price retry cost estimation through `agentic-chaos estimate`.
- Offline synthetic resilience/containment example with a bypassed negative control,
  usage guide, demo and sibling artifact regression coverage.

### Compatibility

- Standalone runtime and existing event/report shapes remain compatible.
- Sidecar 0.8.3 admits Chaos 0.7; MCP 0.3.10 updates published image pins.

## [0.6.0] - 2026-10-17

### Added

- pytest plugin (`pytest_agentic_chaos`, auto-registered through a `pytest11`
  entry point): `@pytest.mark.chaos(faults=..., contracts=..., must_recover=...,
  baseline=..., profile=..., breaker=..., dry_run=...)` runs a test inside a chaos
  session and fails it when a contract does not pass. Markers are inert unless
  pytest runs with `--chaos` (or `chaos = true` in the ini file).
  `--chaos-report-dir` writes per-test native reports and contract results, and
  `--chaos-contract` applies a contract to every chaos test. The `chaos` fixture
  exposes the live session, cost recording and topology attachment. Async tests
  under pytest-asyncio or anyio are supported. Install `agentic-chaos[pytest]`.
- `agentic_chaos.contracts`: `CompletesWithin`, `NoUnhandledError`,
  `MaxRetries`, `RecoveredAfterFailure`, `MaxCostImpact`, `NoRetryStorm` and
  `FullTopologyTraversal`, plus `check_contracts()`, `assert_contracts()`,
  `ContractReport`, `ContractViolationError` (an `AssertionError`) and a compact
  spec syntax (`max_retries:3,step=search`). Results are `passed`, `failed` or
  `inconclusive`, and inconclusive never passes.
- `baseline=True` on the marker runs the test once as a dry run first, giving
  `MaxCostImpact` and `FullTopologyTraversal` a baseline from the same code path.
- A bounded per-session call log written by `chaos_call()`, `chaos_acall()` and
  the stream wrappers. Reports gain the additive fields `calls`, `calls_dropped`
  and `unhandled_error`; older reports still load.
- `ChaosSession.to_report()` builds the native report and records an escaped
  exception, including the fault event it carries.
- CLI: `--contract`, `--baseline` and `--save-contracts` on `chaos run` and
  `agent run`, plus `contracts check` and `contracts list`. A failing contract
  exits 1; a script's own exit code and breaker aborts take precedence.
- The AIOS run export carries `calls: {recorded, dropped}` and `unhandled_error`
  in the `io.deepagentlabs.agentic-chaos` extension. No core AIOS object or
  schema change.
- v0.6 guide, offline contracts demo, `examples/pytest_chaos` suite, a GitHub
  Actions example, a reproducible demo GIF, and Lens/Tower/MCP compatibility
  tests for the new report fields. CI checks that the wheel ships the plugin.

### Changed

- Package version is `0.6.0`; v0.6 is complete. The native event shape and IDs
  are unchanged. Sibling runtimes need no change. Agentic Sidecar 0.8.1 widens
  its optional `agentic-chaos` extra, which was capped below 0.6.
- `chaos run` / `agent run` reports now include the call log and, when the
  script crashes, `unhandled_error`.
- The landing page marks v0.4–v0.6 shipped and describes v0.2's helpers as
  framework-agnostic.

## [0.5.3] - 2026-10-13

### Added

- `agentic_chaos.integrations.agenticlens.span_attributes(event)` and
  `mark_span(span, event)`: tag an AgenticLens structured-trace span with
  `chaos.injected`, `chaos.fault_type`, `chaos.event_id`, and `chaos.outcome`.
  AgenticLens 0.7.0 diagnoses such spans as injected faults and uses them as
  ground truth for `agenticlens attribution-accuracy`. Both helpers are
  duck-typed; the module still never imports AgenticLens at runtime.

### Changed

- The optional `agenticlens` extra now requires `agenticlens>=0.7.0`.

## [0.5.2] - 2026-10-13

### Added

- Session-scoped `CircuitBreaker` / `ChaosAbortedError`, explicit cost and
  token-price accounting, rolling failure-rate limits, cooperative elapsed-time
  limits, and maximum injection counts.
- Shared sync/async/stream/provider safety checks; sticky abort blocks later
  instrumented dispatches, with already-running work recorded separately.
- Python and CLI dry-run: selected faults are previewed without changing target
  calls or stream delivery. Targets still execute and may incur real API spend.
- Additive native report fields for abort reason, preview plans, cost, injection
  count, and in-flight work. CLI saves evidence and exits nonzero on abort.
- AIOS export preserves safety fields in the producer extension and maps an
  aborted run to `cancelled`, without inventing preview failure evidence.
- Safety API guide, offline example, reproducible demo GIF, containment tests
  with a bypass negative control, and Lens/Tower/MCP/AIOS compatibility checks.

### Fixed

- Pass-through fault eligibility and finite burst/turn previews do not invent
  injections; admission reserves capacity and commits only observed fault events.
- Stream cleanup exceptions count as failed completions; delivery rechecks
  safety after an upstream read returns.

### Changed

- Package version is `0.5.2`; v0.5.x safety rails are complete. Limits are
  cooperative and require instrumentation; unknown costs and already-running
  external work are not silently controlled. No sibling patch release required.


## [0.5.1] - 2026-10-13

### Added

- `agentic_chaos.export.to_aios_run()` derives an AI Operations Specification
  v0.4-draft `run` artifact from a `ChaosReport` (or its JSON), following the
  reviewed mapping in ai-operations-spec's
  `reviews/framework-mappings/agentic-chaos.md`. Each event becomes a step-scoped
  occurrence plus a `reliability_event` that `signals-on` it. Package-specific
  fields ride in the `io.deepagentlabs.agentic-chaos` extension. The export claims
  no recovery, step outcome, or retry chain the native events cannot show.
- `--save-aios PATH` on `chaos run` and `agent run`; the run status is `failed`
  when the script crashes. AIOS step IDs are generated per run, so they are always
  valid and collision-free; native `step_id`/`step_name` go in step `attributes`.

### Fixed

- `chaos run` / `agent run` now catch a target script's failing `sys.exit()`, so
  `--save` / `--save-aios` still write their reports. The command then exits with
  the script's own exit code; `sys.exit(0)` counts as success.
- Tests that validate exports against the published v0.4 run schema when an
  `ai-operations-spec` checkout sits next to this repo; CI checks one out in the
  sibling-integration job.

### Changed

- Package version is `0.5.1`. The native `ChaosReport` and event shape are
  unchanged.

## [0.5.0] - 2026-10-12

### Added

- Four lazy sync/async stream faults: cut, bounded hang, slow first-token
  delivery, and slow inter-chunk delivery; `chaos_stream()` / `chaos_astream()`
  emit events when delivery is affected and close owned upstream streams.
- Reversible, context-scoped patches for explicit OpenAI, Anthropic, and
  Google Gen AI client instances, with optional SDK dependencies.
- `AuthErrorFault` (401/403) and `ContextLengthFault` (400), using package
  exceptions that carry their chaos events.
- Seeded per-call/per-stream probability on every fault (defaults to 1.0).
- Named `chaos.toml` profiles with constructor parameters, Python
  `load_profile()`, and `--profile` / `--profile-file` on both run commands.
- `chaos_acall()` for async call injection with cancellable provider work
  and isolated event buffering.
- Offline examples, reproducible demo GIF, API guide, real SDK smoke tests,
  and Lens/Tower/MCP sibling compatibility checks in CI.

### Changed

- Package version is `0.5.0`; native ChaosReport/event shape is unchanged.
- Both run commands require exactly one of `--inject` or `--profile`.
- Python 3.10 uses the conditional `tomli` dependency for TOML loading.
- Structured experiment/AIOS export backlog and v0.5.x safety rails remain planned.

### Added

- `scripts/benchmark_overhead.py` and `make benchmark` — measures
  `chaos_call()`'s per-call instrumentation overhead against a direct call,
  both with no active `chaos_session()` and with a fault actively
  triggering. Documented in README.md's new "Instrumentation Overhead"
  section.

## [0.4.0] - 2026-08-15

### Added

- **Prompt/Model Drift Detector (v0.4)**:
  - New `agentic_chaos.drift` module with `DriftSnapshot`,
    `DriftReport`, `compare_snapshots()`, JSON storage helpers, and
    cooldown-aware emission state.
  - `agentic-chaos drift snapshot` CLI command for capturing local prompt,
    model, output, and retrieval baselines as JSON.
  - `agentic-chaos drift compare` CLI command for comparing a current run
    to a stored baseline, returning exit code `2` on detected drift for
    CI-friendly gating.
  - Prompt hash/diff detection, model fingerprint/version detection,
    output distribution distance checks, and retrieval set drift checks.
  - Cooldown state files to suppress repeated unchanged drift reports
    during scheduled cron/CI runs.
  - `ChaosReport.drift_report` field (schema v1.4) for exported drift
    findings alongside existing chaos artifacts.
  - `attach_drift_report()` helper in the optional AgenticLens integration.
  - New example: `examples/drift_detection_demo.py`.

### Changed

- Bumped package version to `0.4.0`.
- `agentic-chaos drift` is now fully implemented instead of a placeholder.

## [0.3.0] - 2026-08-08

### Added

- **Fidelity Judges & Handoff Chaos (v0.3)**:
  - New `agentic_chaos.judges` module with `JudgeProtocol`,
    `fidelity_session()`, `HeuristicJudge`, `DeepEvalJudge`, and
    `PydanticEvalsJudge`.
  - `ChaosEvent.fidelity_score` field (schema v1.3) for judge-produced
    quality comparisons when a baseline result exists.
  - `HandoffCorruptionFault` for edge-scoped multi-agent faults with
    `"corrupt"`, `"drop"`, and `"delay"` modes.
  - `MemoryCorruptionFault(mode="decay", rate=...)` for progressive
    long-running state degradation across turns.
  - Edge provenance on `ChaosEvent`: `edge_id`, `from_node`, and `to_node`.
  - New example: `examples/chaos_handoff_and_judges_demo.py`.
  - New CLI rendering for fidelity scores when present in recorded events.

### Changed

- Bumped package version to `0.3.0`.
- Drift placeholders and docs now point to v0.4 instead of v0.3.
- `HandoffCorruptionFault(mode="corrupt")` now calls the downstream node
  exactly once, avoiding duplicate side effects on non-pure nodes. As a
  tradeoff, corrupt-mode handoffs do not emit a comparative `fidelity_score`
  unless the caller captures a separate baseline.

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
