# agentic-chaos

`agentic-chaos` is a standalone fault-injection toolkit for LLM calls and
agentic workflows. It deliberately breaks your app — hung completions,
provider rate-limit storms, silently corrupted output — and reports what
happened. It has **no required dependency on any other package**, including
[AgenticLens](https://github.com/DeepAgentLabs/agenticlens): `pip install
agentic-chaos` and use it against any plain Python callable.

Within the broader DeepAgentLabs architecture, Agentic Chaos is the resilience
and failure-validation reference implementation for the **AI Operations
Workflow Specification**. It injects, validates, tests, and proves resilience,
while keeping its workflow artifacts compatible with the same shared
operational model used by AgenticLens, the MCP layer, and the future
Control Tower control plane.

If you also use AgenticLens, an optional integration lets you merge chaos
events straight into an AgenticLens `Workflow`, so `agenticlens analyze`
reports on cost/latency and chaos impact together — see
[Optional: AgenticLens Integration](#optional-agenticlens-integration) below.
Neither package imports the other at the core level; the two are independent
tools that happen to compose.

## Status

`agentic-chaos` is early-stage software. The **LLM Chaos Toolkit** (v0.1),
**Agent Failure Injector** (v0.2), **Fidelity Judges & Handoff Chaos**
(`v0.3.0`), and **Prompt/Model Drift Detector** (`v0.4.0`) are available.
See [ROADMAP.md](ROADMAP.md) for the full plan.

### What's Next

- **Structured experiment reports** — every chaos run emits a report with
  hypothesis, injection point provenance, observed behavior, and verdict
- **Synthetic test scenarios** — prebuilt known-bad agent behaviors for
  consistent resilience validation
- **Memory decay** — progressive corruption for long-running shared state
- **Scheduled drift checks** — snapshot prompts/models/outputs and detect
  silent changes before production behavior shifts further

## Installation

```bash
pip install agentic-chaos
```

or, from source with `uv`:

```bash
git clone https://github.com/DeepAgentLabs/agentic-chaos.git
cd agentic-chaos
uv sync --extra dev --frozen
```

That's it — no other package required. (If you want the optional AgenticLens
integration too, see [below](#optional-agenticlens-integration).)

`--frozen` matters here: `pyproject.toml` points the (currently unpublished)
`agenticlens` extra at a sibling checkout via `[tool.uv.sources]`, and `uv
sync` without `--frozen` tries to validate/refresh the *entire* lock — every
extra, including ones you didn't ask for — which fails if that sibling
directory doesn't exist. `--frozen` installs straight from the committed
`uv.lock` instead. Drop it (and check out `agenticlens` as a sibling
directory) only if you're working on the optional integration itself — see
[Development](#development).

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

Two options worth knowing about that don't show up in the table above (see
[`examples/chaos_advanced_faults_demo.py`](examples/chaos_advanced_faults_demo.py)
for both, runnable):

- `TokenTimeoutFault(mode="delay")` — the call still succeeds, just late,
  instead of raising `TokenTimeoutError`. Recorded outcome is `"delayed"`.
  Useful for testing whether a slow-but-successful call degrades UX on its
  own, separate from outright failure.
- `SilentDegradationFault(degrade_fn=my_fn)` — swap in your own corruption
  logic (`my_fn(result) -> corrupted_result`) instead of the built-in text
  garbler, e.g. to simulate a narrower, more realistic bug than wholesale
  noise.

## CLI Reference

```bash
# Run a script with LLM-level chaos active and print a chaos-events report.
agentic-chaos chaos run my_app.py --inject token_timeout,rate_limit_storm

# Same, saving the resulting standalone report for later inspection.
agentic-chaos chaos run my_app.py --inject silent_degradation --save chaos_run.json

# Run a script with agent-level faults.
agentic-chaos agent run my_agent.py --inject tool_failure,memory_corruption --save report.json

# Run a script with edge-scoped handoff chaos.
agentic-chaos agent run my_agent.py --inject handoff_corruption --save report.json

# Save a drift baseline, then compare a current run against it.
agentic-chaos drift snapshot --name support-agent --save baseline.json --prompt-file prompt.txt --model gpt-5-mini --model-fingerprint fp-a
agentic-chaos drift compare baseline.json --prompt-file prompt.txt --output-file answer.txt --model gpt-5-mini --model-fingerprint fp-b --save drift_report.json

# List all available fault types (v0.1 + v0.3).
agentic-chaos chaos list-faults
```

`agentic-chaos drift compare` exits with code `2` when drift is detected, so
it can fail a CI job while still writing a JSON report when emission rules
allow it.

## Drift Detector (v0.4.0)

Capture a baseline snapshot locally:

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

Compare a current run against that baseline:

```bash
agentic-chaos drift compare baseline.json \
  --prompt-file prompt.txt \
  --output-file current_output.txt \
  --retrieval-file retrieval.txt \
  --model gpt-5-mini \
  --model-fingerprint provider-fp-002 \
  --save drift_report.json
```

The drift module checks four signal types:

- Prompt drift via hash and inline diff metadata.
- Model drift via model name, provider fingerprint, and embedding-model metadata.
- Output drift via a lightweight text-distance score against the baseline.
- Retrieval drift via set-distance on fixed retrieval results.

Repeated scheduled runs can stay quiet until something actually changes:

```bash
agentic-chaos drift compare baseline.json \
  --prompt-file prompt.txt \
  --output-file current_output.txt \
  --save drift_report.json \
  --state-path .agentic-chaos/drift-state.json \
  --cooldown-minutes 1440 \
  --emit-only-on-change
```

### Scheduled CI Example

```yaml
name: Drift Check

on:
  schedule:
    - cron: "0 */6 * * *"
  workflow_dispatch:

jobs:
  drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --extra dev --frozen
      - run: |
          uv run agentic-chaos drift compare baselines/support-agent.json \
            --prompt-file prompts/support.txt \
            --output-file artifacts/latest-output.txt \
            --save artifacts/drift_report.json \
            --state-path artifacts/drift_state.json \
            --cooldown-minutes 1440 \
            --emit-only-on-change
```

## Agent Failure Injector (v0.2)

Three agent-level fault types for testing multi-agent resilience:

| Fault | `--inject` name | What it does |
| --- | --- | --- |
| Tool-call failure | `tool_failure` | Forces a tool call to error (`"error"`), timeout (`"timeout"`), or return null (`"empty"`). Use `tool_name="search"` to target a specific tool; `None` targets all. |
| Memory corruption | `memory_corruption` | Corrupts shared agent state: `"truncate"` cuts to half, `"inject"` inserts garbage, `"garble"` replaces text with random letters, and `"decay"` progressively worsens state across turns. |
| Infinite loop | `infinite_loop` | Replaces the agent's return value with a "continue" signal for `force_turns` calls, then passes through. Tests whether your agent has turn-limit safeguards. |
| Handoff corruption | `handoff_corruption` | Targets a topology edge instead of a node: `"corrupt"` garbles the payload in transit, `"drop"` prevents delivery, and `"delay"` arrives late. |

## Fidelity Judges (v0.3.0)

Fidelity judges answer the question the raw fault event cannot: did the
corrupted output actually get worse?

```python
from agentic_chaos import HeuristicJudge, SilentDegradationFault, chaos_call, chaos_session, fidelity_session

with fidelity_session(HeuristicJudge()):
    with chaos_session([SilentDegradationFault()]) as session:
        answer = chaos_call(agent.answer, "What changed?", faults=["silent_degradation"])

print(session.events[0].fidelity_score)  # 0.0 - 1.0
```

The zero-dependency `HeuristicJudge` ships in-core. `DeepEvalJudge` and
`PydanticEvalsJudge` are lightweight adapters around already-constructed
external evaluator objects, so the base package still has no hard dependency
on any eval framework.

### wrap_tool() / wrap_node() + TopologyTracker

Wrap tool and node functions for transparent chaos injection and topology
recording:

```python
from agentic_chaos import (
    ToolCallFailureFault, TopologyTracker, chaos_session, wrap_tool
)

tracker = TopologyTracker()
tracker.register_node("SupportAgent", type="agent")

search = wrap_tool(search_fn, tool_name="search", tracker=tracker, caller_node="SupportAgent")
refund = wrap_tool(refund_fn, tool_name="refund", tracker=tracker, caller_node="SupportAgent")

with chaos_session([ToolCallFailureFault(tool_name="search")]):
    search("order #123")   # fault fires — tool_name matches
    refund("123")           # passes through — different tool

print(tracker.topology.as_json())  # nodes + edges
```

## Examples

| Script | Needs | Shows |
| --- | --- | --- |
| [`examples/chaos_customer_support_demo.py`](examples/chaos_customer_support_demo.py) | nothing but `agentic_chaos` | All three v0.1 faults' default behavior in one flow: a rate-limit storm the app retries through and recovers from, a token timeout it doesn't handle (fails outright), and a silent degradation (normal-looking call, corrupted output). |
| [`examples/chaos_advanced_faults_demo.py`](examples/chaos_advanced_faults_demo.py) | nothing but `agentic_chaos` | `TokenTimeoutFault(mode="delay")` and a custom `SilentDegradationFault(degrade_fn=...)`. |
| [`examples/chaos_agent_failure_demo.py`](examples/chaos_agent_failure_demo.py) | nothing but `agentic_chaos` | All three v0.2 agent faults: tool-call failure, memory corruption, infinite loop. Plus `wrap_tool()` and `TopologyTracker`. |
| [`examples/chaos_handoff_and_judges_demo.py`](examples/chaos_handoff_and_judges_demo.py) | nothing but `agentic_chaos` | Edge-scoped handoff corruption plus a manual baseline capture that lets `fidelity_session()` score the recorded event safely for a pure downstream function. |
| [`examples/drift_detection_demo.py`](examples/drift_detection_demo.py) | nothing but `agentic_chaos` | Creates a drift baseline and current snapshot, compares them, and writes a drift report JSON. |
| [`examples/chaos_with_agenticlens_demo.py`](examples/chaos_with_agenticlens_demo.py) | `agentic-chaos[agenticlens]` | The optional integration: `attach_events()` + `step_kwargs()` merging chaos events onto a real AgenticLens `Workflow`. |

Run any of them directly (`uv run python examples/...`), or the first two
under the CLI:

```bash
uv run agentic-chaos chaos run examples/chaos_customer_support_demo.py \
    --inject rate_limit_storm,token_timeout,silent_degradation --save /tmp/chaos_run.json
```

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

A `Makefile` provides shorthand for common tasks:

```bash
make install     # install dev dependencies
make check       # run all quality gates (lint + format + typecheck + test)
make test-cov    # tests with coverage report
make help        # list all available targets
```

Without a sibling `agenticlens` checkout, use `--frozen` (see
[Installation](#installation) for why):

```bash
uv sync --extra dev --frozen
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format .
uv run --frozen mypy
```

Tests covering `agentic_chaos.integrations.agenticlens` skip automatically if
`agenticlens` isn't installed. To run the full suite including those, clone
`agenticlens` as a sibling directory and sync with the optional extra
(dropping `--frozen`, since now you *want* the lock to pick it up):

```bash
git clone https://github.com/DeepAgentLabs/agenticlens.git ../agenticlens
uv sync --extra dev --extra agenticlens
uv run pytest
```

(see [`[tool.uv.sources]`](pyproject.toml) for the local sibling-checkout override
used until `agenticlens` publishes a release with `chaos_events` support).

## License

MIT — see [LICENSE](LICENSE).
