# Agentic Chaos

How does the application behave when a dependency fails?

## What it does

Fault injection, experiment reports and resilience evidence, grouped by area below. Each area links to its detailed guide. For runnable commands, see the [developer guide](developer-guide.md).

### 1. LLM-call faults

- **Token timeout**
    - Hangs for `hang_seconds`, then raises `TokenTimeoutError`
    - `mode="delay"` lets the real call finish late instead
- **Rate-limit storm**
    - Fails the first `burst_count` calls with a `retry_after` hint, then clears
- **Silent degradation**
    - Corrupts a successful response's text while latency and token counts stay unchanged
    - Custom corruption with `degrade_fn=`
- **Streaming faults**
    - Cut a stream, hang it, delay the first token or slow every chunk
    - Sync and async streams (`chaos_stream()`, `chaos_astream()`)
- **Provider errors**
    - Authentication errors and context-length overflows, shaped like SDK errors
- **Async calls**
    - `chaos_acall()` with cancellation-aware execution

Guides: [Features](features.md) · [Streaming and async](v0.5.md) ·
[Configuration](configuration.md)

### 2. Agent faults and topology

- **Agent faults**
    - Tool-call failure: error, timeout or empty result, for one tool or all
    - Memory corruption: truncate, inject garbage, garble or decay across turns
    - Infinite loop: forced "continue" signals to test turn limits
    - Handoff corruption: corrupt, drop or delay a payload between two agents
- **Instrumentation**
    - `wrap_tool()` and `wrap_node()` for framework-neutral callables
    - `TopologyTracker` records agent and tool nodes and edges
- **LangGraph**
    - The same wrappers work on LangGraph tools and graph nodes, with no LangGraph dependency

Guides: [Features](features.md#tool-and-node-wrapping-and-topology) ·
[LangGraph adapter](api-reference.md#langgraph-adapter) · [Integrations](integrations.md)

### 3. Advanced chaos

- **Fault cascades**
    - Chain one fault after another with `cascade(first=..., then=..., delay_between=...)`
- **Breaking-point search**
    - `find_breaking_point()` increases fault intensity to find where recovery stops
- **Response poisoning**
    - Confident wrong answers, fabricated references, malformed formats,
      prompt-injection and policy-bypass text (synthetic, never executed)
- **Cost estimates**
    - `agentic-chaos estimate` models retry costs from prices you supply, without running your app

Guides: [v0.7 advanced chaos](v0.7.md)

### 4. Provider patching and profiles

- **Provider patches**
    - `patch_openai()`, `patch_anthropic()` and `patch_google()` inject faults into one real client instance
    - Sync, async and streaming SDK calls; originals restored when the session ends
- **Profiles**
    - Named TOML profiles (`chaos.toml`) for reusable fault sets
    - Seeded probability sampling for repeatable runs

Guides: [v0.5 guide](v0.5.md) · [Configuration](configuration.md)

### 5. Explosion radius

- **Scope**
    - Limit faults to chosen steps or providers with `Scope(...)`
    - Exclusions always win; checked before probability sampling
    - Works on every fault, cascade, workflow step and workflow

Guides: [Scope](v0.8.md#explosion-radius-scope)

### 6. Safety rails

- **Circuit breaker**
    - Limits on recorded cost, failure rate, duration and number of injections
    - Aborts the session and blocks later instrumented calls
- **Dry runs**
    - Preview which faults would fire (target calls still run and can still cost money)
- **Cost recording**
    - `record_cost()` and `record_usage()` with prices you supply; prices are never guessed

Guides: [Safety rails](safety.md)

### 7. Fidelity judges

- **Scoring**
    - A 0–1 score for whether a corrupted output actually got worse
- **Judges**
    - `HeuristicJudge` with no dependencies
    - Adapters for DeepEval and Pydantic Evals evaluators you construct

Guides: [Fidelity judges](features.md#fidelity-judges)

### 8. Contracts and pytest

- **Built-in contracts**
    - Completes within a time limit, no unhandled error, maximum retries,
      recovered after failure, maximum cost impact, no retry storm, full topology traversal
    - Missing evidence is inconclusive and never passes
- **Gates**
    - `--contract` on a CLI run exits 1 unless every contract passes
    - `contracts check` re-checks saved reports
    - Custom contracts by subclassing `Contract`
- **Pytest plugin**
    - `@pytest.mark.chaos` markers, activated with `pytest --chaos`
    - `chaos` fixture, baseline runs and saved reports per test

Guides: [v0.6 contracts and pytest](v0.6.md)

### 9. Resilience probes and score

- **Probes**
    - HTTP, function, response-quality and latency checks
    - Run before, during and after the chaos; a failing "before" probe stops injection
- **Resilience score**
    - A 0–100 score from recovery, probe results, latency and cost evidence
    - Inconclusive when evidence is missing, never invented
- **CI and history**
    - `--min-score` gate
    - Trend history with retention (`score show`, `score history`, `score prune`)

Guides: [v0.9 probes and resilience score](v0.9.md)

### 10. Workflows and experiments

- **Chaos workflows**
    - Multi-stage campaigns from `Step`, `HealthCheck`, `Parallel`, `Suspend` and `Template` stages
    - Human approval gates that can be resumed (`--approve`, `--resume-from`)
- **Declarative experiments**
    - JSON, TOML or YAML documents, linted with `experiment validate` without running targets
- **Scheduling**
    - Previews upcoming runs and prints crontab or GitHub Actions snippets
- **Topology fuzzing**
    - `agent fuzz` places seeded faults across the agent graph, weighted by fan-out
    - Unreached trials are reported, not counted as passes

Guides: [v0.8 workflows](v0.8.md)

### 11. Drift detection

- **Snapshots**
    - Baseline of prompt, model, model fingerprint, output and retrieval results
- **Comparison**
    - `drift compare` flags changes and exits 2 when drift is found
    - Alert cooldowns and emit-on-change controls

Guides: [Drift detector](features.md#drift-detector) ·
[Drift report format](output-formats.md#drift-report-and-state)

### 12. Containment assertions

- **Stop and revoke checks**
    - Verify that nothing was dispatched after an effective stop or revocation
    - In-flight completions and denied attempts handled explicitly
- **Authenticated evidence**
    - Requires a verified, authenticated observation snapshot from AgenticLens
    - Failed, unknown or incomplete evidence cannot pass

Guides: [MCP Phase 6 containment](phase6-containment.md) ·
[API reference](api-reference.md#authenticated-containment-assertions-0100)

### 13. ChaosHub and plugins

- **Recipes**
    - Six bundled scenarios: API cascade storm, multi-agent coordinator down,
      RAG context poisoning, RAG retriever failure, ReAct loop resilience,
      support escalation failure
    - `hub list`, `hub search` and `hub pull`
- **Exchange**
    - Opt-in remote recipes pinned to a full commit SHA; downloading never runs code
- **Fault plugins**
    - Custom faults through the `agentic_chaos.plugins` entry point, loaded only when you ask

Guides: [ChaosHub](v0.11.md)

### 14. Reports and ecosystem interoperability

- **Reports**
    - A `ChaosEvent` for every fault and a standalone JSON `ChaosReport`
    - Workflow, contract, score, fuzz and drift reports
- **AIOS export**
    - `--save-aios` and `to_aios_run()` export a draft AIOS Run
- **Ecosystem**
    - **Lens**: merge chaos events into AgenticLens runs and verify containment evidence
    - **Evals**: owns independent output scoring and release gates
    - **Control Tower**: consumes attributed Chaos evidence
    - **MCP**: the separate MCP package exposes Chaos workflows as tools

Guides: [Output formats](output-formats.md) · [Integrations](integrations.md) ·
[Coordinated readiness](coordinated-v1-readiness.md)

## What you need

A Python callable wrapped with `chaos_call()`, `wrap_tool()` or `wrap_node()`, or an experiment target, plus a fault configuration.

## Start here

Inject a timeout into a local dummy search call: [follow the quickstart](developer-guide.md#quickstart).

## Limits

- Injecting a fault does not prove recovery. Define recovery assertions, probes or contracts.
- Faults are simulated at the Python call boundary. Real network, TLS or provider-side behavior is not reproduced.
- Only wrapped call sites are affected; unwrapped calls are never faulted.
- The resilience score summarizes evidence in the report; it is not a guarantee.
- Not a load-testing tool.

See [Limitations](limitations.md).

## Documentation

- [Developer Guide (simple)](developer-guide.md): short task workflows and a capability index
- [API Reference (detailed)](api-reference.md): exact Python functions, parameters and return values
- [AI Readable Documentation](ai-reference-index.md): the full reference as one file for AI tools, with source declarations
