# Agentic Chaos developer guide

Use this guide to set up Agentic Chaos, run a local example, and apply it to your application. Optional provider and integration fragments identify the objects or services you must supply.

[Quickstart](#quickstart) · [Usage](#usage) · [Configuration](#settings) · [Troubleshooting](#troubleshooting) · [Reference](#reference)

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

[Download chaos_quickstart.py](guide/examples/chaos_quickstart.py)

### Compare normal execution with injected failure

```
python chaos_quickstart.py
agentic-chaos chaos run chaos_quickstart.py --inject token_timeout --save chaos_run.json
```

**Expected:** the normal run returns a document. Under the timeout fault, the script catches the timeout and prints an empty result. A chaos report records the injected event.

An empty result is an observed recovery weakness, not a resilience pass. Decide what a useful fallback should return, implement it, and repeat the experiment.

### Connect real code

Wrap the callable whose failure you want to study. Establish the normal baseline, then inject a single fault before combining scenarios. Keep tests bounded and use a controlled test target.

[Configure experiments ↗](configuration.md) · [Read reports ↗](output-formats.md)

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

Optional Lens correlation is installed with `python -m pip install "agentic-chaos[agenticlens]"`. The published extra declares a package dependency; the sibling path in `tool.uv.sources` is a source-development setting. See the [integration reference](integrations.md) and [runnable correlation example](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/examples/chaos_with_agenticlens_demo.py).

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

Full details are in the [CLI Reference](cli-reference.md#agentic-chaos-drift-snapshot).

## Troubleshooting

Check the failing boundary before changing application behavior.

- No fault outside the CLI/session: the wrapper is a pass-through outside an active chaos context.
- Fault report exists but application succeeds: verify whether a fallback actually met the task requirement.
- Missing optional integration: install only the relevant extra for that workflow.

### Verify your environment

Run commands from the environment where you installed the package. Confirm the input file exists and matches the expected artifact contract. Keep the original evidence when diagnosing a failure.

## Reference

Use the current product reference for exact method signatures, command options, and supported artifacts. The code fragments in configuration and how-to articles build on the quickstart; they are not all standalone scripts.

- [Open API / CLI reference ↗](cli-reference.md)
