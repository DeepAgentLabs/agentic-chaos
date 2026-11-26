# API Reference (detailed)

**Version:** 1.1.0

The Python API for `agentic-chaos`. The core is importable from `agentic_chaos` and
`agentic_chaos.chaos`; the optional AgenticLens bridge lives in
`agentic_chaos.integrations.agenticlens`.

The current checkout is package **1.1.0**. Capability guides retain the versions in which features shipped; draft artifact markers have independent versions. The [robust reference](https://deepagentlabs.io/agentic-chaos/docs/llms-full.md) includes current declared signatures from both distributed packages. Historical compatibility notes do not certify current deployments.

## Imports

```python
# Core
from agentic_chaos.chaos import (
    chaos_call, chaos_session,
    TokenTimeoutFault, RateLimitStormFault, SilentDegradationFault,
    TokenTimeoutError, RateLimitStormError,
)

# Top-level convenience exports (v0.2+)
from agentic_chaos import (
    chaos_call, chaos_session, fidelity_session,
    HeuristicJudge, SilentDegradationFault, ToolCallFailureFault,
    TopologyTracker, wrap_tool,
)

# Probes and the resilience score (v0.9)
from agentic_chaos import (
    chaos_run, HttpProbe, ResponseQualityProbe, LatencyProbe, FunctionProbe, Probe,
    compute_resilience, ResilienceScore, ResilienceHistory,
)

# Async/streaming calls, provider patches and profiles (v0.5)
from agentic_chaos import (
    chaos_acall, chaos_stream, chaos_astream,
    StreamCutFault, StreamHangFault, SlowTTFTFault, SlowChunksFault,
    AuthErrorFault, ContextLengthFault,
    patch_openai, patch_anthropic, patch_google, load_profile,
)

# Safety rails (0.5.2)
from agentic_chaos import CircuitBreaker, ChaosAbortedError

# Contracts (v0.6)
from agentic_chaos.contracts import (
    check_contracts, assert_contracts, parse_contract, describe_contracts,
    CompletesWithin, NoUnhandledError, MaxRetries, RecoveredAfterFailure,
    MaxCostImpact, NoRetryStorm, FullTopologyTraversal,
)

# Advanced chaos (v0.7)
from agentic_chaos import cascade, FaultCascade, find_breaking_point, PoisonedResponseFault
from agentic_chaos.chaos.estimate import estimate_failure

# Scope, workflows, experiments and fuzzing (v0.8)
from agentic_chaos import (
    Scope, ChaosWorkflow, Step, HealthCheck, Parallel, Suspend, Template,
    fuzz_topology, load_experiment, validate_experiment,
)

# ChaosHub and fault plugins (v0.11)
from agentic_chaos.hub import list_recipes, recipe, pull, remote_recipes, push
from agentic_chaos.hub.plugins import installed_plugins, load_plugins

# Optional integration (requires agentic-chaos[agenticlens])
from agentic_chaos.integrations.agenticlens import attach_events, step_kwargs
```

---

## Functions

### `chaos_call`

```python
chaos_call(fn, *args, faults=None, step_id=None, step_name=None, **kwargs)
```

Calls `fn(*args, **kwargs)`, injecting a fault when a `chaos_session` is active.

| Parameter | Description |
| --- | --- |
| `fn` | The callable to run |
| `*args`, `**kwargs` | Forwarded to `fn` |
| `faults` | List of fault names that apply at this call site. **Required** when the active session has more than one fault |
| `step_id`, `step_name` | Optional correlation recorded on the resulting `ChaosEvent` |

**Returns:** whatever `fn` returns (possibly corrupted by a fault such as
`silent_degradation`).
**Raises:** the fault's error type (for example `TokenTimeoutError`,
`RateLimitStormError`) when the fault is an error-raising one.

Outside a session, `chaos_call()` is a transparent pass-through.

### `chaos_session`

```python
with chaos_session(faults) as session:
    ...
```

Context manager that activates faults and collects events.

| Parameter | Description |
| --- | --- |
| `faults` | A list of fault names (`["token_timeout"]`) or fault instances (`[TokenTimeoutFault(hang_seconds=5.0)]`) |

**Yields:** a session object. `session.events` is the list of recorded `ChaosEvent`s.

### `fidelity_session`

```python
with fidelity_session(judge):
    ...
```

Context manager that scores events recorded inside it using `judge`. Each scored event
gets a `fidelity_score` between `0.0` and `1.0`. Nest a `chaos_session` inside it.

### `wrap_tool`

```python
wrap_tool(fn, *, tool_name=None, faults=None, tracker=None, caller_node=None)
```

*Module: `agentic_chaos.agents.langgraph` (also exported from `agentic_chaos` and
`agentic_chaos.agents`).*

Returns a wrapped version of a tool function. The wrapper participates in chaos
injection (for example `ToolCallFailureFault(tool_name=...)` matches on `tool_name`)
and records the caller-to-tool edge on the `TopologyTracker`.

### `wrap_node`

```python
wrap_node(fn, *, node_name=None, node_type="agent", faults=None, tracker=None, caller_node=None)
```

Same idea for node (agent) functions. Use it so handoff and agent faults can be applied
and the topology recorded. `caller_node` records the edge that `HandoffCorruptionFault`
targets.

### LangGraph adapter

`wrap_tool()` and `wrap_node()` live in `agentic_chaos.agents.langgraph`, the
LangGraph adapter. Wrap your plain Python functions before you register them as
LangGraph tools or graph nodes. The wrappers keep the original signature, so
LangGraph calls them as usual. LangGraph is **not** a dependency: the module
imports nothing from it, and the same wrappers work with any framework that calls
Python functions. `agentic-chaos agent run --framework langgraph` is an
informational hint only.

```python
from langgraph.graph import StateGraph
from agentic_chaos import TopologyTracker, wrap_node, wrap_tool

tracker = TopologyTracker()
search = wrap_tool(search_fn, tool_name="search", tracker=tracker, caller_node="planner")
graph = StateGraph(State)
graph.add_node("planner", wrap_node(planner_fn, node_name="planner", tracker=tracker))
graph.add_node("writer", wrap_node(writer_fn, node_name="writer", tracker=tracker,
                                   caller_node="planner"))
```

### `attach_events`

```python
attach_events(session, workflow)
```

*Module: `agentic_chaos.integrations.agenticlens`.* Merges the session's chaos events
onto an AgenticLens `Workflow`.

### `step_kwargs`

```python
step_kwargs(step)
```

*Module: `agentic_chaos.integrations.agenticlens`.* Returns the keyword arguments
(`step_id`, `step_name`) that correlate a `chaos_call()` with an AgenticLens step.
Use it as `chaos_call(fn, *args, **step_kwargs(s))`.

### `attach_drift_report`

```python
attach_drift_report(report, workflow)
```

*Module: `agentic_chaos.integrations.agenticlens`.* Attaches a drift report dict
(schema v1.4) onto an AgenticLens workflow-like object, so a future AgenticLens-side
`DriftRecommender` can inspect the drift findings without a hard package dependency.

---

## Fault classes

### LLM-level

| Class | CLI name | Key parameters |
| --- | --- | --- |
| `TokenTimeoutFault` | `token_timeout` | `hang_seconds=2.0`, `mode="raise"` (also `"delay"`) |
| `RateLimitStormFault` | `rate_limit_storm` | `burst_count=3`, `retry_after=1.0` |
| `SilentDegradationFault` | `silent_degradation` | `degrade_fn=None`, `seed=None` |

### Agent-level

| Class | CLI name | Key parameters |
| --- | --- | --- |
| `ToolCallFailureFault` | `tool_failure` | `tool_name=None`, `mode="error"` (also `"timeout"`, `"empty"`), `timeout_seconds=5.0`, `error_message="Tool execution failed"` |
| `MemoryCorruptionFault` | `memory_corruption` | `mode="garble"` (also `"truncate"`, `"inject"`, `"decay"`), `seed=None`, `rate=0.25` |
| `InfiniteLoopFault` | `infinite_loop` | `force_turns=5`, `continue_value=...` |
| `HandoffCorruptionFault` | `handoff_corruption` | `mode="corrupt"` (also `"drop"`, `"delay"`), `from_node=None`, `to_node=None`, `delay_seconds=1.0`, `seed=None` |

### Streaming and provider faults (v0.5)

Use streaming faults with `chaos_stream()` / `chaos_astream()` or a patched provider
stream. Provider faults raise SDK-shaped errors.

| Class | Name | Key parameters |
| --- | --- | --- |
| `StreamCutFault` | `stream_cut` | `after_chunks=1`: closes the stream after N chunks |
| `StreamHangFault` | `stream_hang` | `after_chunks=0`, `delay_seconds=1.0`: stalls, then raises `StreamHangError` |
| `SlowTTFTFault` | `slow_ttft` | `delay_seconds=1.0`: delays the first chunk |
| `SlowChunksFault` | `slow_chunks` | `delay_seconds=1.0`: delays every chunk |
| `AuthErrorFault` | `auth_error` | `status_code=401`: raises `AuthError` |
| `ContextLengthFault` | `context_length` | raises `ContextLengthError` |

### Response poisoning (v0.7)

| Class | Name | Key parameters |
| --- | --- | --- |
| `PoisonedResponseFault` | `poisoned_response` | `strategy="confident_wrong"` (also `"partial_hallucination"`, `"format_violation"`, `"prompt_injection"`, `"policy_bypass"`), `payload=None` |

Payloads are explicit synthetic text; embedded instructions are never dispatched.

### Options shared by every fault

Every built-in fault also accepts `probability=1.0`, `seed=None` and
`scope=None` (a [`Scope`](#scope-v08)). Scope is checked before probability sampling.

See [Configuration](configuration.md#fault-parameters) for what each parameter does.

---

## Exceptions

| Exception | Raised by | Notes |
| --- | --- | --- |
| `TokenTimeoutError` | `token_timeout` (default `mode="raise"`) | Raised after `hang_seconds` |
| `RateLimitStormError` | `rate_limit_storm` | Carries a `retry_after: float` attribute; raised for the first `burst_count` calls |
| `ToolCallFailureError` | `tool_failure` | Raised in `"error"` and `"timeout"` modes |
| `InfiniteLoopError` | `infinite_loop` | Raised when `raise_after` is enabled and the forced-turn budget is exhausted |
| `StreamHangError` | `stream_hang` | Raised after the stall |
| `AuthError` | `auth_error` | Carries `status_code` |
| `ContextLengthError` | `context_length` | Provider-style context overflow |
| `ChaosAbortedError` | `CircuitBreaker` | Raised for later instrumented calls once a safety limit trips |
| `ContractViolationError` | `assert_contracts()` | Carries the `ContractReport` |
| `ExperimentError` | `load_experiment()` | Carries located `ExperimentIssue`s |

---

## Judges

| Class | Description |
| --- | --- |
| `HeuristicJudge` | Zero-dependency judge shipped in-core |
| `DeepEvalJudge` | Adapter around an already-constructed DeepEval evaluator object |
| `PydanticEvalsJudge` | Adapter around an already-constructed pydantic-evals evaluator object |

---

## Data objects

### `ChaosEvent`

| Field | Description |
| --- | --- |
| `id` | UUID string auto-generated per event |
| `fault_type` | Fault name, such as `"token_timeout"` |
| `outcome` | What happened: `"errored"`, `"degraded"`, `"delayed"`, or `"looped"` |
| `step_id`, `step_name` | Correlation you provided at the call site |
| `timestamp` | UTC datetime when the event was recorded |
| `message` | Human-readable description of the outcome |
| `fidelity_score` | `0.0` to `1.0` when a judge scored the event, otherwise `None` |
| `edge_id` | ID of the topology edge, when the fault targets an edge |
| `from_node`, `to_node` | Source and destination node names for edge-scoped faults |
| `detail` | Dict of fault-specific metadata (e.g. `hang_seconds`, `burst_count`, `mode`) |

### `TopologyTracker`

| Member | Description |
| --- | --- |
| `register_node(name, type=...)` | Declare a node, for example `type="agent"` |
| `topology` | The recorded graph; `topology.as_json()` returns nodes and edges |

### `ChaosReport`

The package's standalone report format, shared in shape with AgenticLens's
`chaos_events` field (schema v1.1). See [Output Formats](output-formats.md).

New in 0.9.0: `probes` (a list of probe results, in run order) and `resilience`
(the score JSON), plus the read-only `resilience_score` property (an `int`, or
`None` when the score was not computed or is inconclusive).

## Async and streaming calls (v0.5)

See the [v0.5 guide](v0.5.md) for cancellation and stream closure.

| Name | Description |
| --- | --- |
| `chaos_acall(fn, *args, faults=None, step_id=None, step_name=None, chaos_provider=None, **kwargs)` | Async counterpart of `chaos_call()`; awaits `fn` and is cancellation-aware. |
| `chaos_stream(source, *, faults=None, step_id=None, step_name=None, chaos_provider=None)` | Wraps a sync iterator so streaming faults can cut, hang or slow it. Closes the source without reading ahead. |
| `chaos_astream(source, *, faults=None, step_id=None, step_name=None, chaos_provider=None)` | Async-iterator counterpart of `chaos_stream()`. |

`chaos_provider` labels a direct call for `Scope(providers=...)` matching.

## Provider patching and profiles (v0.5)

| Name | Description |
| --- | --- |
| `patch_openai(client, *, faults=None)` | Patches `chat.completions.create` and `responses.create` on one explicit OpenAI client instance (sync or async, including streams). Returns a `ProviderPatch`. |
| `patch_anthropic(client, *, faults=None)` | Patches `messages.create` (including `stream=True`) on one Anthropic client instance. |
| `patch_google(client, *, faults=None)` | Patches `models.generate_content`, `models.generate_content_stream` and the `client.aio.models` equivalents on one Google Gen AI client. |
| `ProviderPatch` | Patch handle. Originals are restored when the session exits; `close()` restores them earlier and is safe to repeat. Patched calls are labelled with their provider automatically. |
| `load_profile(name, path="chaos.toml")` | Loads a named TOML profile and returns fresh fault instances. A `parameters.NAME.scope` table sets each fault's scope. |

```python
from agentic_chaos import chaos_session, patch_openai

with chaos_session(["rate_limit_storm"]):
    patch_openai(client)
    client.chat.completions.create(...)
# Original methods are restored when the session exits, even on error.
```

A patch needs an active session. With several faults configured, select one with
`faults=[...]`. Only the client object you pass is patched.

## Safety rails (0.5.2)

See the [safety guide](safety.md).

| Name | Description |
| --- | --- |
| `CircuitBreaker(*, max_cost_usd=None, max_failure_rate=None, window_size=20, min_calls=1, max_duration_seconds=None, max_injections=None)` | Limits for one session. When a limit trips, the session aborts and later instrumented calls raise `ChaosAbortedError`. |
| `chaos_session(faults, *, breaker=None, dry_run=False)` | `dry_run=True` records which faults would fire without injecting them. Target calls still run, so they can still cost money. |
| `session.record_cost(cost_usd)` | Records a cost you measured. May raise `ChaosAbortedError`. |
| `session.record_usage(*, input_tokens, output_tokens, input_usd_per_million, output_usd_per_million)` | Records token usage at prices you supply; prices are never inferred. |

The cost limit only sees cost you record explicitly.

## Contracts (v0.6)

*Module: `agentic_chaos.contracts`.* See [contract definitions and evidence requirements](v0.6.md#contracts).

| Name | Description |
| --- | --- |
| `check_contracts(report, contracts, *, baseline=None)` | Returns a `ContractReport`. `report` may be a `ChaosReport`, a dict or a JSON path. |
| `assert_contracts(report, contracts, *, baseline=None)` | Same, but raises `ContractViolationError` unless every contract passes. |
| `parse_contract(spec)` | Builds a built-in contract from a CLI spec such as `max_retries:3` or `max_retries:n=3,step=llm`. |
| `describe_contracts()` | Lists the built-ins and their parameters (what `contracts list` prints). |
| `Contract` | Base class for your own contracts: set `name`, implement `check(report, baseline)` and return `self.result(...)`. |
| `ContractResult` | `contract`, `status` (`passed`, `failed` or `inconclusive`), `message`, `parameters`, `observed`. |
| `ContractReport` | `results`, `passed`, `failures()`, `summary()`, `as_json()`, `raise_for_failures()`. |

### Built-in contracts

| Class | CLI spec | Passes when |
| --- | --- | --- |
| `CompletesWithin(timeout_s)` | `completes_within:30` | The run finished within `timeout_s` seconds |
| `NoUnhandledError()` | `no_unhandled_error` | No exception escaped the run |
| `MaxRetries(n, *, step=None)` | `max_retries:3` | No step (or the named step) retried more than `n` times in a row |
| `RecoveredAfterFailure(*, require_step_success=False)` | `recovered_after_failure` | Every injected failure was followed by recovery |
| `MaxCostImpact(factor, *, metric="cost_usd", baseline_value=None)` | `max_cost_impact:1.5` | Cost (or another metric) stayed within `factor` × the baseline |
| `NoRetryStorm(max_retries_per_window, *, window_seconds=60.0)` | `no_retry_storm:10` | Retries stayed under the limit in every window |
| `FullTopologyTraversal(*, expected_nodes=None, ignore=())` | `full_topology_traversal` | Every expected (or baseline) node was still visited |

Missing evidence makes a contract `inconclusive`, and an inconclusive contract never passes.

## Pytest plugin (v0.6)

*Package: `pytest_agentic_chaos`, loaded automatically through the `pytest11` entry point.*
Install `agentic-chaos[pytest]`.

| Item | Description |
| --- | --- |
| `@pytest.mark.chaos(...)` | Marker arguments: `faults`, `profile`, `profile_file`, `contracts`, `must_recover`, `baseline`, `breaker`, `dry_run`, `probes`, `min_score`. Markers do nothing unless chaos is enabled. |
| `chaos` fixture | Gives the test its live chaos session, for recording usage and topology. |
| `--chaos` | Enables markers for this run. The `chaos = true` ini option enables them by default. |
| `--chaos-contract SPEC` | Adds a contract to every marked test (repeatable). |
| `--chaos-report-dir DIR` | Saves each marked test's report as JSON. |

## Advanced chaos (v0.7)

See the [v0.7 guide](v0.7.md).

| Name | Description |
| --- | --- |
| `cascade(*, first, then, delay_between=0, scope=None)` | Returns a `FaultCascade`: `first` fires, then `then` fires on a later call after `delay_between` seconds. Events record cascade provenance. |
| `find_breaking_point(app, *, fault, param, range, recovered=None, fault_kwargs=None)` | Runs `app` once per value of `param` across the inclusive `range` and returns a `BreakingPointResult` (`breaking_point`, `trials`, `assumption`). It assumes recovery is deterministic and monotonic. |
| `estimate_failure(*, fault, retries, calls=1, cost_per_call_usd)` | *Module: `agentic_chaos.chaos.estimate`.* Returns a `FailureEstimate` (`baseline_usd`, `extra_usd`, `total_usd`) without running any code. CLI: `agentic-chaos estimate`. |

```python
from agentic_chaos import RateLimitStormFault, TokenTimeoutFault, cascade, find_breaking_point

storm_then_hang = cascade(first=RateLimitStormFault(burst_count=2),
                          then=TokenTimeoutFault(hang_seconds=0), delay_between=0.5)
result = find_breaking_point(my_app, fault=RateLimitStormFault, param="burst_count", range=(1, 8))
print(result.breaking_point)
```

## Scope (v0.8)

```python
Scope(*, steps=None, providers=None, exclude_steps=None, exclude_providers=None)
```

Limits where a fault may fire. Exclusions always win. An include list never matches
a call that has no step or provider label. Methods: `allows(*, step_name=None, provider=None)`,
`intersect(other)`, `as_json()`, `from_json()`. Pass it as `scope=` to any fault,
`cascade()`, `Step` or `ChaosWorkflow`.

## Chaos workflows (v0.8)

*Module: `agentic_chaos.workflows`.* See [node semantics, approvals, reports and statuses](v0.8.md#chaos-workflows).

| Name | Description |
| --- | --- |
| `ChaosWorkflow(name, steps, *, target=None, stop_on_failure=True, breaker=None, scope=None, probes=(), weights=None)` | A multi-stage campaign. |
| `.run(target=None, *, dry_run=False, approve=None, resume_from=None, experiment=None, baseline=None, history=None)` | Runs the stages and returns a `WorkflowReport`. Chaos outcomes never raise. `resume_from="gate"` re-runs the definition starting after that approved `Suspend` gate. |
| `Step(name, faults=(), target=None, repeat=1, contracts=(), breaker=None, dry_run=False, scope=None)` | A fault stage with its own contracts, breaker and scope. |
| `HealthCheck(fn=None, query=..., name=None, expect_success=True, expect_contains=None, expect=None, retries=0, retry_delay_seconds=0.0, halt_on_failure=True)` | A steady-state gate between stages. |
| `Parallel(*branches, name=None, max_workers=None)` | Runs branches concurrently, each in its own chaos session. |
| `Suspend(name, reason="", approve=None)` | A human approval gate. An unapproved gate stops the run (CLI exit code `3`). |
| `Template(name, build, **defaults)` and `.use(*, name=None, **params)` | Reusable, parameterized stages. |
| `WorkflowReport` | Stage results, events, contracts, probes and `resilience_score`; `.save(path)`. |

## Declarative experiments (v0.8)

*Module: `agentic_chaos.experiments`.* JSON and TOML need no extras; YAML needs
`agentic-chaos[yaml]`. See [declarative experiments](v0.8.md#declarative-experiments).

| Name | Description |
| --- | --- |
| `validate_experiment(source, *, base_dir=None, check_targets=True)` | Lints a file, dict or path without running targets. Returns a `ValidationResult` (`ok`, `errors`, `warnings`, located `ExperimentIssue`s). |
| `load_experiment(source, *, base_dir=None, check_targets=True)` | Compiles a document into an `Experiment` (`workflow`, `schedule`, `min_score`, `history`, `.run()`). Raises `ExperimentError`. |
| `parse_cron(expression)` | Returns a `CronSchedule` with `matches()` and `next_runs()`. |

## Topology fuzzing (v0.8)

```python
fuzz_topology(target, *, n=20, topology=None, faults=None, scope=None, seed=0,
              recovered=None, contracts=(), breaker=None)
```

Discovers the agent graph, places one seeded fault per trial (weighted by node fan-out),
and returns a `FuzzReport` (`trials`, `nodes`, `failures()`, `failing_nodes()`, `save()`).
Trials whose node was never reached are reported as unreached, not as passes.
CLI: `agentic-chaos agent fuzz`.

## Drift detection (v0.4)

*Module: `agentic_chaos.drift`.* See [the drift report format](output-formats.md#drift-report-and-state).

| Name | Description |
| --- | --- |
| `DriftSnapshot` | Prompt, model, model fingerprint, output and retrieval baseline. `save_snapshot()` / `load_snapshot()`. |
| `compare_snapshots(baseline, current, *, output_distance_threshold=0.18, retrieval_distance_threshold=0.4)` | Returns a `DriftReport` with `DriftFinding`s. |
| `should_emit_report(report, state, *, cooldown_minutes, emit_only_on_change=True)` / `update_alert_state(report)` | Alert emission controls backed by `DriftAlertState`. |

## ChaosHub and fault plugins (v0.11)

See [recipe identities, pinned exchange and plugin packaging](v0.11.md).

| Name | Description |
| --- | --- |
| `list_recipes(query="")` | Lists bundled recipes, optionally filtered. |
| `recipe(name)` | Returns one bundled recipe document. |
| `pull(name, destination, *, repository=None, ref=None)` | Writes a bundled recipe to a file without overwriting, or a remote recipe when `repository` and a full commit SHA `ref` are given. Downloading never executes code. |
| `remote_recipes(repository, ref, query="")` | Lists recipes in a remote registry at a pinned commit. |
| `push(source, checkout)` | Stages a recipe in a local registry checkout; it does not publish. |
| `installed_plugins()` | *Module: `agentic_chaos.hub.plugins`.* Lists fault plugins in the `agentic_chaos.plugins` entry-point group without importing them. |
| `load_plugins()` | Imports and registers trusted plugin faults. It validates names and constructors and rejects collisions before changing the registry. |

Bundled recipes: `api-cascade-storm`, `multi-agent-coordinator-down`,
`rag-context-poisoning`, `rag-retriever-failure`, `react-loop-resilience`,
`support-escalation-failure`.

## Probes and resilience (v0.9)

See the [v0.9 guide](v0.9.md) for the lifecycle and the scoring method.

| Name | Description |
| --- | --- |
| `chaos_run(target, faults, *, probes=(), name=None, repeat=1, breaker=None, dry_run=False, baseline=None, weights=None, history=None, require_steady_state=True)` | One chaos run with the pre/during/post probe lifecycle. Returns a scored `ChaosReport`; never raises for the target's exceptions. |
| `HttpProbe(url, *, expect_status=200, method="GET", expect_contains=None, headers=None, body=None, timeout_seconds=5.0, ...)` | Checks an HTTP(S) endpoint with the standard library. |
| `ResponseQualityProbe(fn, query, *, expect_contains=None, expect_not_contains=None, expect_regex=None, expect=None, reference=None, min_similarity=None, judge=None, ...)` | Checks an answer's content and, with a reference, its similarity. |
| `LatencyProbe(fn, query, *, max_ms, samples=1, statistic="max", ...)` | Checks response time. |
| `FunctionProbe(fn, query=..., *, expect=None, ...)` | Passes when the call returns (and `expect` accepts it). |
| `Probe` | Base class: implement `evaluate() -> (message, observed)`, raise when unhealthy. Common options: `name`, `phases`, `retries`, `retry_delay_seconds`, `weight`. |
| `run_probes(probes, phase, *, step=None)` | Run the probes configured for one phase; returns `ProbeResult`s. |
| `compute_resilience(report, *, baseline=None, weights=None, latency_tolerance=2.0, cost_tolerance=1.0)` | Score a report, its dict or a JSON path. Returns a `ResilienceScore`. |
| `ResilienceScore` | `score`, `status`, `grade`, `components`, `faults`, `reasons`, `trend`; `meets(n)`, `component(name)`, `summary()`, `as_json()`, `from_json()`. |
| `ResilienceHistory(path, *, max_runs=None, max_age_days=None)` | Local trend store: `record(score)`, `trend(name, score)`, `latest(name)`, `entries(name)`, `prune()`. |
| `ChaosWorkflow(..., probes=(), weights=None)` and `.run(..., baseline=None, history=None)` | Workflow-level probes and scoring; `WorkflowReport.resilience_score`. |


## Authenticated containment assertions (0.10.0)

Install `agentic-chaos[containment]` for the Lens adapter.
`agentic_chaos.containment.assert_contained(records, manifest=..., trusted_keys=...,
expected_stream_id=..., acknowledgement_id=..., subject=..., task_id=...,
attempted_call_ids=...)` verifies one detached ordered JSON snapshot before
checking required attempts, acknowledgements and forbidden dispatch reservations.
The host supplies trusted keys and expected scope; they never come from evidence.
Operational kinds are `dispatched`, `completed`, `denied`,
`stop_acknowledged` and `revocation_acknowledged`; `scenario` carries metadata.
Each operational row requires subject/task scope; dispatch/completion/denial also
require a nonempty call correlation. Native producer records must be normalized
explicitly; the API does not guess that a verdict or native event was a dispatch.
Unknown kinds, malformed records, orphan completions and failed/unknown/incomplete
Lens verification raise. Coverage remains producer-declared.
See [the guide](phase6-containment.md) and `examples/containment_demo.py`.


## Capability modules

| Module | Detailed workflow and public contract |
| --- | --- |
| `agentic_chaos.chaos` | [Sessions, call faults and event capture](features.md) |
| `chaos.async_call`, `chaos.streaming` | [Async/stream execution, cancellation and closure](v0.5.md) |
| `integrations.providers`, `chaos.provider_faults`, `chaos.profiles` | [Explicit client patches, provider failures, seeds and TOML profiles](v0.5.md) |
| `agentic_chaos.agents` | [Tool/node wrappers, topology and agent faults](features.md) |
| `agentic_chaos.safety` | [CircuitBreaker, accounting, abort and dry runs](safety.md) |
| `agentic_chaos.judges` | [Fidelity judges and adapter requirements](features.md#fidelity-judges) |
| `agentic_chaos.drift` | [Snapshot, comparison and emission-state formats](output-formats.md#drift-report-and-state) |
| `agentic_chaos.contracts` | [Seven built-ins, parsing, check/assert and inconclusive evidence](v0.6.md) |
| `pytest_agentic_chaos.plugin` | [Markers, fixture, options, baseline and async support](v0.6.md) |
| `chaos.advanced`, `chaos.poisoning`, `chaos.estimate` | [Cascades, breaking points, synthetic strategies and budget estimates](v0.7.md) |
| `chaos.scope`, `agentic_chaos.workflows`, `agentic_chaos.experiments` | [Scope predicates, workflow nodes, fuzzing, compiler, target loading and schedules](v0.8.md) |
| `agentic_chaos.probes`, `agentic_chaos.resilience` | [Probe lifecycle, scores, trend/retention and gates](v0.9.md) |
| `agentic_chaos.containment` | [Authenticated stop/revocation assertions](phase6-containment.md) |
| `agentic_chaos.hub`, `hub.plugins` | [Recipes, pinned exchange and explicit plugin loading](v0.11.md) |
| `agentic_chaos.export.aios`, `integrations.agenticlens` | [Native exports and Lens correlation](integrations.md) |

Names beginning `chaos.`, `integrations.` or `hub.` in this table are relative to `agentic_chaos`. The root `__all__` is a convenience surface, not the entire package capability set. Undocumented helpers remain internal even when source declarations are included for lookup.

## Native report serialization and AIOS export

`session.to_report(name, *, end_time=None, error=None, agent_topology=None)` builds a native `ChaosReport`. Pass an escaped exception as `error` when constructing it yourself. Unlike `WorkflowReport`, `ChaosReport` does not have `.save()`; use its Pydantic serialization:

```python
from pathlib import Path
from agentic_chaos import chaos_session
from agentic_chaos.export import to_aios_run
import json

with chaos_session([]) as session:
    pass
report = session.to_report("offline")
Path("report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
aios = to_aios_run(report, status="completed", producer_version="1.1.0")
Path("aios-run.json").write_text(json.dumps(aios, indent=2), encoding="utf-8")
```

`to_aios_run(report, *, status="completed", workflow_id=None, producer_version=None)` returns a `0.4-draft` Run dict, preserving producer-local evidence under extensions. The caller supplies observed run status; an aborted report maps to `cancelled`. It is an export mapping, not a claim of independent schema/semantic acceptance. See the [export mapping](output-formats.md#aios-run-export).
