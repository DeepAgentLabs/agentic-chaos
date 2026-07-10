# agentic-chaos

`agentic-chaos` is a standalone fault-injection toolkit for LLM calls and
agentic workflows. It deliberately breaks your app — hung completions,
provider rate-limit storms, silently corrupted output — and reports what
happened. It has **no required dependency on any other package**, including
[AgenticLens](https://github.com/DeepAgentLabs/agenticlens): `pip install
agentic-chaos` and use it against any plain Python callable.

If you also use AgenticLens, an optional integration lets you merge chaos
events straight into an AgenticLens `Workflow`, so `agenticlens analyze`
reports on cost/latency and chaos impact together — see
[Optional: AgenticLens Integration](#optional-agenticlens-integration) below.
Neither package imports the other at the core level; the two are independent
tools that happen to compose.

## Status

`agentic-chaos` is early-stage software (v0.1 — the **LLM Chaos Toolkit**).
Two more modules are planned: an **Agent Failure Injector** for
LangGraph/CrewAI/AutoGen (v0.2), and a **Prompt/Model Drift Detector** (v0.3).
See [ROADMAP.md](ROADMAP.md) for the full plan.

## Installation

```bash
pip install agentic-chaos
```

or, from source with `uv`:

```bash
git clone https://github.com/DeepAgentLabs/agentic-chaos.git
cd agentic-chaos
uv sync --extra dev
```

That's it — no other package required. (If you want the optional AgenticLens
integration too, see [below](#optional-agenticlens-integration).)

## Quickstart

Wrap the calls you want to be fragile with `chaos_call()`:

```python
from agentic_chaos.chaos import chaos_call, TokenTimeoutError

try:
    chunks = chaos_call(retriever.search, user_question, faults=["token_timeout"])
except TokenTimeoutError:
    chunks = []  # no fallback handled it -- this is exactly what we want to find
```

Outside of a `chaos_session(...)`, `chaos_call()` is a transparent pass-through
— `fn(*args, **kwargs)` runs exactly as if `agentic-chaos` weren't there. So
the same instrumented code path is safe to ship; chaos only activates when you
explicitly turn it on.

Run the script under chaos from the CLI, choosing which faults are active
without touching the code:

```bash
uv run agentic-chaos chaos run my_app.py --inject token_timeout,rate_limit_storm --save chaos_run.json
```

```text
                                  Chaos Events
  Step        Fault           Outcome    Message
 ────────────────────────────────────────────────────────────────────────────
  Retriever   token_timeout   errored    call hung for 2.0s then timed out

1 chaos event(s) recorded.

Saved chaos report to chaos_run.json
```

`chaos_run.json` is this package's own standalone report — no other library
needed to produce or read it.

## Fault Types (v0.1)

| Fault | `--inject` name | What it does |
| --- | --- | --- |
| Token timeout | `token_timeout` | Hangs for `hang_seconds` (default 2.0s), then raises `TokenTimeoutError` — simulates a client-side timeout on a hung/slow completion. Pass `mode="delay"` to let the real call complete late instead of erroring. |
| Rate-limit storm | `rate_limit_storm` | Raises `RateLimitStormError` (with a `retry_after` hint) for the first `burst_count` calls (default 3), then passes calls through normally — simulates a provider 429/backoff cascade that eventually clears. |
| Silent degradation | `silent_degradation` | Calls the real function, then corrupts its text content (`.content`/`.text`/a raw string) while preserving latency and token counts. The hardest fault to detect and the highest-value one to catch — nothing in cost/latency telemetry looks wrong. |

Every fault records a `ChaosEvent` (`fault_type`, `outcome`, and — when you
pass `step_id`/`step_name` — the correlation you chose). Use the Python API
to override defaults per fault:

```python
from agentic_chaos.chaos import chaos_session, TokenTimeoutFault, RateLimitStormFault

with chaos_session([TokenTimeoutFault(hang_seconds=5.0), RateLimitStormFault(burst_count=1)]):
    ...
```

When more than one fault is configured for a session, `chaos_call()` requires
you to pass `faults=[...]` at each call site to say which one applies there —
silently picking one for you would be surprising.

## CLI Reference

```bash
# Run a script with chaos active and print a chaos-events report.
agentic-chaos chaos run my_app.py --inject token_timeout,rate_limit_storm

# Same, saving the resulting standalone report for later inspection.
agentic-chaos chaos run my_app.py --inject silent_degradation --save chaos_run.json

# List available fault types.
agentic-chaos chaos list-faults
```

`agentic-chaos agent ...` and `agentic-chaos drift ...` are placeholders for
the v0.2 and v0.3 modules — running them today prints a pointer to
[ROADMAP.md](ROADMAP.md).

## Example

```bash
uv run agentic-chaos chaos run examples/chaos_customer_support_demo.py \
    --inject rate_limit_storm,token_timeout,silent_degradation --save /tmp/chaos_run.json
```

The example wraps a Planner (rate-limit storm the app retries through and
recovers from), a Retriever (token timeout the app doesn't handle, so it
fails outright), and a Final Response (silent degradation — a normal-looking
call with corrupted output) — the three shapes of chaos this module injects.
It imports nothing but `agentic_chaos`.

## Optional: AgenticLens Integration

If you *also* use [AgenticLens](https://github.com/DeepAgentLabs/agenticlens)
to profile cost/latency, install the extra:

```bash
pip install agentic-chaos[agenticlens]
```

Then correlate chaos events to AgenticLens steps and merge them onto the
`Workflow` yourself:

```python
from agenticlens import profile, step
from agenticlens.exporters import JSONExporter
from agentic_chaos.chaos import chaos_call, chaos_session, TokenTimeoutError
from agentic_chaos.integrations.agenticlens import attach_events, step_kwargs

with chaos_session(["token_timeout"]) as session:
    with profile("Customer Support Agent") as workflow:
        with step("Retriever", type="retriever", chunk_count=4) as s:
            try:
                chunks = chaos_call(retriever.search, user_question, **step_kwargs(s))
            except TokenTimeoutError:
                chunks = []
    attach_events(session, workflow)

JSONExporter().export(workflow, "workflow.json")
```

```bash
agenticlens analyze workflow.json
```

```text
Optimization Suggestions
  * Chaos impact: token_timeout on 'Retriever'
    -- Injected fault 'token_timeout' hit step 'Retriever' 1 time and the call
       raised an error each time (call hung for 2.0s then timed out). ... (~0 tokens)
```

`agentic_chaos.chaos_call()`/`chaos_session()` and the CLI never import
AgenticLens — only `agentic_chaos.integrations.agenticlens` does, and only
when you import it yourself. See
[`examples/chaos_with_agenticlens_demo.py`](examples/chaos_with_agenticlens_demo.py)
for a runnable version of the above.

This works because `agentic-chaos`'s own report format (`ChaosReport`) and
AgenticLens's `chaos_events` field share a documented JSON shape (schema
v1.1, see
[`docs/workflow-schema-spec.md`](https://github.com/DeepAgentLabs/agenticlens/blob/main/docs/workflow-schema-spec.md)
in the agenticlens repo) — interop through a shared file format, not a code
dependency in either direction.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy
```

Tests covering `agentic_chaos.integrations.agenticlens` skip automatically if
`agenticlens` isn't installed. To run the full suite including those, install
the optional extra too: `uv sync --extra dev --extra agenticlens` (see
[`[tool.uv.sources]`](pyproject.toml) for the local sibling-checkout override
used until `agenticlens` publishes a release with `chaos_events` support).

## License

MIT — see [LICENSE](LICENSE).
