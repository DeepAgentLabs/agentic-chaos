# Integrate with your workflow

Reference examples below show API composition and configuration fragments. Start with the complete quickstart before adapting these to your application.

## AgenticLens

[AgenticLens](https://github.com/DeepAgentLabs/agenticlens) profiles cost and latency of LLM workflows. The optional integration lets `agenticlens analyze` report chaos impact alongside that profile.

"No code dependency in either direction"

Only `agentic_chaos.integrations.agenticlens` touches AgenticLens, and only when you import it yourself. `chaos_call()`, `chaos_session()` and the CLI never import it. The two packages interoperate through a shared JSON shape (the `chaos_events` field, workflow schema the documented release).

## Install

```
pip install agentic-chaos[agenticlens]
```

"Unpublished extra"

In the source repository the `agenticlens` extra points at a sibling checkout through `[tool.uv.sources]` until AgenticLens publishes a release with `chaos_events` support. See [Troubleshooting](../troubleshooting.md#uv-sync-fails-because-of-the-agenticlens-extra).

## Usage

Two helpers do the work:

- `step_kwargs(s)` returns the `step_id` / `step_name` keyword arguments for the current AgenticLens step, so the chaos event is correlated to it.
- `attach_events(session, workflow)` copies the events recorded by the chaos session onto the AgenticLens `Workflow`.

```
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

Then analyze the exported workflow:

```
agenticlens analyze workflow.json
```

Example output:

```
Optimization Suggestions
  * Chaos impact: token_timeout on 'Retriever'
    -- Injected fault 'token_timeout' hit step 'Retriever' 1 time and the call
       raised an error each time (call hung for 2.0s then timed out). ... (~0 tokens)
```

A runnable version is in [`examples/chaos_with_agenticlens_demo.py`](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/examples/chaos_with_agenticlens_demo.py).

## Data flow

```
flowchart LR
    A[chaos_session] -->|ChaosEvent| B[attach_events]
    C[AgenticLens profile / step] -->|step_kwargs| D[chaos_call]
    D --> A
    B --> E[Workflow.chaos_events]
    E --> F[JSONExporter]
    F --> G[agenticlens analyze]
```

## Fidelity judge adapters

Fidelity judges score whether corrupted output actually got worse. See [Features](../features.md) for the full concept.

- `HeuristicJudge` ships in-core with zero dependencies.
- `DeepEvalJudge` and `PydanticEvalsJudge` are lightweight adapters around **already-constructed** external evaluator objects. Agentic Chaos does not install or import those frameworks for you, so the base package keeps no hard dependency on any eval framework.

```
from agentic_chaos import SilentDegradationFault, chaos_call, chaos_session, fidelity_session

# my_judge is a DeepEvalJudge or PydanticEvalsJudge wrapping an evaluator you built
with fidelity_session(my_judge):
    with chaos_session([SilentDegradationFault()]) as session:
        answer = chaos_call(agent.answer, "What changed?", faults=["silent_degradation"])

print(session.events[0].fidelity_score)
```

Check the [API Reference](../api-reference.md) for the exact constructor arguments of each adapter.

## Any SDK or framework

Because Agentic Chaos operates on plain callables, it works with any client library or orchestration framework (OpenAI, Anthropic, LangChain, LlamaIndex, custom agents, and so on). Wrap the call that you want to make fragile:

```
from agentic_chaos.chaos import chaos_call

# Any callable works: an SDK method, a retriever, a tool function, a lambda
response = chaos_call(client.messages.create, faults=["rate_limit_storm"], model="...", messages=[...])
```

For agent frameworks, wrap tools and graph nodes instead:

```
from agentic_chaos import wrap_tool, wrap_node, TopologyTracker

tracker = TopologyTracker()
tracker.register_node("SupportAgent", type="agent")

search = wrap_tool(search_fn, tool_name="search", tracker=tracker, caller_node="SupportAgent")
```

Positional and keyword arguments are forwarded unchanged to the wrapped function.

## Continuous integration

The CLI exits after running your script, so it can be used in CI to save a report as a build artifact:

```
agentic-chaos chaos run my_app.py --inject token_timeout,rate_limit_storm --save chaos_run.json
```

For scheduled drift checks (the command exits with code `2` on drift):

```
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

See [Output Formats](../output-formats.md) for the report structure and [CLI Reference](../cli-reference.md) for all options.
