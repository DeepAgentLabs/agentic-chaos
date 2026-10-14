# Configuration

Agentic Chaos has **no configuration file and no required environment variables**.
Behavior is configured in three places: fault constructor arguments, `chaos_session()`
and `chaos_call()` arguments in Python, and CLI flags.

## Choosing active faults

=== "CLI"

    ```bash
    agentic-chaos chaos run my_app.py --inject token_timeout,rate_limit_storm
    ```

    `--inject` takes a comma-separated list of fault names.

=== "Python (by name)"

    ```python
    from agentic_chaos.chaos import chaos_session

    with chaos_session(["token_timeout"]) as session:
        ...
    ```

=== "Python (by instance)"

    ```python
    from agentic_chaos.chaos import chaos_session, TokenTimeoutFault

    with chaos_session([TokenTimeoutFault(hang_seconds=5.0)]) as session:
        ...
    ```

Passing a name uses the fault's defaults. Passing an instance lets you override them.

## Fault parameters

### LLM-level faults

| Fault | Parameter | Default | Meaning |
| --- | --- | --- | --- |
| `TokenTimeoutFault` | `hang_seconds` | `2.0` | Seconds to hang before raising `TokenTimeoutError` |
| `TokenTimeoutFault` | `mode` | `"raise"` | `"delay"` lets the real call complete late instead of raising; outcome becomes `"delayed"` |
| `RateLimitStormFault` | `burst_count` | `3` | Number of initial calls that raise `RateLimitStormError` before calls pass through |
| `RateLimitStormFault` | `retry_after` | `1.0` | Seconds hint carried on the `RateLimitStormError.retry_after` attribute for callers that implement backoff |
| `SilentDegradationFault` | `degrade_fn` | built-in text garbler | `fn(result) -> corrupted_result`, replaces the default corruption |
| `SilentDegradationFault` | `seed` | `None` | Integer seed for the internal RNG; set for reproducible garbling |

### Agent-level faults

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

<!-- Note: HandoffCorruptionFault only fires when chaos_call() is called with _chaos_edge_id set (i.e. via wrap_node()). -->

## Call-site arguments

`chaos_call(fn, *args, faults=[...], step_id=..., step_name=..., **kwargs)`

| Argument | Required | Meaning |
| --- | --- | --- |
| `faults` | Required when the session has more than one fault | Names of the fault(s) that apply at this call site |
| `step_id`, `step_name` | Optional | Correlation recorded on the `ChaosEvent` (and used to join events to AgenticLens steps) |

All other positional and keyword arguments are forwarded to `fn` unchanged.

## Fidelity scoring

Activate a judge around a session:

```python
with fidelity_session(HeuristicJudge()):
    with chaos_session([...]) as session:
        ...
```

Swap `HeuristicJudge()` for a `DeepEvalJudge` or `PydanticEvalsJudge` that wraps an
evaluator object you have already constructed.

## Drift configuration

Drift behavior is configured entirely through `agentic-chaos drift` flags.

| Concern | Flags |
| --- | --- |
| What to snapshot or compare | `--prompt-file`, `--output-file`, `--retrieval-file` |
| Model identity | `--model`, `--model-fingerprint`, `--embedding-model` |
| Where to write results | `--save` |
| Quiet scheduled runs | `--state-path`, `--cooldown-minutes`, `--emit-only-on-change` |

Full details are in the [CLI Reference](cli-reference.md#agentic-chaos-drift-snapshot).

## Installation configuration

| Setting | Where | Notes |
| --- | --- | --- |
| Optional AgenticLens support | `pip install agentic-chaos[agenticlens]` | Installs the extra |
| Development tooling | `uv sync --extra dev --frozen` | Test, lint and type-check tools |
| Local sibling AgenticLens checkout | `[tool.uv.sources]` in `pyproject.toml` | Only needed when developing the integration |

## Development commands

The `Makefile` wraps common tasks:

```bash
make install     # install dev dependencies
make check       # lint + format + typecheck + test
make test-cov    # tests with coverage report
make help        # list all targets
```
