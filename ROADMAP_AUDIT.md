# agentic-chaos roadmap implementation audit

Audit date: 2026-09-11. Baseline: commit `856ebbc2e613185321e7e0109967b071beb95075`
on `main`, clean working tree (this audit's own edits to `ROADMAP.md` and this
file are the only changes made). Scope: the canonical [product
roadmap](ROADMAP.md) — its Release Status table, per-version checkbox
deliverables (v0.1 through v1.0), the shipped-module table, and the
Cross-Project Dependencies section.

**v0.1 through v0.4 are substantially implemented as claimed. One status line
is corrected below for overstated scope (the "LangGraph adapter" wording).
v0.5 through v1.0 are correctly unimplemented — their `[ ]` checkboxes and
🚧 Planned markers match an empty search for any corresponding code.**

## How to read this audit

- **Implemented (I):** usable code exists for the stated scope; evidence and
  test limits are recorded below. This does not assert publication, PyPI
  release status, or independent third-party validation.
- **Partial (P):** the deliverable exists but is narrower than the checkbox
  wording implies, or a dependent piece (usually on the `agenticlens` side)
  is missing.
- **Missing (M):** no implementation of the stated capability was found in
  the inspected source, tests, examples, or configuration.
- **Unverified (U):** the claim depends on internals of a sibling repository
  that this audit does not treat as authoritative to assess.

## Milestone summary

| Milestone | Assessment | Main open work |
| --- | --- | --- |
| v0.1 LLM Chaos Toolkit | Implemented | Demo GIF outstanding (cosmetic, roadmap already marks it `[ ]`) |
| v0.2 Agent Failure Injector | Implemented, one line overstated | "LangGraph adapter" is a framework-agnostic callable wrapper with no LangGraph-specific code, dependency, or test — corrected below |
| v0.2.x Structured Experiment Reports & Synthetic Scenarios | Missing | All five deliverables unimplemented; roadmap already shows them unchecked |
| v0.3 Fidelity Judges & Handoff Chaos | Implemented | `ChaosImpactRecommender` fidelity-score weighting not yet built in `agenticlens` (roadmap already shows this unchecked) |
| v0.4 Prompt/Model Drift Detector | Implemented | Only the attach-side helper (`attach_drift_report()`) exists; no consuming `DriftRecommender` class exists yet in `agenticlens` |
| v0.5 Streaming Faults, Provider Patching & Chaos Profiles | Missing | No streaming fault classes, patch helpers, or `chaos.toml` loader found; matches 🚧 Planned |
| v0.5.x Safety Rails | Missing | No `agentic_chaos.safety` module exists |
| v0.6 Pytest Plugin & Assertions | Missing | No pytest plugin or `agentic_chaos.contracts` found |
| v0.7 Fault Cascades, Adaptive Intensity & Response Poisoning | Missing | No `cascade()`, `find_breaking_point()`, or `PoisonedResponseFault` found |
| v0.8 Chaos Workflows, Declarative Experiments & Explosion Radius | Missing | No `agentic_chaos.workflows` module found |
| v0.9 Resilience Probes & Resilience Score | Missing | No `agentic_chaos.probes` module or resilience-score engine found |
| v1.0 ChaosHub | Missing | No `agentic_chaos.hub` module or plugin entry-point group found |

## Evidence index

Paths are relative to this repository unless noted. Tests substantiate their
covered cases, not every possible behavior of an entire milestone.

| Key | Source | Regression evidence |
| --- | --- | --- |
| CHAOS | [faults](src/agentic_chaos/chaos/faults.py), [inject](src/agentic_chaos/chaos/inject.py), [context](src/agentic_chaos/chaos/context.py), [session](src/agentic_chaos/chaos/session.py) | [test_faults.py](tests/test_faults.py), [test_inject.py](tests/test_inject.py) |
| EVENT/REPORT | [ChaosEvent](src/agentic_chaos/models/chaos_event.py), [ChaosReport](src/agentic_chaos/models/report.py) | [test_chaos_event.py](tests/test_chaos_event.py), [test_report.py](tests/test_report.py) |
| AGENTFAULTS | [agent faults](src/agentic_chaos/agents/faults.py) — `ToolCallFailureFault`, `MemoryCorruptionFault`, `InfiniteLoopFault`, `HandoffCorruptionFault` | [test_agent_faults.py](tests/test_agent_faults.py) |
| TOPOLOGY | [topology tracker](src/agentic_chaos/agents/topology.py), [topology models](src/agentic_chaos/models/agent_topology.py) | [test_agent_topology.py](tests/test_agent_topology.py) |
| LANGGRAPH | [langgraph.py](src/agentic_chaos/agents/langgraph.py) — `wrap_tool()`, `wrap_node()` | Exercised indirectly via [test_cli.py](tests/test_cli.py)'s `agent run` tests; no dedicated adapter test, no `langgraph` dependency anywhere in the repo |
| JUDGES | [judges](src/agentic_chaos/judges/__init__.py) — `HeuristicJudge`, `DeepEvalJudge`, `PydanticEvalsJudge`, `fidelity_session()` | [test_judges.py](tests/test_judges.py) |
| DRIFT | [core](src/agentic_chaos/drift/core.py), [models](src/agentic_chaos/drift/models.py), [storage](src/agentic_chaos/drift/storage.py) | [test_drift.py](tests/test_drift.py) |
| INTEGRATIONS | [agenticlens adapter](src/agentic_chaos/integrations/agenticlens.py) — `attach_events()`, `step_kwargs()`, `attach_drift_report()` | [test_integrations_agenticlens.py](tests/test_integrations_agenticlens.py) — `importorskip("agenticlens")`; passes for real against a sibling `agenticlens==0.4.0` checkout (see Verification) |
| CLI | [cli/main.py](src/agentic_chaos/cli/main.py), [cli/render.py](src/agentic_chaos/cli/render.py) | [test_cli.py](tests/test_cli.py) |

## v0.1 — LLM Chaos Toolkit

| Roadmap deliverable | Status | Evidence / remaining boundary |
| --- | --- | --- |
| `agentic-chaos.chaos` module + CLI subcommand | I | CHAOS, CLI; `chaos run` / `chaos list-faults` covered by `test_chaos_list_faults`, `test_chaos_run_*` |
| `chaos_events` schema extension (documented) | I | EVENT/REPORT defines the field; documented externally at `agenticlens`'s [`docs/workflow-schema-spec.md`](https://github.com/DeepAgentLabs/agenticlens/blob/main/docs/workflow-schema-spec.md) (file confirmed present in the sibling checkout used for this audit) |
| AgenticLens `ChaosImpactRecommender` adapter | I | Confirmed present in the `agenticlens` sibling checkout at `src/agenticlens/recommenders/chaos_impact.py`; it reads `chaos_events[].fault_type`/`outcome` and groups by `(step, fault_type, outcome)` — matches this repo's event shape. This is a sibling-repo file inspected for corroboration, not something this audit can certify as maintained going forward. |
| README section + 1 example script | I | README's Fault Types section; `examples/chaos_customer_support_demo.py` and `examples/chaos_advanced_faults_demo.py` both exist and run standalone |
| demo GIF | M | No `.gif` file anywhere in the repository |

## v0.2 — Agent Failure Injector

| Roadmap deliverable | Status | Evidence / remaining boundary |
| --- | --- | --- |
| `agentic_chaos.agents` module (labeled "LangGraph adapter") | **P** | The three v0.2 fault classes are fully implemented and tested (AGENTFAULTS). `agents/langgraph.py`'s `wrap_tool()`/`wrap_node()` are **framework-agnostic** Python-callable wrappers: `pyproject.toml` declares no `langgraph` dependency, no source or test file imports `langgraph`, and the module's own `TYPE_CHECKING` block is an empty placeholder (`"LangGraph types would go here once we add type stubs"`). The CLI's `--framework langgraph` option is documented in its own help text as **"Currently informational."** Nothing in the wrapper inspects LangGraph's `StateGraph`, node/edge types, or a compiled graph. Corrected in `ROADMAP.md` to describe this as a framework-agnostic helper rather than a LangGraph-specific adapter. |
| `agent_topology` schema extension | I | TOPOLOGY; `test_agent_topology.py` (19 cases) plus CLI round-trip in `test_agent_run_includes_topology_in_report` / `test_agent_run_renders_topology_output` |
| AgenticLens `AgentResilienceRecommender` adapter + resilience score *(deferred to v0.9)* | M | No `AgentResilienceRecommender` class found anywhere in the `agenticlens` sibling checkout. Roadmap already marks this `[ ]`/deferred, which matches. Note: `src/agentic_chaos/models/agent_topology.py`'s own docstring states *"AgenticLens's `AgentResilienceRecommender` reads this to produce resilience scores at the workflow level"* as if that consumer already exists — a stale/aspirational source-code comment inconsistent with the roadmap's own "deferred" framing. Not corrected here (source code is out of this audit's scope); flagged under Issues below. |
| README section + 1 example | I | `examples/chaos_agent_failure_demo.py` confirmed to need "nothing but `agentic_chaos`" (no LangGraph install), consistent with the P finding above |
| demo GIF | M | No `.gif` file found |

## v0.2.x — Structured Experiment Reports & Synthetic Scenarios

All five deliverables are **M**, matching the roadmap's own unchecked boxes:

| Roadmap deliverable | Status | Evidence |
| --- | --- | --- |
| Structured `ExperimentReport` model with provenance fields | M | No `ExperimentReport` class anywhere in `src/` |
| Report export to JSON (AI Operations Specification-compatible) | M | No AIOS export code found (see Integration inventory) |
| 4+ synthetic scenario fixtures in `tests/synthetic/` | M | No `tests/synthetic/` directory exists |
| CLI `--report` flag | M | No `--report` option in `cli/main.py` |
| README section with report schema example | M | Not present |

## v0.3 — Fidelity Judges & Handoff Chaos

| Roadmap deliverable | Status | Evidence / remaining boundary |
| --- | --- | --- |
| `agentic_chaos.judges` module — `DeepEvalJudge`, `PydanticEvalsJudge`, `fidelity_session()` | I | JUDGES; `test_judges.py` covers the heuristic fallback, a monkeypatched DeepEval `LLMTestCase` path, and `PydanticEvalsJudge` against callable, single-arg-`evaluate`, and async-evaluator shapes |
| `fidelity_score` schema extension (`chaos_events` v1.3) | I | `ChaosEvent.fidelity_score`; populated via `score_outcome()` in `chaos/inject.py`, exercised in `test_fidelity_session_scores_silent_degradation_events` / `..._memory_corruption_events` |
| `HandoffCorruptionFault` (`corrupt`/`drop`/`delay`, edge-scoped) | I | AGENTFAULTS; `test_agent_faults.py` covers all three modes plus non-matching-edge and missing-edge-id pass-through |
| `MemoryCorruptionFault(mode="decay", rate=...)` | I | `_decay_result` in `agents/faults.py`; `test_decay_mode_progressively_worsens_state`, `test_decay_mode_rejects_invalid_rate` |
| AgenticLens `ChaosImpactRecommender` update to weight by `fidelity_score` | M | No `fidelity_score` reference anywhere in the `agenticlens` sibling checkout. Roadmap already marks this `[ ]`, which matches. |
| README section + example | I | `examples/chaos_handoff_and_judges_demo.py` confirmed |
| demo GIF | M | No `.gif` file found |

## v0.4 — Prompt/Model Drift Detector

| Roadmap deliverable | Status | Evidence / remaining boundary |
| --- | --- | --- |
| `agentic-chaos.drift` module + CLI subcommand | I | DRIFT, CLI; `drift snapshot`/`drift compare` covered by `test_drift.py` and the drift tests in `test_cli.py` |
| Local snapshot/baseline storage (simple JSON) | I | `drift/storage.py` `load_snapshot`/`save_snapshot`; round-tripped in `test_drift_snapshot_saves_json` |
| AgenticLens `DriftRecommender` adapter surface (`attach_drift_report()`) | **P** | The named surface — `attach_drift_report()` — is implemented and tested (`test_attach_drift_report_sets_workflow_field`, confirmed passing against a real `agenticlens==0.4.0` install, see Verification). No `DriftRecommender` class exists yet on the consuming `agenticlens` side (none found via repo-wide search). The checkbox's parenthetical already scopes the claim narrowly to the attach-side helper, so it is not incorrect, but a reader could infer a working consumer exists; it does not yet. |
| Cooldown-protected scheduled drift checks | I | `should_emit_report`/`update_alert_state`/`DriftAlertState` in `drift/core.py` and `drift/models.py`; `--cooldown-minutes`/`--emit-only-on-change` CLI flags; `test_should_emit_report_suppresses_unchanged_fingerprint_inside_cooldown` and related fingerprint-noise tests |
| README section + example (scheduled drift check in CI) | I | README's "Scheduled CI Example" GitHub Actions snippet + `examples/drift_detection_demo.py` |

## v0.5 — Streaming Faults, Provider Patching & Chaos Profiles

All listed deliverables are **M**. No `StreamCutFault`/`StreamHangFault`/
`SlowTTFTFault`/`SlowChunksFault`, no `patch_openai`/`patch_anthropic`/
`patch_google` helpers, no `chaos.toml` profile loader or `--profile` flag,
no `probability` parameter on any fault class, and no `AuthErrorFault`/
`ContextLengthFault` were found anywhere in `src/`. Matches the roadmap's own
🚧 Planned marker and unchecked boxes.

## v0.5.x — Safety Rails (Circuit Breaker & Dry-Run)

All listed deliverables are **M**. No `agentic_chaos.safety` module exists
(confirmed by directory listing and a repo-wide search for `CircuitBreaker`),
no `max_cost_usd`/`max_failure_rate` parameters on `chaos_session()`, no
`aborted` field on `ChaosReport`, and no `--dry-run` flag on either CLI
command. Matches 🚧 Planned.

## v0.6 — Pytest Plugin & Assertions

All listed deliverables are **M**. No `pytest-agentic-chaos` plugin, no
`agentic_chaos.contracts` module, and no `--chaos` pytest flag exist in this
repository. Matches 🚧 Planned.

## v0.7 — Fault Cascades, Adaptive Intensity & Response Poisoning

All listed deliverables are **M**. No `cascade()`, `find_breaking_point()`,
`PoisonedResponseFault`, or `agentic-chaos estimate` CLI subcommand were
found. Matches 🚧 Planned.

## v0.8 — Chaos Workflows, Declarative Experiments & Explosion Radius

All listed deliverables are **M**. No `agentic_chaos.workflows` module,
`ChaosWorkflow`/`Step`/`HealthCheck`/`Parallel`/`Suspend`/`Template` types,
YAML experiment loader, `Scope` class, or `fuzz_topology()` exist. Matches
🚧 Planned.

## v0.9 — Resilience Probes & Resilience Score

All listed deliverables are **M**. No `agentic_chaos.probes` module, probe
classes, resilience-score computation, trend tracking, or run-history
retention exist. Matches 🚧 Planned.

## v1.0 — ChaosHub (Shared Experiment Registry)

All listed deliverables are **M**. No `agentic_chaos.hub` module, `hub` CLI
subcommand group, `BaseFault` plugin entry-point group, or bundled recipe
files exist. Matches 🚧 Planned.

## Integration inventory

| Target | Status | Evidence / boundary |
| --- | --- | --- |
| `agenticlens` | P | `ChaosImpactRecommender` (v0.1 chaos events) confirmed present and reads this repo's event shape. `attach_events()`, `step_kwargs()`, and `attach_drift_report()` were verified end-to-end against a real `agenticlens==0.4.0` install, not just a mock (see Verification). `AgentResilienceRecommender`, `fidelity_score` weighting, and a consuming `DriftRecommender` do not yet exist on the `agenticlens` side — all three are already unchecked or narrowly scoped in `ROADMAP.md`. |
| `ai-operations-spec` | M | No AIOS export code, schema import, or dependency exists in this repository despite the "Architecture" section's stated goal that "chaos experiments should be exportable as AI Operations Specification artifacts." This is narrative intent, not a versioned checkbox, so no roadmap correction was required — but it is not implemented. |
| `deep-agentic-core-mcp` | U | Not checkable from this repository; no MCP-facing code exists here to audit. |
| `agenticops-control-tower` | U | Roadmap's own text frames this as "coordinate with" once Control Tower ships; not checkable from this repository. |
| LangGraph | P | See the v0.2 finding above: `wrap_tool()`/`wrap_node()` are generic callable wrappers with no LangGraph-specific dependency, import, or type handling. |
| CrewAI / AutoGen | M | Named only as "stretch goals" in narrative text; no adapter code exists. |

## Verification

**Environment note:** this session initially had no working Python
interpreter and no `uv` binary — the repository's committed `.venv` is a
`uv`-managed trampoline pointing at a `cpython-3.14` toolchain that was not
present on this machine, and no system Python could be found either. Network
access was available, so `uv` 0.12.13 was installed fresh via the official
installer (`curl -LsSf https://astral.sh/uv/install.sh | sh`) to unblock
verification rather than relying on static inspection alone.

- `uv sync --extra dev --frozen` (core only, no sibling `agenticlens`
  checkout) then `uv run --frozen pytest -q`: **124 passed, 1 skipped**
  (the skip is `test_integrations_agenticlens.py` via
  `pytest.importorskip("agenticlens")`), 88% overall statement coverage
  (`integrations/agenticlens.py` itself at 0% in this run, since its tests
  were skipped).
- `uv sync --extra dev --extra agenticlens` (the sibling `agenticlens`
  checkout at `E:\DeepAgentLabs\agenticlens` resolved via
  `[tool.uv.sources]`) then `uv run pytest -q --no-cov`: **129 passed, 0
  skipped** — this run exercises the AgenticLens integration adapter against
  a real, installed `agenticlens==0.4.0` package rather than a stub, and is
  the strongest available evidence for the P-rated integration claims above.
- `uv run ruff check .`: all checks passed. `uv run mypy` (strict mode): no
  issues found in 24 source files.
- The unfrozen `uv sync --extra agenticlens` step modified `uv.lock`; it was
  reverted afterward (`git checkout -- uv.lock`) so this audit leaves no
  dependency-lock changes behind. The working tree is otherwise unchanged
  except for this file and the corrections in `ROADMAP.md`.
- CI itself (`.github/workflows/ci.yml`) was not re-run on GitHub Actions;
  it runs the same `pytest`/`ruff check`/`ruff format --check`/`mypy`
  commands across Python 3.10–3.13 (core job) plus a dedicated
  sibling-checkout job for the `agenticlens` extra, which is consistent with
  what was verified locally on Python 3.14.7.
- No PyPI publication, no production/live-provider chaos run, and no
  independent (non-source-review) validation of the `agenticlens` sibling
  repo's internals were performed — those integration claims are marked **U**
  or **P** above rather than **I**.

## Issues worth addressing

Source review surfaced the following, none of which this audit fixed:

1. **"LangGraph adapter" is overstated in three places** — the Release
   Status table, the shipped-module table, and the v0.2 deliverable
   checkbox all name a "LangGraph adapter," but `agents/langgraph.py` has no
   LangGraph-specific code, dependency, or test, and the CLI's own help text
   calls `--framework langgraph` "Currently informational." Corrected in
   `ROADMAP.md` (see diff) to describe `wrap_tool()`/`wrap_node()` as
   framework-agnostic helpers.
2. `src/agentic_chaos/models/agent_topology.py`'s docstring asserts that
   "AgenticLens's `AgentResilienceRecommender` reads this to produce
   resilience scores" as current fact; no such class exists in the
   `agenticlens` sibling checkout, and the roadmap itself correctly defers
   this to v0.9. Worth updating the docstring to match the roadmap's own
   framing.
3. `AGENTS.md`'s repo map still lists `src/agentic_chaos/drift/` as
   "Prompt/model drift detection (planned)," but drift shipped in `v0.4.0`
   (2026-08-15 per `CHANGELOG.md`) and is fully implemented. This is stale
   relative to both `CHANGELOG.md` and `ROADMAP.md`. Not corrected here
   because this audit's edit scope was `ROADMAP.md`/`ROADMAP_AUDIT.md` only.
4. ~~No reproducible instrumentation-overhead benchmark exists for the chaos
   injection path itself~~ — **addressed after this audit**:
   [`scripts/benchmark_overhead.py`](scripts/benchmark_overhead.py) now
   measures `chaos_call()`'s per-call overhead against a direct call, with
   results documented in [README.md](README.md#instrumentation-overhead).
   Measured on one machine (Windows, Python 3.14): +0.16 µs/call with no
   active session, +29.8 µs/call with a fault actively triggering (isolated
   using `SilentDegradationFault`, which adds no artificial delay of its
   own). Not a certified cross-platform benchmark — run it yourself via
   `make benchmark` to reproduce on your own hardware.

No other product fixes were made by this audit. All local evidence links in
this document resolve to files that exist in this repository at the audited
commit (verified by path).

## Recommended follow-through

1. Soften or scope the "LangGraph adapter" language everywhere it appears
   (`AGENTS.md`, `README.md`'s "Framework support" line) to match the
   `ROADMAP.md` correction made here, or build the LangGraph-specific
   integration the name implies.
2. Fix the stale "planned" drift entry in `AGENTS.md`'s repo map.
3. Update `models/agent_topology.py`'s docstring to stop asserting the
   `AgentResilienceRecommender` exists.
4. When the v0.2.x structured `ExperimentReport` work starts, keep it and
   the AIOS export narrative in the "Architecture" section from drifting
   further apart — right now the architecture section states an AIOS-export
   goal with no corresponding code anywhere in the package.
