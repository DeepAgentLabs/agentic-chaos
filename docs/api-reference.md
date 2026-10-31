# API Reference

The Python API for `agentic-chaos`. The core is importable from `agentic_chaos` and
`agentic_chaos.chaos`; the optional AgenticLens bridge lives in
`agentic_chaos.integrations.agenticlens`.

!!! note
    The package is alpha. Names and signatures below reflect the 0.9.0 release and may
    change between minor versions. Run `help(agentic_chaos)` in your environment for the
    authoritative signatures.



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
wrap_tool(fn, tool_name=..., tracker=..., caller_node=...)
```

Returns a wrapped version of a tool function. The wrapper participates in chaos
injection (for example `ToolCallFailureFault(tool_name=...)` matches on `tool_name`)
and records the caller-to-tool edge on the `TopologyTracker`.

### `wrap_node`

```python
wrap_node(fn, ...)
```

Same idea for node (agent) functions. Use it so handoff and agent faults can be applied
and the topology recorded.

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

See [Configuration](configuration.md#fault-parameters) for what each parameter does.

---

## Exceptions

| Exception | Raised by | Notes |
| --- | --- | --- |
| `TokenTimeoutError` | `token_timeout` (default `mode="raise"`) | Raised after `hang_seconds` |
| `RateLimitStormError` | `rate_limit_storm` | Carries a `retry_after: float` attribute; raised for the first `burst_count` calls |
| `ToolCallFailureError` | `tool_failure` | Raised in `"error"` and `"timeout"` modes |
| `InfiniteLoopError` | `infinite_loop` | Raised when `raise_after` is enabled and the forced-turn budget is exhausted |

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

