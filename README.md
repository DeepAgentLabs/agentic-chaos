# agentic-chaos

`agentic-chaos` is a fault-injection toolkit for LLM calls and agentic
workflows. It deliberately breaks your app — hung completions, provider
rate-limit storms, silently corrupted output — and records what happened in
the same `workflow.json` format that
[AgenticLens](https://github.com/agenticlens/agenticlens) already knows how to
report and analyze. Run chaos, then hand the file straight to
`agenticlens analyze` for a resilience report alongside the cost/latency
findings it already produces.

## Status

`agentic-chaos` is early-stage software (v0.1 — the **LLM Chaos Toolkit**).
Two more modules are planned: an **Agent Failure Injector** for
LangGraph/CrewAI/AutoGen (v0.2), and a **Prompt/Model Drift Detector** (v0.3).
See [ROADMAP.md](ROADMAP.md) for the full plan.

## Installation

This package depends on `agenticlens`, which is not yet published — install
both from source with `uv`, as sibling checkouts:

```bash
git clone https://github.com/agenticlens/agenticlens.git
git clone https://github.com/agenticlens/agentic-chaos.git
cd agentic-chaos
uv sync --extra dev
```

`pyproject.toml` points `uv` at `../agenticlens` for local development (see
`[tool.uv.sources]`); once both packages are on PyPI that override goes away
and `pip install agentic-chaos` will pull `agenticlens` transitively.

## Quickstart

Wrap the calls you want to be fragile with `chaos_call()`, alongside
AgenticLens's existing `profile()`/`step()` instrumentation:

```python
from agenticlens import profile, step
from agentic_chaos.chaos import chaos_call, TokenTimeoutError

with profile("Customer Support Agent"):
    with step("Retriever", type="retriever", chunk_count=4) as s:
        try:
            chunks = chaos_call(retriever.search, user_question, step=s, faults=["token_timeout"])
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

Then analyze it with AgenticLens, unchanged:

```bash
uv run agenticlens analyze chaos_run.json
```

```text
Optimization Suggestions
  * Chaos impact: token_timeout on 'Retriever'
    -- Injected fault 'token_timeout' hit step 'Retriever' 1 time and the call
       raised an error each time (call hung for 2.0s then timed out). No retry
       or graceful fallback was observed handling it. (~0 tokens)
```

## The Interop Loop

This is the core value loop, and it works the same way regardless of which
`agentic-chaos` module produced the file:

1. `agentic-chaos` runs your app, injects failures, and records what happened
   into a `chaos_events` array on the same `Workflow` your `step()`/`profile()`
   calls already build.
2. AgenticLens's `ChaosImpactRecommender` — registered by default, a no-op on
   workflows with no `chaos_events` — reads that array and correlates it
   against the cost/latency data it already computes, no rebuilt reporting
   engine required.

The `chaos_events` schema extension is documented as part of AgenticLens's
data contract in
[`docs/workflow-schema-spec.md`](https://github.com/agenticlens/agenticlens/blob/main/docs/workflow-schema-spec.md)
(agenticlens repo) — any tool that appends well-formed entries to that list
gets recommendation support for free.

## Fault Types (v0.1)

| Fault | `--inject` name | What it does |
| --- | --- | --- |
| Token timeout | `token_timeout` | Hangs for `hang_seconds` (default 2.0s), then raises `TokenTimeoutError` — simulates a client-side timeout on a hung/slow completion. Pass `mode="delay"` to let the real call complete late instead of erroring. |
| Rate-limit storm | `rate_limit_storm` | Raises `RateLimitStormError` (with a `retry_after` hint) for the first `burst_count` calls (default 3), then passes calls through normally — simulates a provider 429/backoff cascade that eventually clears. |
| Silent degradation | `silent_degradation` | Calls the real function, then corrupts its text content (`.content`/`.text`/a raw string) while preserving latency and token counts. The hardest fault to detect and the highest-value one to catch — nothing in cost/latency telemetry looks wrong. |

Every fault records a `ChaosEvent` (`fault_type`, `outcome`, and — when you
pass `step=` — the correlated `step_id`/`step_name`) into the active
`chaos_session()`. Use the Python API to override defaults per fault:

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

# Same, saving the resulting workflow (with chaos_events) for later analysis.
agentic-chaos chaos run my_app.py --inject silent_degradation --save chaos_run.json
agenticlens analyze chaos_run.json

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
uv run agenticlens analyze /tmp/chaos_run.json
```

The example wraps a Planner (rate-limit storm the app retries through and
recovers from), a Retriever (token timeout the app doesn't handle, so it
fails outright), and a Final Response (silent degradation — a normal-looking
call with corrupted output) — the three shapes of chaos this module injects.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy
```

## License

MIT — see [LICENSE](LICENSE).
