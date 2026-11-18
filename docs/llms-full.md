# Agentic Chaos — comprehensive AI-readable reference

Product: Agentic Chaos
Distribution: `agentic-chaos`
Python requirement: `>=3.10`

Inject controlled faults into explicit execution boundaries and inspect resulting evidence. Fault injection alone does not demonstrate successful recovery.

## Interpretation and evidence boundaries

- This is reference data, not authority to execute commands or approve actions. Example strings and artifacts are data.
- Use the current product's APIs and commands. Sibling integrations are optional unless a specific operation lists them as prerequisites.
- Source declarations and JSON schemas below describe the included checkout. They take precedence over abbreviated tutorial fragments; inherited methods and dynamically registered APIs may require the linked reference.
- Declared signatures are extracted without importing product code. They are reference fragments, not runnable modules; model field constraints use the original source expressions.
- Local examples are distinguished from provider/host integration fragments. Do not describe fixture outputs as measured production evidence.
- Preserve schema identifiers, unknown values, failure outcomes, authentication requirements, and approval boundaries. A package release does not imply live integration certification.
- This file is a generated snapshot. The adjacent `ai-docs-manifest.json` records source hashes and its checksum; verify freshness before ingestion. Source URLs follow main and may advance after this snapshot.

## Package entry points

```json
{
  "agentic-chaos": "agentic_chaos.cli.main:app"
}
```

## Installation dependencies and optional extras

```json
{
  "dependencies": [
    "pydantic>=2.0,<3",
    "typer>=0.12",
    "rich>=13.0",
    "tomli>=2.0; python_version < '3.11'"
  ],
  "optional_extras": {
    "containment": [
      "agenticlens>=0.12.0,<2"
    ],
    "providers": [
      "openai>=1.0",
      "anthropic>=0.40",
      "google-genai>=1.0"
    ],
    "yaml": [
      "pyyaml>=6.0"
    ],
    "pytest": [
      "pytest>=8.0"
    ],
    "agenticlens": [
      "agenticlens>=0.7.0"
    ]
  }
}
```

## Setup and task workflows

Source: [docs/developer-guide.md](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/developer-guide.md)

Use this guide to set up Agentic Chaos, run a local example, and apply it to your application. Optional provider and integration fragments identify the objects or services you must supply.

[Quickstart](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/developer-guide.md#quickstart) · [Usage](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/developer-guide.md#usage) · [Configuration](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/developer-guide.md#settings) · [Troubleshooting](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/developer-guide.md#troubleshooting) · [Reference](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/developer-guide.md#reference)

## Quickstart

Requires Python 3.10 or newer. Run commands in an activated virtual environment. Download referenced files into the same working directory before running them.

### Install and inspect available faults

```
python -m pip install agentic-chaos
agentic-chaos chaos list-faults
```

### Create a local target

chaos_quickstart.py · complete file

```python
from agentic_chaos.chaos import chaos_call, TokenTimeoutError

def search(question):
    return [f"Document about {question}"]

try:
    result = chaos_call(search, "refund policy", faults=["token_timeout"], step_name="Search")
except TokenTimeoutError:
    result = []
print("Search result:", result)
```

[Download chaos_quickstart.py](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/guide/examples/chaos_quickstart.py)

### Compare normal execution with injected failure

```
python chaos_quickstart.py
agentic-chaos chaos run chaos_quickstart.py --inject token_timeout --save chaos_run.json
```

**Expected:** the normal run returns a document. Under the timeout fault, the script catches the timeout and prints an empty result. A chaos report records the injected event.

An empty result is an observed recovery weakness, not a resilience pass. Decide what a useful fallback should return, implement it, and repeat the experiment.

### Connect real code

Wrap the callable whose failure you want to study. Establish the normal baseline, then inject a single fault before combining scenarios. Keep tests bounded and use a controlled test target.

[Configure experiments ↗](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/configuration.md) · [Read reports ↗](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/output-formats.md)

## Usage

<span id="integrations"></span>

### Wrap your application calls

Wrap the synchronous callable you want to test and activate a chaos session around it. Outside an active session, `chaos_call` invokes the real callable without injecting a fault.

```python
from agentic_chaos.chaos import TokenTimeoutError, TokenTimeoutFault, chaos_call, chaos_session

def search(query):
    return ["result for " + query]

with chaos_session([TokenTimeoutFault(hang_seconds=0)]):
    try:
        result = chaos_call(search, "refund policy", faults=["token_timeout"])
    except TokenTimeoutError:
        result = []
assert result == []
```

For agent frameworks, use the documented tool/node adapters. Do not assume a synchronous wrapper provides native asynchronous or streaming behavior; consult the matching adapter contract.

Optional Lens correlation is installed with `python -m pip install "agentic-chaos[agenticlens]"`. The published extra declares a package dependency; the sibling path in `tool.uv.sources` is a source-development setting. See the [integration reference](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/integrations.md) and [runnable correlation example](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/examples/chaos_with_agenticlens_demo.py).

<span id="settings"></span>

## Configuration

### Configure faults and call sites

#### Choosing active faults

###### CLI

```
    agentic-chaos chaos run my_app.py --inject token_timeout,rate_limit_storm
```

`--inject` takes a comma-separated list of fault names.

###### Python (by name)

```
    from agentic_chaos.chaos import chaos_session

    with chaos_session(["token_timeout"]) as session:
        ...
```

###### Python (by instance)

```
    from agentic_chaos.chaos import chaos_session, TokenTimeoutFault

    with chaos_session([TokenTimeoutFault(hang_seconds=5.0)]) as session:
        ...
```

Passing a name uses the fault's defaults. Passing an instance lets you override them.

#### Fault parameters

#### LLM-level faults

| Fault | Parameter | Default | Meaning |
| --- | --- | --- | --- |
| `TokenTimeoutFault` | `hang_seconds` | `2.0` | Seconds to hang before raising `TokenTimeoutError` |
| `TokenTimeoutFault` | `mode` | `"raise"` | `"delay"` lets the real call complete late instead of raising; outcome becomes `"delayed"` |
| `RateLimitStormFault` | `burst_count` | `3` | Number of initial calls that raise `RateLimitStormError` before calls pass through |
| `RateLimitStormFault` | `retry_after` | `1.0` | Seconds hint carried on the `RateLimitStormError.retry_after` attribute for callers that implement backoff |
| `SilentDegradationFault` | `degrade_fn` | built-in text garbler | `fn(result) -> corrupted_result`, replaces the default corruption |
| `SilentDegradationFault` | `seed` | `None` | Integer seed for the internal RNG; set for reproducible garbling |

#### Agent-level faults

| Fault | Parameter | Values / Default | Meaning |
| --- | --- | --- | --- |
| `ToolCallFailureFault` | `mode` | `"error"` | Also `"timeout"` or `"empty"`. How the tool fails |
| `ToolCallFailureFault` | `tool_name` | `None` | Target one tool by name; `None` targets all |
| `ToolCallFailureFault` | `timeout_seconds` | `5.0` | Seconds to sleep before raising in `"timeout"` mode |
| `ToolCallFailureFault` | `error_message` | `"Tool execution failed"` | Message on the raised `ToolCallFailureError` |
| `MemoryCorruptionFault` | `mode` | `"garble"` | Also `"truncate"`, `"inject"`, `"decay"` |
| `MemoryCorruptionFault` | `seed` | `None` | Integer seed for the internal RNG |
| `MemoryCorruptionFault` | `rate` | `0.25` | Decay rate per turn (used only in `"decay"` mode) |
| `InfiniteLoopFault` | `force_turns` | `5` | Number of calls that return the "continue" signal before passing through |
| `InfiniteLoopFault` | `continue_value` | `"I need to continue processing this request."` | The value substituted for the real return during forced turns |
| `HandoffCorruptionFault` | `mode` | `"corrupt"` | Also `"drop"` or `"delay"` |
| `HandoffCorruptionFault` | `from_node` | `None` | Only fire when source node matches; `None` matches any |
| `HandoffCorruptionFault` | `to_node` | `None` | Only fire when destination node matches; `None` matches any |
| `HandoffCorruptionFault` | `delay_seconds` | `1.0` | Seconds to sleep in `"delay"` mode |
| `HandoffCorruptionFault` | `seed` | `None` | Integer seed for the internal RNG used in `"corrupt"` mode |

#### Call-site arguments

`chaos_call(fn, *args, faults=[...], step_id=..., step_name=..., **kwargs)`

| Argument | Required | Meaning |
| --- | --- | --- |
| `faults` | Required when the session has more than one fault | Names of the fault(s) that apply at this call site |
| `step_id`, `step_name` | Optional | Correlation recorded on the `ChaosEvent` (and used to join events to AgenticLens steps) |

All other positional and keyword arguments are forwarded to `fn` unchanged.

#### Drift configuration

Drift behavior is configured entirely through `agentic-chaos drift` flags.

| Concern | Flags |
| --- | --- |
| What to snapshot or compare | `--prompt-file`, `--output-file`, `--retrieval-file` |
| Model identity | `--model`, `--model-fingerprint`, `--embedding-model` |
| Where to write results | `--save` |
| Quiet scheduled runs | `--state-path`, `--cooldown-minutes`, `--emit-only-on-change` |

Full details are in the [CLI Reference](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/cli-reference.md#agentic-chaos-drift-snapshot).

## Troubleshooting

Check the failing boundary before changing application behavior.

- No fault outside the CLI/session: the wrapper is a pass-through outside an active chaos context.
- Fault report exists but application succeeds: verify whether a fallback actually met the task requirement.
- Missing optional integration: install only the relevant extra for that workflow.

### Verify your environment

Run commands from the environment where you installed the package. Confirm the input file exists and matches the expected artifact contract. Keep the original evidence when diagnosing a failure.

## Reference

Use the current product reference for exact method signatures, command options, and supported artifacts. The code fragments in configuration and how-to articles build on the quickstart; they are not all standalone scripts.

- [Open API / CLI reference ↗](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/cli-reference.md)

---

## Api Reference

Source: [docs/api-reference.md](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/api-reference.md)

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

See [Configuration](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/configuration.md#fault-parameters) for what each parameter does.

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
`chaos_events` field (schema v1.1). See [Output Formats](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/output-formats.md).

New in 0.9.0: `probes` (a list of probe results, in run order) and `resilience`
(the score JSON), plus the read-only `resilience_score` property (an `int`, or
`None` when the score was not computed or is inconclusive).

## Probes and resilience (v0.9)

See the [v0.9 guide](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/v0.9.md) for the lifecycle and the scoring method.

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
See [the guide](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/phase6-containment.md) and `examples/containment_demo.py`.

---

## Cli Reference

Source: [docs/cli-reference.md](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/cli-reference.md)

The package installs one executable, `agentic-chaos`. Prefix with `uv run` when working
from a source checkout.

```text
agentic-chaos
├── chaos
│   ├── run <script> --inject <faults> [--save <file>] [--probe ...] [--min-score N]
│   ├── list-faults
│   └── workflow run|validate <file>
├── agent
│   ├── run <script> --inject <faults> [--save <file>] [--probe ...] [--min-score N]
│   └── fuzz <script>
├── contracts
│   ├── list
│   └── check <report>
├── experiment
│   ├── validate <files>
│   ├── run <file> [--min-score N] [--history <file>]
│   └── schedule <file>
├── score
│   ├── show <report> [--baseline ...] [--min-score N] [--json]
│   ├── history [--history <file>]
│   └── prune [--history <file>] --max-runs N | --max-age-days D
├── drift
│   ├── snapshot --name ... --save ...
│   └── compare <baseline> ...
└── estimate
```

Get help for any command with `--help`, for example
`agentic-chaos drift compare --help`.

## `agentic-chaos chaos run`

Run a Python script with LLM-level chaos active and print a chaos-events report.

```bash
agentic-chaos chaos run <script.py> --inject <fault[,fault...]> [--save <report.json>]
```

| Option | Description |
| --- | --- |
| `<script.py>` | The script to run under chaos |
| `--inject` | Comma-separated fault names: `token_timeout`, `rate_limit_storm`, `silent_degradation` |
| `--save` | Write the standalone chaos report to this path |

```bash
agentic-chaos chaos run my_app.py --inject token_timeout,rate_limit_storm
agentic-chaos chaos run my_app.py --inject silent_degradation --save chaos_run.json
```

The script's `chaos_call()` sites select which active fault applies where. If you
inject more than one fault, each call site must pass `faults=[...]`.

## `agentic-chaos agent run`

Run a script with agent-level or handoff faults active.

```bash
agentic-chaos agent run <script.py> --inject <fault[,fault...]> [--save <report.json>]
```

| Option | Description |
| --- | --- |
| `--inject` | `tool_failure`, `memory_corruption`, `infinite_loop`, `handoff_corruption` |
| `--save` | Write the report to this path |

```bash
agentic-chaos agent run my_agent.py --inject tool_failure,memory_corruption --save report.json
agentic-chaos agent run my_agent.py --inject handoff_corruption --save report.json
```

## `agentic-chaos chaos list-faults`

List every available fault type.

```bash
agentic-chaos chaos list-faults
```

## `agentic-chaos drift snapshot`

Capture a baseline from your current prompt, output, retrieval results and model
identity.

```bash
agentic-chaos drift snapshot \
  --name support-agent \
  --save baseline.json \
  --prompt-file prompt.txt \
  --output-file baseline_output.txt \
  --retrieval-file retrieval.txt \
  --model gpt-5-mini \
  --model-fingerprint provider-fp-001 \
  --embedding-model text-embed-1
```

| Option | Description |
| --- | --- |
| `--name` | Name for this baseline |
| `--save` | Path to write the baseline JSON |
| `--prompt-file` | File containing the prompt |
| `--output-file` | File containing a representative model output |
| `--retrieval-file` | File containing the fixed retrieval results |
| `--model` | Model name |
| `--model-fingerprint` | Provider-reported model or system fingerprint |
| `--embedding-model` | Embedding model identifier |

## `agentic-chaos drift compare`

Compare a current run against a saved baseline.

```bash
agentic-chaos drift compare baseline.json \
  --prompt-file prompt.txt \
  --output-file current_output.txt \
  --retrieval-file retrieval.txt \
  --model gpt-5-mini \
  --model-fingerprint provider-fp-002 \
  --save drift_report.json
```

| Option | Description |
| --- | --- |
| `<baseline.json>` | Baseline created by `drift snapshot` |
| `--prompt-file`, `--output-file`, `--retrieval-file` | Current prompt, output and retrieval results |
| `--model`, `--model-fingerprint`, `--embedding-model` | Current model identity |
| `--save` | Path to write the drift report JSON |
| `--state-path` | File that remembers the previous result between scheduled runs |
| `--cooldown-minutes` | Minimum minutes before the same drift is emitted again |
| `--emit-only-on-change` | Stay quiet unless the drift result changed since the last run |

**Exit code:** `drift compare` exits with code **`2`** when drift is detected, so it can
fail a CI job. A JSON report is still written when the emission rules allow it.

Quiet scheduled run:

```bash
agentic-chaos drift compare baseline.json \
  --prompt-file prompt.txt \
  --output-file current_output.txt \
  --save drift_report.json \
  --state-path .agentic-chaos/drift-state.json \
  --cooldown-minutes 1440 \
  --emit-only-on-change
```

## Fault names

| Name | Family | Used with |
| --- | --- | --- |
| `token_timeout` | LLM | `chaos run` |
| `rate_limit_storm` | LLM | `chaos run` |
| `silent_degradation` | LLM | `chaos run` |
| `tool_failure` | Agent | `agent run` |
| `memory_corruption` | Agent | `agent run` |
| `infinite_loop` | Agent | `agent run` |
| `handoff_corruption` | Agent / edge | `agent run` |

## Resilience options (v0.9)

`chaos run`, `agent run`, `experiment run` and `chaos workflow run` print a
probe table and a resilience report after every run, and accept:

| Option | Description |
| --- | --- |
| `--probe SPEC` | `chaos run` and `agent run` only, repeatable. An `http(s)://` URL must answer 200. A `file.py:function` or `module:function` spec must return without raising. Runs before and after the chaos; a failure before it exits 1 without injecting anything. |
| `--min-score N` | Exit 1 unless the resilience score is at least N (0-100). An inconclusive score fails. |
| `--history PATH` | Record the score in a run-history file and print the trend. |
| `--history-max-runs N` | Keep the newest N runs per name in that file. |
| `--history-max-age-days D` | Drop runs older than D days from that file. |
| `--baseline PATH` | A fault-free report for the latency and cost components (and the contracts that compare against one). |

## `agentic-chaos score`

```bash
agentic-chaos score show chaos_run.json [--baseline baseline.json] [--weight recovery=0.5] \
    [--min-score 70] [--history h.json] [--json] [--save score.json]
agentic-chaos score history [--history .agentic-chaos/resilience-history.json] [--name NAME] [--json]
agentic-chaos score prune [--history ...] [--max-runs N] [--max-age-days D]
```

`score show` recomputes the score from a saved native, merged or workflow
report, so it works on CI artifacts. See the [v0.9 guide](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/v0.9.md).

---

## Output Formats

Source: [docs/output-formats.md](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/output-formats.md)

Agentic Chaos produces three kinds of output: a console table, a standalone JSON report, and (for agent runs) a topology JSON. Optionally, events can also be merged into an AgenticLens workflow.

## Console report

`agentic-chaos chaos run` prints a table of recorded events:

```text
                                  Chaos Events
  Step        Fault           Outcome    Message
 ────────────────────────────────────────────────────────────────────────────
  Retriever   token_timeout   errored    call hung for 2.0s then timed out

1 chaos event(s) recorded.

Saved chaos report to chaos_run.json
```

| Column | Meaning |
| --- | --- |
| Step | The `step_name` you supplied, if any. |
| Fault | The fault type name (for example `token_timeout`). |
| Outcome | What happened at the call site. See [outcomes](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/output-formats.md#outcomes). |
| Message | A human-readable description of the effect. |

## ChaosEvent

Every injected fault records one `ChaosEvent`. The fields documented for the package are:

| Field | Description |
| --- | --- |
| `fault_type` | Which fault fired. |
| `outcome` | What the call did as a result. |
| `step_id` / `step_name` | Correlation you chose by passing them to `chaos_call()` (or via `step_kwargs()` for AgenticLens). Optional. |
| `fidelity_score` | A `0.0` to `1.0` score, present when a [fidelity session](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/features.md) is active. |

Events are available from the session object:

```python
with chaos_session([...]) as session:
    ...
for event in session.events:
    print(event.fault_type, event.outcome)
```

### Outcomes

| Outcome | Produced by | Meaning |
| --- | --- | --- |
| `errored` | Error-raising faults (`token_timeout`, `rate_limit_storm`, `tool_failure` in `"error"`/`"timeout"` mode) | The call raised an error. |
| `degraded` | Corruption faults (`silent_degradation`, `memory_corruption`, `tool_failure` in `"empty"` mode, `handoff_corruption` in `"corrupt"`/`"drop"` mode) | The call completed but its output was altered or discarded. |
| `delayed` | `TokenTimeoutFault(mode="delay")`, `HandoffCorruptionFault(mode="delay")` | The call succeeded, but late. |
| `looped` | `InfiniteLoopFault` | The fault replaced the real return value with a "continue" signal. |

## Standalone JSON report (`--save`)

Passing `--save <path>` writes the package's own report, a `ChaosReport`, as JSON:

```bash
agentic-chaos chaos run my_app.py --inject silent_degradation --save chaos_run.json
```

The report needs no other library to produce or read. It contains:

```json
{
  "id": "<uuid>",
  "name": "my_app",
  "start_time": "2026-08-01T10:00:00Z",
  "end_time": "2026-08-01T10:00:02Z",
  "chaos_events": [
    {
      "id": "<uuid>",
      "fault_type": "token_timeout",
      "outcome": "errored",
      "step_name": "Retriever",
      "message": "call hung for 2.0s then timed out",
      "timestamp": "2026-08-01T10:00:01Z",
      "fidelity_score": null,
      "detail": {"hang_seconds": 2.0, "mode": "raise"}
    }
  ],
  "agent_topology": null,
  "drift_report": null
}
```

Read it back with any JSON tool:

```bash
python -m json.tool chaos_run.json
jq '.chaos_events[] | {fault_type, outcome}' chaos_run.json
```

### Probes and resilience (0.9.0)

Reports also carry the steady-state probe results and the resilience score:

```json
{
  "probes": [
    {"probe": "answers", "kind": "response_quality", "phase": "post", "status": "passed",
     "message": "answer meets every quality check", "attempts": 1, "duration_ms": 0.4,
     "weight": 1.0, "started_at": "2026-10-31T02:00:01+00:00", "observed": {"output": "'Answer: ...'"}}
  ],
  "resilience": {
    "version": "1.0", "score": 92, "status": "scored", "grade": "A",
    "components": [{"name": "recovery", "score": 1.0, "weight": 0.35,
                    "detail": "3/3 injections recovered", "observed": {"retried": 3}}],
    "faults": [{"fault_type": "rate_limit_storm", "events": 3, "score": 100,
                "verdicts": {"retried": 3}, "note": "3 retried"}],
    "reasons": [], "trend": {"previous": 84, "delta": 8, "direction": "up"}
  }
}
```

`resilience.score` is `null` (status `inconclusive`) when it cannot be computed;
`reasons` says why. Both fields are absent from, and optional on, older reports.

### Agent runs

`agentic-chaos agent run ... --save report.json` writes the same style of report for agent-level faults (`tool_failure`, `memory_corruption`, `infinite_loop`, `handoff_corruption`).

## Topology JSON

`TopologyTracker` records nodes and edges while you use `wrap_tool()` / `wrap_node()`:

```python
print(tracker.topology.as_json())  # nodes + edges
```

Nodes are registered with `tracker.register_node(name, type=...)`. Edges are recorded between caller nodes and the tools or nodes they call. Handoff chaos targets these edges rather than nodes.

```mermaid
flowchart LR
    SupportAgent((SupportAgent)) -- search --> Search[search tool]
    SupportAgent -- refund --> Refund[refund tool]
```

## AgenticLens `chaos_events`

When you use the [AgenticLens integration](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/integrations.md#agenticlens), `attach_events()` copies events onto the `Workflow`. To attach a drift report as well, use `attach_drift_report(report_dict, workflow)` from the same module. Exporting with `JSONExporter` then includes `chaos_events` and `drift_report` fields, following the documented shared JSON shapes (workflow schema v1.1 and v1.4).

`agenticlens analyze workflow.json` turns those events into an "Optimization Suggestions" entry such as:

```text
* Chaos impact: token_timeout on 'Retriever'
  -- Injected fault 'token_timeout' hit step 'Retriever' 1 time and the call
     raised an error each time (call hung for 2.0s then timed out). ... (~0 tokens)
```

## Drift report and state

`agentic-chaos drift snapshot --save baseline.json` writes a baseline snapshot, and `drift compare ... --save drift_report.json` writes a drift report. The comparison covers four signal types:

| Signal | Based on |
| --- | --- |
| Prompt drift | Hash and inline diff metadata of the prompt file. |
| Model drift | Model name, provider fingerprint and embedding-model metadata. |
| Output drift | A lightweight text-distance score against the baseline output. |
| Retrieval drift | Set distance on fixed retrieval results. |

`--state-path` (for example `.agentic-chaos/drift-state.json`) stores state used by `--cooldown-minutes` and `--emit-only-on-change`, so scheduled runs stay quiet until something changes.

**Exit codes:** `drift compare` exits with `2` when drift is detected, otherwise it follows normal CLI conventions.

### Drift snapshot fields

A snapshot saved with `drift snapshot --save baseline.json` has these top-level fields:

| Field | Type | Description |
| --- | --- | --- |
| `id` | string (UUID) | Auto-generated snapshot ID |
| `name` | string | The `--name` you supplied |
| `captured_at` | datetime string | UTC timestamp of capture |
| `prompt_text` | string or null | Full prompt text (from `--prompt-file`) |
| `prompt_hash` | string or null | SHA-256 of normalised prompt |
| `model_name` | string or null | From `--model` |
| `model_fingerprint` | string or null | From `--model-fingerprint` |
| `output_text` | string or null | From `--output-file` |
| `output_hash` | string or null | SHA-256 of normalised output |
| `retrieval_items` | list of strings | From `--retrieval-file` or `--retrieval-item` |
| `retrieval_hash` | string or null | SHA-256 of joined retrieval items |
| `embedding_model` | string or null | From `--embedding-model` |
| `metadata` | dict | Reserved for future use |

### Drift report fields

A drift report saved with `drift compare --save drift_report.json` has these top-level fields:

| Field | Type | Description |
| --- | --- | --- |
| `id` | string (UUID) | Auto-generated report ID |
| `name` | string | Name from the current snapshot |
| `compared_at` | datetime string | UTC timestamp of comparison |
| `baseline_snapshot_id` | string | ID of the baseline snapshot |
| `current_snapshot_id` | string | ID of the current snapshot |
| `has_drift` | boolean | `true` when any finding has `changed=true` |
| `findings` | list of `DriftFinding` | One entry per signal checked (prompt, model, output, retrieval) |
| `baseline` | dict | Metadata from the baseline snapshot |
| `current` | dict | Metadata from the current snapshot |

Each `DriftFinding` has: `kind` (`"prompt"`, `"model"`, `"output"`, `"retrieval"`), `changed` (boolean), `score` (float or null), `threshold` (float or null), `message`, `detail`.

---

## Safety

Source: [docs/safety.md](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/safety.md)

Safety rails are cooperative guards on instrumented work. Use them with
`chaos_call`, `chaos_acall`, `chaos_stream`, `chaos_astream`, and explicit provider
patches. The package remains standalone; SDKs and sibling projects are optional.

```python
from agentic_chaos import CircuitBreaker, ChaosAbortedError, chaos_call, chaos_session

with chaos_session([], breaker=CircuitBreaker(
    max_cost_usd=5.0, max_failure_rate=0.5, window_size=20, min_calls=5,
    max_duration_seconds=60, max_injections=100,
)) as session:
    try:
        result = chaos_call(lambda: "offline result")
        session.record_usage(input_tokens=100, output_tokens=50,
                             input_usd_per_million=1, output_usd_per_million=2)
    except ChaosAbortedError:
        print(session.report_fields())
```

## Limits and accounting

- Cost aborts at or above `max_cost_usd`. Call `session.record_cost(cost_usd)` or
  `record_usage(...)` with measured tokens and supplied per-million prices.
  No provider prices or response usage are guessed. An unreported cost cannot
  trigger this limit. Accounting after a call can overshoot the budget by that
  call's cost. Record reservations before a call if pre-dispatch budgeting is needed.
- Failure rate aborts **above** `max_failure_rate`, using the last `window_size`
  completed wrapped operations, after `min_calls` completions. An escaping
  exception counts as failure; degradation and stream cuts do not imply a
  failed target operation. Stream consumption counts once, not once per chunk.
  Stream-provider creation is a separate guarded operation. Cancellation counts
  as a failed completion when its worker finishes. This is operational exception
  rate, not recovery quality or a resilience score.
- `max_injections` reserves capacity before fault execution and commits the
  count only when a fault event is produced. Eventless completions release their
  reservation. Built-in pass-through predicates skip admission. The next eligible injection
  attempt aborts. It does not count preview records. Slow-stream delay faults
  count once per stream even if they delay multiple chunks.
- Duration is elapsed monotonic time checked at admission, dispatch, stream
  iteration/delivery boundaries, and completion. It is cooperative: blocking
  target calls, upstream reads, and bounded fault sleeps can exceed the duration
  before the next check. There is no timer that kills arbitrary code.
- Limits validate finite values and positive integer windows/counts. Failure
  rates lie in `[0, 1]`; `min_calls` cannot exceed `window_size`. Breaker
  configuration is copied into fresh state on each session entry.

Abort is sticky. Catching `ChaosAbortedError` does not re-enable dispatch.
Shared locked state covers async workers and inherited tasks; queued async
provider work checks again on the event loop before entering its target.
A session that has ended rejects inherited instrumented work.

Already-running calls can finish after abort. `in_flight_at_abort` records how
many wrapped operations were running when the threshold fired; `in_flight`
records outstanding operations when the report is captured. Reports are snapshots,
not a guarantee that external work stopped. Direct calls and custom fault code
that bypass these wrappers remain outside this boundary. The containment tests
include a deliberately bypassed direct call as a negative control.

## Dry-run

```bash
agentic-chaos chaos run examples/chaos_customer_support_demo.py \
  --inject rate_limit_storm --dry-run --save preview.json
agentic-chaos agent run my_agent.py --profile staging --profile-file chaos.toml \
  --dry-run --max-duration-seconds 30 --save preview.json
```

`chaos_session(..., dry_run=True)` uses the same configured selection and seeded
probability, tool/edge predicates, and finite burst/turn state. Selection RNG and
preview counters use private copies; original fault state stays unchanged.
Custom pass-through faults should implement `eligible()` and, if stateful,
`advance_preview()` (use independent scalar preview state); their trigger is
never executed to discover eligibility during dry-run. It executes targets and delivers original stream chunks without
fault mutation, delay, error, or skipped calls. This can still make real API calls
and spend money. Preview records live in `planned_events` (`would_inject`) rather
than `chaos_events`, so consumers do not mistake a plan for an observed failure.
For streams, a plan is recorded when consumption reaches the configured fault
boundary. An unconsumed stream has no plan. Multiple faults still require explicit
call-site selection. Safety limits also apply during preview.

Both CLI run commands support `--max-cost-usd`, `--max-failure-rate`,
`--failure-window`, `--min-calls`, `--max-duration-seconds`, `--max-injections`,
and `--dry-run`. They save evidence even when the target raises or catches an
abort; an aborted command exits nonzero.

## Reports and sibling compatibility

Build a native report with the session's additive safety fields:

```python
from datetime import datetime, timezone
from agentic_chaos.models import ChaosReport

report = ChaosReport(name="experiment", start_time=datetime.now(timezone.utc),
                     chaos_events=session.events_as_json(), **session.report_fields())
```

The fields are `aborted`, `abort_reason` (threshold, limit, observed value,
`in_flight_at_abort`), `dry_run`, `planned_events`, `cost_usd`, `injections`, and
`in_flight`. Old reports load with defaults. The native event shape is unchanged.
AIOS export preserves these fields under the existing
`io.deepagentlabs.agentic-chaos.safety` extension and maps abort to Run
`cancelled`; preview adds no synthetic occurrence or reliability evidence.
No new canonical AIOS type is invented.

Compatibility tests exercise Lens's Workflow parser, Tower's native report
reader, MCP's saved-report AIOS export, and AIOS schema/semantic validation.
Existing consumers accept additive fields, but their native views need not display
abort/preview metadata. MCP's existing `run_experiment` does not expose the new
CLI flags or populate safety fields automatically. Use the Python API or CLI for
safety-controlled execution; the saved-report export preserves its metadata.
No sibling runtime dependency or patch release is required for these compatible
artifacts. The development lock includes Lens 0.6.1 and Evals 0.7.1; CI checks out
current Lens, Tower, MCP, and AIOS sources.

Run `uv run python examples/chaos_safety_demo.py` for the offline example.
Regenerate the demo with
`uv run --with pillow python scripts/generate_safety_demo.py`.

![Offline safety demonstration](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/assets/safety-demo.gif)

---

## Limitations

Source: [docs/limitations.md](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/limitations.md)

Agentic Chaos is early-stage software. This page lists what it does not do today so you can plan around it.

## Maturity

- The package is **early-stage (PyPI classifier: Alpha)** and supports Python 3.10 to 3.13.
- Released modules: **LLM Chaos Toolkit** (v0.1), **Agent Failure Injector** (v0.2), **Fidelity Judges & Handoff Chaos** (v0.3.0) and **Prompt/Model Drift Detector** (v0.4.0).
- APIs may change between early releases. Pin your version in production test suites.
- Planned work is tracked only in the [Roadmap](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/roadmap.md).

## What it simulates, and what it does not

- **Client-side simulation.** Faults are injected at the Python call boundary. They do not touch the network, so they cannot reproduce provider-side behavior such as real latency distributions, partial streaming failures, or TLS and DNS errors.
- **Explicit opt-in per call site.** Only code wrapped with `chaos_call()`, `wrap_tool()` or `wrap_node()` (or run through the CLI against instrumented code) can be affected. Calls you did not wrap are never faulted.
- **Python only.** The toolkit targets Python callables. Other languages and remote services are out of scope.
- **Not a load-testing tool.** The rate-limit storm is a deterministic burst of errors, not traffic generation.

## Fault-specific notes

| Fault | Limitation |
| --- | --- |
| `token_timeout` | Hangs by sleeping for `hang_seconds`, so it slows the process for that long. In `mode="delay"` the real call still runs. It does not model streaming token timeouts. |
| `rate_limit_storm` | Fails the first `burst_count` calls and then clears. There is no random or time-windowed pattern. |
| `silent_degradation` | The built-in corruption only handles `.content`, `.text`, or a raw string. Other shapes need a custom `degrade_fn`. |
| `tool_failure` | Matches by tool name. Tools not wrapped with `wrap_tool()` are not affected. |
| `memory_corruption` | Operates on the shared agent state you expose to it. It cannot see state hidden inside a framework. |
| `infinite_loop` | Replaces the return value with a continue signal for `force_turns` calls. Your agent must interpret that signal for the test to be meaningful. |
| `handoff_corruption` | Targets edges recorded in a `TopologyTracker`. Edges you never registered cannot be targeted. |

## Fidelity judging

- `HeuristicJudge` is a lightweight, dependency-free heuristic. It is a signal, not a ground-truth quality metric.
- `DeepEvalJudge` and `PydanticEvalsJudge` wrap evaluator objects that you construct. Their scoring quality, cost and any API keys are your responsibility.
- Judges need a baseline to compare against. For pure downstream functions you may need to capture it manually.

## Drift detector

- Compares **local files and metadata you provide** (prompt file, output file, retrieval file, model name and fingerprint). It does not call a model or provider itself.
- Output drift uses a lightweight text-distance score. It is a change signal, not a semantic quality judgment.
- Retrieval drift is a set-distance over *fixed* retrieval results.
- `drift compare` exits with code `2` when drift is detected. CI steps must expect that code.
- Scheduling is external (cron, CI). The package does not run a scheduler.

## Reporting

- The standalone `ChaosReport` records what happened, but experiment reports with hypothesis, provenance and verdict are not yet available (see the [Roadmap](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/roadmap.md)).
- There are no built-in HTML dashboards. Use the JSON report, or AgenticLens for analysis.

## Resilience score

- The score summarizes evidence in the report. It is not a guarantee: a run
  that never exercised a failure path cannot show how that path recovers.
- Recovery is inferred from the call log. A failure counts as recovered when
  a later call to the same step succeeded, or when nothing escaped and the
  step was not retried. Instrument the steps you care about with `step_name`.
- Silent degradation counts only when a fidelity judge scored it. Otherwise it
  is reported as `unverified` and left out.
- Latency and cost need a baseline report, and latency compares wall-clock
  run durations, which are noisy for very short runs.
- The run history is a local JSON file with no locking. Give concurrent jobs
  separate files.

## Integrations

- The AgenticLens extra is currently resolved from a sibling checkout in the source repository until a compatible AgenticLens release is published.
- Interop relies on the shared JSON shape (schema v1.1). Changes to that schema may require upgrading both packages.

## Safety

!!! danger "Do not run chaos against production data without safeguards"
    Faults can raise exceptions, corrupt text, and alter agent state. Run experiments in test or staging environments, and ensure wrapped tools do not perform irreversible actions (for example real refunds) while a fault is active.

---

## Source declarations: src/agentic_chaos/__init__.py

Source: [src/agentic_chaos/__init__.py](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/src/agentic_chaos/__init__.py)

```python
__all__ = ['FunctionProbe', 'HttpProbe', 'LatencyProbe', 'Probe', 'ResilienceHistory', 'ResilienceScore', 'ResponseQualityProbe', 'chaos_run', 'compute_resilience', 'ChaosWorkflow', 'HealthCheck', 'Parallel', 'Step', 'Suspend', 'Template', 'WorkflowReport', 'fuzz_topology', 'load_experiment', 'validate_experiment', 'BreakingPointResult', 'FaultCascade', 'cascade', 'find_breaking_point', 'PoisonedResponseFault', 'Scope', 'CompletesWithin', 'ContractViolationError', 'FullTopologyTraversal', 'MaxCostImpact', 'MaxRetries', 'NoRetryStorm', 'NoUnhandledError', 'RecoveredAfterFailure', 'assert_contracts', 'check_contracts', 'CircuitBreaker', 'ChaosAbortedError', 'load_profile', 'chaos_acall', 'patch_openai', 'patch_anthropic', 'patch_google', 'AuthErrorFault', 'ContextLengthFault', 'SlowChunksFault', 'SlowTTFTFault', 'StreamCutFault', 'StreamHangFault', 'chaos_astream', 'chaos_stream', 'DeepEvalJudge', 'DriftReport', 'DriftSnapshot', 'HandoffCorruptionFault', 'HeuristicJudge', 'InfiniteLoopFault', 'MemoryCorruptionFault', 'PydanticEvalsJudge', 'RateLimitStormFault', 'SilentDegradationFault', 'TokenTimeoutFault', 'ToolCallFailureFault', 'TopologyTracker', '__version__', 'chaos_call', 'chaos_session', 'compare_snapshots', 'fidelity_session', 'wrap_node', 'wrap_tool']
```

---

## Source declarations: src/agentic_chaos/models/__init__.py

Source: [src/agentic_chaos/models/__init__.py](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/src/agentic_chaos/models/__init__.py)

```python
__all__ = ['AgentEdge', 'AgentNode', 'AgentTopology', 'ChaosEvent', 'ChaosReport', 'Outcome']
```

---

## Source declarations: src/agentic_chaos/models/agent_topology.py

Source: [src/agentic_chaos/models/agent_topology.py](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/src/agentic_chaos/models/agent_topology.py)

```python
class AgentNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: str = 'agent'
class AgentEdge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    target_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message_type: str = 'call'
class AgentTopology(BaseModel):
    nodes: list[AgentNode] = Field(default_factory=list)
    edges: list[AgentEdge] = Field(default_factory=list)
    def as_json(self) -> dict[str, Any]: ...
```

---

## Source declarations: src/agentic_chaos/models/chaos_event.py

Source: [src/agentic_chaos/models/chaos_event.py](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/src/agentic_chaos/models/chaos_event.py)

```python
class ChaosEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fault_type: str
    step_id: str | None = None
    step_name: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    outcome: Outcome
    message: str
    fidelity_score: float | None = None
    edge_id: str | None = None
    from_node: str | None = None
    to_node: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
```

---

## Source declarations: src/agentic_chaos/models/report.py

Source: [src/agentic_chaos/models/report.py](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/src/agentic_chaos/models/report.py)

```python
class ChaosReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    start_time: datetime
    end_time: datetime | None = None
    chaos_events: list[dict[str, Any]] = Field(default_factory=list)
    agent_topology: dict[str, Any] | None = None
    drift_report: dict[str, Any] | None = None
    aborted: bool = False
    abort_reason: dict[str, Any] | None = None
    dry_run: bool = False
    planned_events: list[dict[str, Any]] = Field(default_factory=list)
    cost_usd: float = 0.0
    injections: int = 0
    in_flight: int = 0
    calls: list[dict[str, Any]] = Field(default_factory=list)
    calls_dropped: int = 0
    unhandled_error: dict[str, Any] | None = None
    workflow: dict[str, Any] | None = None
    probes: list[dict[str, Any]] = Field(default_factory=list)
    resilience: dict[str, Any] | None = None
    @property
    def resilience_score(self) -> int | None: ...
def load_report(report: ReportLike) -> ChaosReport: ...
```

---

## Source declarations: src/agentic_chaos/chaos/faults.py

Source: [src/agentic_chaos/chaos/faults.py](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/src/agentic_chaos/chaos/faults.py)

```python
class ChaosFaultError(Exception):
    def __init__(self, message: str, event: ChaosEvent) -> None: ...
class TokenTimeoutError(ChaosFaultError):
    ...
class RateLimitStormError(ChaosFaultError):
    def __init__(self, message: str, event: ChaosEvent, retry_after: float) -> None: ...
@dataclass
class FaultOutcome():
    result: Any = None
    event: ChaosEvent | None = None
    raised: BaseException | None = None
    baseline: Any = None
class BaseFault(ABC):
    name: str
    scope: 'Scope | None' = None
    def __init__(self, probability: float=1.0, seed: int | None=None, *, scope: 'Scope | None'=None) -> None: ...
    def in_scope(self, *, step_name: str | None=None, provider: str | None=None) -> bool: ...
    def should_trigger(self) -> bool: ...
    def eligible(self, *, step_name: str | None=None, edge_id: str | None=None, from_node: str | None=None, to_node: str | None=None) -> bool: ...
    def advance_preview(self) -> None: ...
    @abstractmethod
    def trigger(self, call: Callable[..., Any], *, step_id: str | None, step_name: str | None, call_args: tuple[Any, ...]=(), call_kwargs: dict[str, Any] | None=None, edge_id: str | None=None, from_node: str | None=None, to_node: str | None=None) -> FaultOutcome: ...
class TokenTimeoutFault(BaseFault):
    name = 'token_timeout'
    def __init__(self, hang_seconds: float=2.0, mode: str='raise', *, probability: float=1.0, seed: int | None=None, scope: 'Scope | None'=None) -> None: ...
    def trigger(self, call: Callable[..., Any], *, step_id: str | None, step_name: str | None, call_args: tuple[Any, ...]=(), call_kwargs: dict[str, Any] | None=None, edge_id: str | None=None, from_node: str | None=None, to_node: str | None=None) -> FaultOutcome: ...
class RateLimitStormFault(BaseFault):
    name = 'rate_limit_storm'
    def __init__(self, burst_count: int=3, retry_after: float=1.0, *, probability: float=1.0, seed: int | None=None, scope: 'Scope | None'=None) -> None: ...
    def eligible(self, **kwargs: Any) -> bool: ...
    def advance_preview(self) -> None: ...
    def trigger(self, call: Callable[..., Any], *, step_id: str | None, step_name: str | None, call_args: tuple[Any, ...]=(), call_kwargs: dict[str, Any] | None=None, edge_id: str | None=None, from_node: str | None=None, to_node: str | None=None) -> FaultOutcome: ...
def garble_text(text: str, rng: random.Random | None=None) -> str: ...
def mutate_text_attrs(result: Any, mutator: Callable[[str], str]) -> Any: ...
def snapshot_baseline(value: Any) -> Any: ...
class SilentDegradationFault(BaseFault):
    name = 'silent_degradation'
    def __init__(self, degrade_fn: Callable[[Any], Any] | None=None, seed: int | None=None, probability: float=1.0, *, scope: 'Scope | None'=None) -> None: ...
    def trigger(self, call: Callable[..., Any], *, step_id: str | None, step_name: str | None, call_args: tuple[Any, ...]=(), call_kwargs: dict[str, Any] | None=None, edge_id: str | None=None, from_node: str | None=None, to_node: str | None=None) -> FaultOutcome: ...
def resolve_faults(names: 'str | Sequence[str | BaseFault]') -> list[BaseFault]: ...
```

---

## Source declarations: src/agentic_chaos/agents/faults.py

Source: [src/agentic_chaos/agents/faults.py](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/src/agentic_chaos/agents/faults.py)

```python
class ToolCallFailureError(ChaosFaultError):
    ...
class InfiniteLoopError(ChaosFaultError):
    ...
class ToolCallFailureFault(BaseFault):
    name = 'tool_failure'
    def __init__(self, mode: str='error', timeout_seconds: float=5.0, error_message: str='Tool execution failed', tool_name: str | None=None, probability: float=1.0, seed: int | None=None, *, scope: 'Scope | None'=None) -> None: ...
    def eligible(self, *, step_name: str | None=None, **kwargs: Any) -> bool: ...
    def trigger(self, call: Callable[..., Any], *, step_id: str | None, step_name: str | None, call_args: tuple[Any, ...]=(), call_kwargs: dict[str, Any] | None=None, edge_id: str | None=None, from_node: str | None=None, to_node: str | None=None) -> FaultOutcome: ...
class MemoryCorruptionFault(BaseFault):
    name = 'memory_corruption'
    def __init__(self, mode: str='garble', seed: int | None=None, rate: float=0.25, probability: float=1.0, *, scope: 'Scope | None'=None) -> None: ...
    def trigger(self, call: Callable[..., Any], *, step_id: str | None, step_name: str | None, call_args: tuple[Any, ...]=(), call_kwargs: dict[str, Any] | None=None, edge_id: str | None=None, from_node: str | None=None, to_node: str | None=None) -> FaultOutcome: ...
class HandoffCorruptionFault(BaseFault):
    name = 'handoff_corruption'
    def __init__(self, *, from_node: str | None=None, to_node: str | None=None, mode: str='corrupt', delay_seconds: float=1.0, seed: int | None=None, probability: float=1.0, scope: 'Scope | None'=None) -> None: ...
    def eligible(self, *, edge_id: str | None=None, from_node: str | None=None, to_node: str | None=None, **kwargs: Any) -> bool: ...
    def trigger(self, call: Callable[..., Any], *, step_id: str | None, step_name: str | None, call_args: tuple[Any, ...]=(), call_kwargs: dict[str, Any] | None=None, edge_id: str | None=None, from_node: str | None=None, to_node: str | None=None) -> FaultOutcome: ...
class InfiniteLoopFault(BaseFault):
    name = 'infinite_loop'
    def __init__(self, force_turns: int=5, continue_value: Any='I need to continue processing this request.', probability: float=1.0, seed: int | None=None, *, scope: 'Scope | None'=None) -> None: ...
    def eligible(self, **kwargs: Any) -> bool: ...
    def advance_preview(self) -> None: ...
    def trigger(self, call: Callable[..., Any], *, step_id: str | None, step_name: str | None, call_args: tuple[Any, ...]=(), call_kwargs: dict[str, Any] | None=None, edge_id: str | None=None, from_node: str | None=None, to_node: str | None=None) -> FaultOutcome: ...
```

---

## Source declarations: src/agentic_chaos/chaos/inject.py

Source: [src/agentic_chaos/chaos/inject.py](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/src/agentic_chaos/chaos/inject.py)

```python
def chaos_call(fn: Callable[..., T], *args: Any, step_id: str | None=None, step_name: str | None=None, _chaos_edge_id: str | None=None, _chaos_from_node: str | None=None, _chaos_to_node: str | None=None, chaos_provider: str | None=None, faults: list[str] | None=None, **kwargs: Any) -> T: ...
```

---

## Example file: chaos_quickstart.py

Source: [docs/guide/examples/chaos_quickstart.py](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/docs/guide/examples/chaos_quickstart.py)

```python
from agentic_chaos.chaos import TokenTimeoutError, chaos_call


def search(question):
    return [f"Document about {question}"]


try:
    result = chaos_call(search, "refund policy", faults=["token_timeout"], step_name="Search")
except TokenTimeoutError:
    result = []
print("Search result:", result)
```
