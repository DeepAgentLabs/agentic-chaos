# agentic-chaos — Roadmap & Architecture

## Release Status

- **v0.1** ✅ Complete — LLM Chaos Toolkit (3 faults, CLI, AgenticLens adapter)
- **v0.2** ✅ Complete — Agent Failure Injector (3 agent faults, topology tracking, LangGraph adapter) — shipped 2026-07-13
- **v0.3** ✅ Complete — Fidelity Judges & Handoff Chaos (`v0.3.0`)
- **v0.4** 🚧 Planned — Prompt/Model Drift Detector
- **v0.5** 🚧 Planned — Streaming Faults, Provider Patching & Chaos Profiles
- **v0.6** 🚧 Planned — Pytest Plugin & Assertions
- **v0.7** 🚧 Planned — Fault Cascades, Adaptive Intensity & Response Poisoning
- **v0.8** 🚧 Planned — Chaos Workflows, Declarative Experiments & Explosion Radius
- **v0.9** 🚧 Planned — Resilience Probes & Resilience Score
- **v1.0** 🚧 Planned — ChaosHub (Shared Experiment Registry)

---

## Architecture

`agentic-chaos` is a **standalone** fault-injection toolkit — `pip install
agentic-chaos` works against any plain Python callable with no other package
required. AgenticLens integration is optional (`pip install
agentic-chaos[agenticlens]`).

Within the broader DeepAgentLabs story, the package boundary should stay clear:

- **AgenticLens observes, evaluates, explains, and recommends**
- **Agentic Chaos injects, validates, tests, and proves resilience**

From a developer perspective, `agentic-chaos` exists to answer a simple
question:

`If my agentic AI system is slow, wrong, brittle, or unsafe under stress, can
I prove it before production does?`

That means `agentic-chaos` should stay focused on resilience testing,
failure-mode validation, and recovery evidence rather than absorbing general
observability, governance, or deployment features that belong elsewhere.

For clarity, the package should not invent a separate closed reporting format as
its main output. The canonical artifact for chaos and resilience evidence
should remain the **AI Operations Specification** reference representation.

In practice, that means:

- chaos experiments should be exportable as AI Operations Specification
  artifacts
- resilience findings should attach as additive extensions to `workflow.json`
- any JSON, CLI, report, or future telemetry output should derive from that
  same shared contract

The package should focus on these high-level resilience domains:

- model and provider failure simulation
- tool and API failure simulation
- workflow and orchestration failure simulation
- RAG and knowledge corruption scenarios
- memory corruption and decay
- agent handoff and coordination failures
- safety and policy stress scenarios
- recovery and degraded-mode evidence
- resilience scoring and experiment reporting

The package contains the following modules (shipped and planned):

| Module | Status | Purpose |
|--------|--------|---------|
| `agentic_chaos.chaos` | ✅ Shipped (v0.1) | LLM-level fault injection — `TokenTimeoutFault`, `RateLimitStormFault`, `SilentDegradationFault` |
| `agentic_chaos.agents` | ✅ Shipped (v0.2) | Agent-level fault injection — `ToolCallFailureFault`, `MemoryCorruptionFault`, `InfiniteLoopFault`, LangGraph adapter, topology tracking |
| `agentic_chaos.judges` | ✅ Shipped (v0.3) | Fidelity Judges — LLM-as-judge scoring to determine if corrupted output is actually worse |
| `agentic_chaos.drift` | 🚧 Planned (v0.4) | Prompt/model drift detection — snapshot, compare, detect silent changes |
| `agentic_chaos.integrations` | ✅ Shipped (v0.1) | Optional AgenticLens adapter (`attach_events()`, `step_kwargs()`) |

## Package Layout (current)

```
agentic-chaos/
  src/agentic_chaos/
    chaos/              # LLM Chaos Toolkit (v0.1)
      faults.py         # TokenTimeout, RateLimitStorm, SilentDegradation
      inject.py         # chaos_call()
      context.py        # ChaosSession
      session.py
    agents/             # Agent Failure Injector (v0.2)
      faults.py         # ToolCallFailure, MemoryCorruption, InfiniteLoop
      langgraph.py      # wrap_tool(), wrap_node()
      topology.py       # TopologyTracker, AgentTopology
    drift/              # Placeholder (v0.4)
    integrations/       # Optional adapters
      agenticlens.py    # attach_events(), step_kwargs()
    cli/                # CLI entry point
    models/             # ChaosReport, ChaosEvent, schema extensions
```

One repo, one PyPI package, one CLI with subcommands.

---

## CLI (shipped commands)

```bash
# LLM-level chaos (v0.1)
agentic-chaos chaos run my_app.py --inject token_timeout,rate_limit_storm --save chaos_run.json
agentic-chaos chaos list-faults

# Agent-level chaos (v0.2)
agentic-chaos agent run my_graph.py --framework langgraph --inject memory_corruption,tool_failure --save chaos_run.json
```

## Optional AgenticLens Integration

```bash
# 1. agentic-chaos runs your agent, injects failures, saves a ChaosReport
agentic-chaos agent run my_agent.py --inject tool_failure,memory_corrupt --save chaos_run.json

# 2. AgenticLens analyzes the same file (ChaosReport is workflow.json-compatible)
agenticlens analyze chaos_run.json
```

The `ChaosReport` JSON format is compatible with AgenticLens's `Workflow`
schema — `agenticlens analyze` reads `chaos_events` alongside its normal
cost/latency data. The `ChaosImpactRecommender` (in the agenticlens repo)
reports resilience findings. Neither package imports the other at the core
level.

Developers contributing to `agentic-chaos` should be able to ask:

`How does this fault, experiment, or report extend and export the AI Operations
Specification?`

---

## Build Order (within the single `agentic-chaos` package)

Build the modules in this order — each is releasable as a **minor
version bump** of the same package, so you get incremental PyPI releases
(good for showing sustained activity/impact) without splitting into separate
repos.

## Capability Direction

Over time, the package should evolve around a resilience-testing shape like:

```text
agentic-chaos
├── faults
├── scenarios
├── experiments
├── recovery
├── release-tests
├── conformance-tests
├── benchmarks
└── reports
```

Not all of these need to become top-level modules immediately, but they are the
right long-term categories for the package.

## Developer Journey

The roadmap should match how teams actually harden an agentic AI system:

### Basic hardening

- inject faults into single model calls
- simulate timeouts, rate limits, and silent degradation
- capture evidence from one run

### Workflow hardening

- break tools, memory, and agent loops
- validate retries and fallback behavior
- stress handoffs between agents and workflow steps

### Production hardening

- run repeatable chaos experiments in CI
- measure quality impact, not only failure occurrence
- compare baseline versus chaos runs
- generate resilience evidence and readiness reports

### v0.1 — LLM Chaos Toolkit (`agentic-chaos.chaos`)
Narrowest scope, fastest to ship, most novel gap in the market (Chaos
Mesh/Gremlin don't touch this layer). Also establishes the `chaos_events`
schema extension that Module 2 will reuse.

**Fault types (start with 3):**
- Token-timeout — simulate a hung/slow completion mid-generation
- Rate-limit storm — simulate provider 429s/backoff cascades
- Silent model degradation — same latency/token count, garbage output
  (hardest to detect, highest value)

**Stretch:** partial-stream drop, embedding-store latency spike, vector DB
node kill.

**Deliverables:**
- [x] `agentic-chaos.chaos` module + CLI subcommand
- [x] `chaos_events` schema extension (documented)
- [x] AgenticLens `ChaosImpactRecommender` adapter
- [x] README section + 1 example script
- [ ] demo GIF

### v0.2 — Agent Failure Injector (`agentic-chaos.agents`)
Reuses the fault-injection engine/scheduler built in v0.1. Adds
framework-specific hooks and an `agent_topology` field (which agent talked to
which, memory reads/writes) so reports can speak to resilience at the
workflow level, not just the single-call level.

**Fault types (start with 3):**
- Tool-call failure — force a registered tool to error/timeout/return bad data
- Memory corruption — truncate/inject garbage into shared agent state mid-run
- Infinite loop trigger — force agents to loop past N turns

**Framework support:** LangGraph first (most structured), CrewAI/AutoGen as
stretch goals.

**Deliverables:**
- [x] `agentic-chaos.agents` module (LangGraph adapter)
- [x] `agent_topology` schema extension
- [ ] AgenticLens `AgentResilienceRecommender` adapter + resilience score *(deferred to v0.9)*
- [x] README section + 1 example (LangGraph multi-agent demo) + demo GIF

### v0.2.x — Structured Experiment Reports & Synthetic Scenarios

Enhancements to the shipped foundation — focused on making chaos results
operationally useful rather than adding new fault types.

**Structured experiment reports:**

Every chaos run should emit a report with a clear shape:
- hypothesis (what you expected to break)
- injection point with provenance (which agent, tool, step, and context)
- fault applied
- observed behavior
- recovery outcome
- verdict (recovered / degraded / failed)

This goes beyond "fault fired" into answering "what does this mean for
production readiness?" Reports should be exportable as AI Operations
Specification artifacts.

**Synthetic test scenarios:**

Prebuilt known-bad agent behaviors that validate resilience behavior
consistently:
- agent that always retries until budget exhaustion
- agent that silently drops a required step under load
- agent that enters a handoff loop between two nodes
- agent that succeeds but at 5× expected cost

These serve as regression fixtures and benchmarking baselines for the chaos
toolkit itself.

**Deliverables:**
- [ ] structured `ExperimentReport` model with provenance fields
- [ ] report export to JSON (AI Operations Specification-compatible)
- [ ] 4+ synthetic scenario fixtures in `tests/synthetic/`
- [ ] CLI `--report` flag to emit structured reports
- [ ] README section with report schema example

### v0.3 — Fidelity Judges & Handoff Chaos (`agentic_chaos.judges`, `agentic_chaos.agents` extension)

Slotted directly after the shipped Agent Failure Injector because it closes the
two gaps that matter most the moment you're running multi-agent chaos for
real: knowing whether a corrupted response is *actually* worse, and being
able to break the **link** between two agents, not just an agent itself.

**Fidelity Judges — is "different" actually "worse"?**

`SilentDegradationFault` already corrupts output undetectably by cost/latency
telemetry alone — nothing in the existing report says whether the corruption
*mattered*. Fidelity Judges wrap an LLM-as-judge framework and attach a
continuous score to the event, rather than gating a pass/fail test:

```python
from agentic_chaos.judges import DeepEvalJudge, fidelity_session
from deepeval.metrics import GEval

with fidelity_session(DeepEvalJudge(GEval(name="task-completion", criteria="..."))):
    with chaos_session([SilentDegradationFault()]):
        result = chaos_call(agent.answer, question, faults=["silent_degradation"])
```

```
ChaosEvent(fault_type="silent_degradation", outcome="corrupted", fidelity_score=0.31)
```

Unlike a pytest-style assertion, `fidelity_score` is **data** — an additive
`chaos_events` schema field (v1.3) — so the AgenticLens `ChaosImpactRecommender`
can rank faults by how much they actually degraded quality, not merely
whether they fired. Ships with `DeepEvalJudge` and `PydanticEvalsJudge`
adapters.

**Handoff Chaos — corrupt the wire, not the node**

Every fault through v0.2 targets a *node*: a tool call, an LLM call, or an
agent's own memory. Nothing targets the **edge** — the payload one agent
hands to the next, which `TopologyTracker` already models as `AgentEdge`.
`HandoffCorruptionFault` fires on a specific edge, corrupting, delaying, or
dropping the message in transit between two named nodes:

```python
from agentic_chaos.agents import HandoffCorruptionFault

with chaos_session([HandoffCorruptionFault(from_node="Planner", to_node="Executor", mode="drop")]):
    ...
```

Because it's edge-scoped, the resulting `ChaosEvent` records exactly which
link in the topology broke (`edge_id`, `from_node`, `to_node`) — something a
topology-blind fault can't express. Modes: `"corrupt"` (garble the payload),
`"drop"` (message never arrives), `"delay"` (late arrival, tests timeout
handling downstream).

**Memory Decay — corruption as drift, not a single event**

A `mode="decay"` option on the existing `MemoryCorruptionFault`: instead of a
one-shot truncate/inject/garble, corrupts shared state progressively across
`N` turns (`rate` param) — modeling the more realistic long-running-session
failure where state degrades gradually rather than breaking all at once.

**Deliverables:**
- [x] `agentic_chaos.judges` module — `DeepEvalJudge`, `PydanticEvalsJudge`, `fidelity_session()`
- [x] `fidelity_score` schema extension (`chaos_events` v1.3)
- [x] `HandoffCorruptionFault` (`agentic_chaos.agents`) — corrupt/drop/delay modes, edge-scoped
- [x] `MemoryCorruptionFault(mode="decay", rate=...)`
- [ ] AgenticLens `ChaosImpactRecommender` update to weight by `fidelity_score`
- [ ] README section + example + demo GIF

### v0.4 — Prompt/Model Drift Detector (`agentic-chaos.drift`)
Different shape (monitoring/snapshotting vs. one-off fault injection), but
lives in the same package and reuses the same export layer.

**Detects:**
- Prompt template drift — hash/diff of the actual prompt sent
- Model version drift — tracks model fingerprint/version metadata to catch
  silent provider-side swaps
- Output distribution drift — embedding-space distance vs. a stored baseline
  (catches "same everything, different quality")
- Retrieval/embedding drift — flags when an embedding model change shifts
  retrieval results for a fixed test query set

**Deliverables:**
- [ ] `agentic-chaos.drift` module + CLI subcommand
- [ ] Local snapshot/baseline storage (simple JSON to start)
- [ ] AgenticLens `DriftRecommender` adapter
- [ ] README section + example (scheduled drift check in CI) + demo GIF

### v0.5 — Streaming Faults, Provider Patching & Chaos Profiles

Closes the biggest remaining gaps in fault coverage and adoption friction.

**Streaming faults (new fault classes):**
- `StreamCutFault` — terminate a streaming response mid-way through generation
- `StreamHangFault` — hang the stream without sending data (simulates frozen connection)
- `SlowTTFTFault` — delay time-to-first-token to simulate cold-start / queue backup
- `SlowChunksFault` — slow inter-chunk delivery to simulate degraded throughput

**Provider auto-patching (opt-in helpers):**
- `patch_openai(faults=[...])` — monkey-patch the OpenAI client so all calls
  are automatically wrapped; no need to change every call site to `chaos_call()`
- `patch_anthropic(faults=[...])` — same for Anthropic/Claude
- `patch_google(faults=[...])` — same for Google Gemini
- Patches are reversible and scoped to `chaos_session()` lifetime

**Chaos profiles (named presets via `chaos.toml`):**
```toml
[profiles.production-like]
faults = ["rate_limit_storm", "token_timeout"]
probability = 0.1

[profiles.stress-test]
faults = ["rate_limit_storm", "silent_degradation", "token_timeout"]
probability = 0.8
```
```bash
agentic-chaos chaos run my_app.py --profile production-like
```

**Probabilistic triggers:**
- All faults gain a `probability` parameter (0.0–1.0) — fault fires randomly
  per call instead of deterministically, enabling more realistic chaos runs

**Additional LLM faults:**
- `AuthErrorFault` — simulate 401/403 authentication failures
- `ContextLengthFault` — simulate context-length-exceeded errors

**Deliverables:**
- [ ] 4 streaming fault classes
- [ ] Provider patching helpers (OpenAI, Anthropic, Gemini)
- [ ] `chaos.toml` profile loader + `--profile` CLI flag
- [ ] `probability` parameter on all fault classes
- [ ] `AuthErrorFault` + `ContextLengthFault`
- [ ] README section + example + demo GIF

### v0.6 — Pytest Plugin & Assertions

Makes chaos a first-class part of CI/CD — not a separate manual step.

**Pytest plugin (`pytest-agentic-chaos`):**
```python
@pytest.mark.chaos(faults=["rate_limit_storm"], must_recover=True)
def test_agent_handles_rate_limits():
    result = my_agent("What's the weather?")
    assert result is not None
```
```bash
pytest --chaos   # enables chaos markers; without flag, tests run normally
```

**Built-in contracts (pass/fail checks, `agentic_chaos.contracts`):**
- `CompletesWithin(timeout_s)` — call finishes within time budget
- `NoUnhandledError()` — no unhandled exceptions escaped
- `MaxRetries(n)` — agent didn't exceed retry limit
- `RecoveredAfterFailure()` — agent produced a valid result despite injected fault
- `MaxCostImpact(factor)` — cost under chaos didn't exceed N× baseline
- `NoRetryStorm(max_retries_per_window)` — flags cascading retries *across the
  whole topology* within a time window, not just repeated calls from a single
  node — catches the case where a fault on one agent triggers a retry storm
  that ripples through its callers
- `FullTopologyTraversal()` — every node reachable in the `AgentTopology`
  baseline run was actually visited under chaos; catches an agent silently
  short-circuiting a planned step (e.g. the reviewer node never ran) rather
  than just checking the conversation didn't error

Contracts run against a `ChaosReport`/`AgentTopology` after the fact — they
read the same schema AgenticLens consumes, so a contract failure and an
AgenticLens recommendation come from the same data, not two disconnected
checks.

**Deliverables:**
- [ ] `pytest-agentic-chaos` plugin (separate small package or entry point)
- [ ] 7 contract classes in `agentic_chaos.contracts`
- [ ] `--chaos` pytest flag for opt-in activation
- [ ] README section + CI example (GitHub Actions) + demo GIF

### v0.7 — Fault Cascades, Adaptive Intensity & Response Poisoning

Advanced chaos capabilities — models real-world compound failures and
automates threshold discovery.

**Fault cascades (chained failures):**
```python
cascade(
    first=RateLimitStormFault(burst_count=3),
    then=TokenTimeoutFault(hang_seconds=10),
    delay_between=2.0
)
```
Models real production patterns where one failure triggers another (e.g.,
429 storm → timeouts as the queue backs up).

**Adaptive fault intensity (breaking-point finder):**
```python
result = find_breaking_point(
    my_app,
    fault=RateLimitStormFault,
    param="burst_count",
    range=(1, 20),
)
# → "Agent breaks at burst_count=7 (no recovery after 7 consecutive 429s)"
```
Binary-searches fault severity to find the exact threshold where the agent
fails — useful for capacity planning and SLA definition.

**LLM response poisoning (adversarial injection):**
```python
PoisonedResponseFault(
    strategy="confident_wrong",    # wrong answer, high confidence
    # or "partial_hallucination"   # mostly correct, one wrong fact
    # or "format_violation"        # correct content, broken JSON/format
)
```
Tests whether downstream validation/guardrails catch plausible-looking bad
output — more realistic than random text garbling.

**Cost-of-failure estimation (pre-run):**
```bash
agentic-chaos estimate my_app.py --fault rate_limit_storm --retries 3
# → "Estimated cost impact: +$0.12/call (+140%), 3 extra LLM calls"
```

**Deliverables:**
- [ ] `cascade()` API + cascade scheduling engine
- [ ] `find_breaking_point()` binary-search utility
- [ ] `PoisonedResponseFault` with 3 strategies
- [ ] `agentic-chaos estimate` CLI subcommand
- [ ] README section + examples + demo GIF

### v0.8 — Chaos Workflows, Declarative Experiments & Explosion Radius

Inspired by Chaos Mesh's orchestration model — adapted for AI agents instead
of Kubernetes pods.

**Chaos workflows (serial/parallel experiment orchestration):**

Define multi-step chaos *campaigns* with health checks between stages,
modeling progressive failure escalation:
```python
from agentic_chaos.workflows import ChaosWorkflow, Step, HealthCheck

workflow = ChaosWorkflow("resilience-suite", steps=[
    Step("warm-up", faults=[RateLimitStormFault(burst_count=2)]),
    HealthCheck(fn=my_agent, query="Are you working?", expect_success=True),
    Step("escalate", faults=[RateLimitStormFault(burst_count=5), TokenTimeoutFault()]),
    HealthCheck(fn=my_agent, query="Are you working?", expect_success=True),
    Step("full-blast", faults=[cascade(...)]),
])
report = workflow.run(my_app)
```
Workflows compose multiple fault types in sequence with status verification
between stages — models how real outages escalate.

**CLI:**
```bash
agentic-chaos chaos workflow run chaos_workflow.yaml --save report.json
```

**Declarative experiment definitions (YAML):**

Separates experiment *definition* from *execution* so non-developers (SREs,
QA) can author chaos experiments without writing Python:
```yaml
# experiments/rate-limit-recovery.yaml
name: rate-limit-recovery
target: my_app.py
faults:
  - type: rate_limit_storm
    burst_count: 5
    retry_after: 1.0
  - type: token_timeout
    hang_seconds: 3.0
    probability: 0.3
assertions:
  - completes_within: 30
  - max_retries: 5
  - recovered_after_failure: true
schedule:
  cron: "0 2 * * *"  # nightly
```
YAML experiments can be version-controlled alongside application code and
run via CLI or CI.

**Explosion radius control (scoped targeting):**

Scope faults to specific steps, tools, or LLM providers — prevents
accidental chaos in critical paths (safety checks, auth):
```python
RateLimitStormFault(
    burst_count=3,
    scope=Scope(
        steps=["retriever", "planner"],     # only these steps
        providers=["openai"],                # only OpenAI calls
        exclude_steps=["safety_check"],      # never touch this
    )
)
```

**Topology Fuzzer (exploration, not a fixed workflow):**

Rather than fuzzing random faults against a flat call list, `fuzz_topology()`
walks the actual `AgentTopology` graph and weights fault placement by graph
structure — e.g. hitting high-fan-out coordinator nodes more often than leaf
tool calls, since that's where a real cascade is most likely to start:

```python
from agentic_chaos.workflows import fuzz_topology

report = fuzz_topology(my_graph, n=20, scope=Scope(exclude_steps=["safety_check"]))
```

Useful once enough fault types exist (post-cascade, post-handoff-chaos) to
make random combinations worth exploring; complements `find_breaking_point()`
rather than replacing it — one searches a single parameter, the other
explores across the whole graph.

**Deliverables:**
- [ ] `agentic_chaos.workflows` module (`ChaosWorkflow`, `Step`, `HealthCheck`)
- [ ] `agentic-chaos chaos workflow run` CLI subcommand
- [ ] YAML experiment loader + schema validation
- [ ] `Scope` class for fault targeting (steps, providers, excludes)
- [ ] `fuzz_topology()` graph-weighted fuzzer
- [ ] Cron-based scheduling support for continuous chaos testing
- [ ] README section + workflow example + demo GIF

### v0.9 — Resilience Probes & Resilience Score

Inspired by LitmusChaos's resilience probes and scoring — adapted for AI
agents. Moves agentic-chaos from "observe what happened" to "measure how
resilient the agent actually is."

**Resilience probes (reusable steady-state validators):**

Probes are plug-and-play health checks, separate from faults, that verify
agent steady-state *before*, *during*, and *after* chaos injection:
```python
from agentic_chaos.probes import Probe, HttpProbe, ResponseQualityProbe, LatencyProbe

# Define once, reuse across all experiments
probes = [
    HttpProbe(url="http://localhost:8080/health", expect_status=200),
    ResponseQualityProbe(
        fn=my_agent,
        query="What is 2+2?",
        expect_contains="4",
    ),
    LatencyProbe(fn=my_agent, query="Hello", max_ms=3000),
]

# Probes run before, during, and after chaos injection
report = chaos_run(my_app, faults=[...], probes=probes)
# → "Pre-chaos: all probes passed. Post-chaos: ResponseQualityProbe FAILED"
```

Key difference from v0.6 contracts: contracts check *during* a chaos run;
probes check whether the agent **recovered to normal** after chaos stopped.

**Resilience score (quantified 0–100 metric):**

A single number summarizing agent resilience across all experiments — usable
as a CI gate, dashboard metric, and trend tracker:
```
Resilience Report: my_support_agent
═══════════════════════════════════
  Overall Score: 72/100

  Rate-limit recovery:     ██████████░░  85/100  (retried, recovered)
  Token timeout handling:  ████████░░░░  65/100  (recovered but slow)
  Silent degradation:      ██████░░░░░░  50/100  (no detection)
  Tool failure recovery:   █████████░░░  90/100  (graceful fallback)

  Trend: ↑ +8 from last run (was 64)
```

```python
report = chaos_run(my_app, faults=[...], probes=probes)
print(report.resilience_score)  # 72
assert report.resilience_score >= 70  # CI gate
```

Score is computed from: fault recovery rate, probe pass rate, latency impact,
retry efficiency, and cost overhead.

**Deliverables:**
- [ ] `agentic_chaos.probes` module (`Probe`, `HttpProbe`, `ResponseQualityProbe`, `LatencyProbe`)
- [ ] Pre/during/post probe execution lifecycle
- [ ] Resilience score computation engine
- [ ] Score trend tracking (compare against previous runs)
- [ ] Rich terminal report with per-fault breakdown + bar chart
- [ ] `--min-score` CLI flag for CI gating
- [ ] README section + CI example + demo GIF

### v1.0 — ChaosHub (Shared Experiment Registry)

A community-contributed library of pre-built fault recipes for common agent
patterns — lowers the "what should I even test?" barrier.

**CLI:**
```bash
# Browse available experiments
agentic-chaos hub list
agentic-chaos hub search "rag"

# Pull a community experiment
agentic-chaos hub pull rag-retriever-failure
agentic-chaos hub pull react-loop-resilience

# Run it against your app
agentic-chaos chaos run my_app.py --experiment rag-retriever-failure

# Contribute your own
agentic-chaos hub push my_experiment.yaml
```

**Bundled experiment recipes (ships with the package):**

| Recipe | Pattern | Faults injected |
|---|---|---|
| `rag-retriever-failure` | RAG agents | Embedding timeout, vector DB empty results, retriever returns stale data |
| `rag-context-poisoning` | RAG agents | Retrieved context contains contradictory or hallucinated information |
| `react-loop-resilience` | ReAct agents | Tool chain failure mid-reasoning, observation corruption |
| `multi-agent-coordinator-down` | Multi-agent | Coordinator agent timeout, inter-agent message loss |
| `support-escalation-failure` | Customer support | Escalation path failure, knowledge base corruption |
| `api-cascade-storm` | Tool-heavy agents | Multiple tools fail in sequence, simulating downstream outage |

**Architecture:**
- **Local hub**: Bundled YAML experiments shipped with the package (works offline)
- **Remote hub**: GitHub-hosted registry for community contributions (opt-in,
  requires network)
- Experiments are standard YAML files (same format as v0.8 declarative experiments)

**Deliverables:**
- [ ] `agentic_chaos.hub` module (list, search, pull, push)
- [ ] `agentic-chaos hub` CLI subcommand group
- [ ] 6+ bundled experiment recipes (RAG, ReAct, multi-agent, support)
- [ ] GitHub-hosted remote registry with contribution workflow
- [ ] `--experiment` flag on `chaos run` to use hub recipes directly
- [ ] README section + "getting started in 30 seconds" guide + demo GIF

---

## Shared Data Contract

Document the `chaos_events`, `agent_topology`, `fidelity_score`, and
drift-report extensions as a proper **spec**, not just implementation detail —
`docs/workflow-schema-spec.md` in the `agenticlens` repo, versioned (`v1.1`
chaos_events, `v1.2` agent_topology, `v1.3` fidelity_score, `v1.4` drift).
Each `agentic-chaos` module README links to it.

This is what turns "one package with three modules" into a stronger petition
artifact: you're not just shipping a tool, you're the author of the open
schema that ties your whole observability ecosystem together, plus the
reference implementation of it.

---

## Suggested Timeline

| Phase | Deliverable | Approx. effort |
|---|---|---|
| 1 | `agentic-chaos` v0.1 — LLM Chaos Toolkit + CLI + AgenticLens adapter | 2–4 weeks |
| 2 | PyPI release v0.1, README, demo, push for initial GitHub adoption | ongoing |
| 3 | v0.2 — Agent Failure Injector (LangGraph) | 3–5 weeks |
| 4 | PyPI release v0.2 | ongoing |
| 5 | v0.3 — Fidelity Judges & Handoff Chaos | 2–4 weeks |
| 6 | PyPI release v0.3 | ongoing |
| 7 | v0.4 — Drift Detector | 2–4 weeks |
| 8 | PyPI release v0.4, publish the schema spec doc | ongoing |
| 9 | v0.5 — Streaming Faults, Provider Patching & Chaos Profiles | 3–5 weeks |
| 10 | PyPI release v0.5 | ongoing |
| 11 | v0.6 — Pytest Plugin & Assertions | 2–4 weeks |
| 12 | PyPI release v0.6 | ongoing |
| 13 | v0.7 — Fault Cascades, Adaptive Intensity & Response Poisoning | 4–6 weeks |
| 14 | PyPI release v0.7 | ongoing |
| 15 | v0.8 — Chaos Workflows, Declarative Experiments & Explosion Radius | 4–6 weeks |
| 16 | PyPI release v0.8 | ongoing |
| 17 | v0.9 — Resilience Probes & Resilience Score | 3–5 weeks |
| 18 | PyPI release v0.9 | ongoing |
| 19 | v1.0 — ChaosHub (Shared Experiment Registry) | 3–5 weeks |
| 20 | PyPI release v1.0 | ongoing |
| 21 | Blog post / talk: "one schema, one chaos toolkit, full AI-infra reliability stack" | after v1.0 ships |
