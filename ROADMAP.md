# agentic-chaos — Roadmap & Architecture

## Release Status

- **v0.1** ✅ Complete — LLM Chaos Toolkit (3 faults, CLI, AgenticLens adapter)
- **v0.2** ✅ Complete — Agent Failure Injector (3 agent faults, topology tracking, LangGraph adapter) — shipped 2026-07-13
- **v0.3** 🚧 Planned — Prompt/Model Drift Detector
- **v0.4** 🚧 Planned — Streaming Faults, Provider Patching & Chaos Profiles
- **v0.5** 🚧 Planned — Pytest Plugin & Assertions
- **v0.6** 🚧 Planned — Fault Cascades, Adaptive Intensity & Response Poisoning
- **v0.7** 🚧 Planned — Chaos Workflows, Declarative Experiments & Explosion Radius
- **v0.8** 🚧 Planned — Resilience Probes & Resilience Score
- **v0.9** 🚧 Planned — ChaosHub (Shared Experiment Registry)

---

> **Update:** `agentic-chaos` is a standalone package with **no required
> dependency on `agenticlens`** (or vice versa) -- `pip install agentic-chaos`
> works against any plain Python callable with nothing else installed. The
> "shared workflow.json format" described below is real, but it's an
> *optional* integration (`pip install agentic-chaos[agenticlens]`,
> `agentic_chaos.integrations.agenticlens`), not a hard dependency baked into
> either package's core. See the README's Installation and "Optional:
> AgenticLens Integration" sections for the current shape. The rest of this
> document is the original architecture plan and is still directionally
> accurate, but written from before that decoupling.

## What We're Building

**One new package**, `agentic-chaos`, that sits alongside your existing
`agenticlens` (profiler/reporting engine — already built, extended only
additively for interop: a `chaos_events` field and a `ChaosImpactRecommender`).

`agentic-chaos` contains **three feature modules** in a single package:

1. **LLM Chaos Toolkit** — inject faults at the single LLM-call level
2. **Agent Failure Injector** — inject faults at the multi-agent orchestration
   level (LangGraph, CrewAI, AutoGen)
3. **Prompt/Model Drift Detector** — snapshot + detect silent drift over time

All three modules write data in AgenticLens's existing `workflow.json` format
(with small, additive schema extensions), so your existing `agenticlens`
package can analyze and report on all of it without you rebuilding any
reporting/cost logic. `agenticlens` becomes the shared "brain"; `agentic-chaos`
is the one new tool that produces richer data for it to analyze.

```
                    ┌───────────────────────────┐
                    │   workflow.json format    │
                    │  (shared data contract)   │
                    └─────────────┬─────────────┘
                 ┌────────────────┴─────────────────┐
                 │                                  │
           agentic-chaos                         agenticlens
     (ONE package, 3 modules:                (existing — profiler,
      chaos / agent-guard /                   cost engine, reporting,
      driftwatch submodules)                  recommendations)
```

---

## Package Layout

```
agentic-chaos/
  src/agentic-chaos/
    chaos/            # Module 1: LLM Chaos Toolkit
      faults.py       # TokenTimeout, RateLimitStorm, SilentDegradation, etc.
      inject.py
    agents/           # Module 2: Agent Failure Injector
      langgraph.py    # framework-specific adapters
      crewai.py
      autogen.py
      faults.py       # ToolFailure, MemoryCorruption, InfiniteLoop
    drift/            # Module 3: Prompt/Model Drift Detector
      snapshot.py
      compare.py
    cli/              # single CLI, subcommands per module
    models/           # schema extensions to workflow.json (chaos_events, etc.)
```

One repo, one PyPI package (`pip install agentic-chaos`), one CLI with
subcommands — not three separate installs.

---

## CLI Shape (single tool, three subcommands)

```bash
# Module 1: LLM-level chaos
agentic-chaos chaos run my_app.py --inject token_timeout,rate_limit_storm --save chaos_run.json

# Module 2: Agent-orchestration chaos
agentic-chaos agent run my_graph.py --framework langgraph --inject memory_corruption,tool_failure --save chaos_run.json

# Module 3: Drift detection
agentic-chaos drift snapshot --prompt my_prompt.txt --model gpt-4o-mini --save baseline.json
agentic-chaos drift compare baseline.json --against current_run.json
```

All three save output in the same `workflow.json`-compatible format.

---

## The Interop Piece You Asked About

This is the core value loop, and it works the same way regardless of which
`agentic-chaos` module produced the file:

```bash
# 1. agentic-chaos runs your agent, injects failures, records what happened
agentic-chaos agent run my_agent.py --inject tool_failure,memory_corrupt --save chaos_run.json

# 2. AgenticLens (already built) analyzes that same file
agenticlens analyze chaos_run.json
```

```
Chaos Impact Report
  * Tool failure injected at step "Retriever" → agent retried 3x, +$0.04 cost
  * Memory corruption at step "Planner" → agent hallucinated fallback answer
  * Total cost impact under failure: +140%
  * Recovery: FAILED (no graceful degradation detected)
```

How this works under the hood:
- `agentic-chaos` injects a fault (delays a call, kills a tool, corrupts a memory
  field) and logs what happened into a `chaos_events` array — which step was
  hit, what fault type, and how the app responded (retried / errored /
  returned degraded output).
- This `chaos_events` array is an **additive extension** to the same
  `workflow.json` your `step()`/`profile()` context managers already produce.
- AgenticLens needs only a **thin adapter**: one new recommender rule
  (`ChaosImpactRecommender`) that reads `chaos_events` and correlates them
  against the existing cost/latency data it already computes. You're not
  rebuilding the reporting engine — you're extending it with one new rule set.
- The drift module (Module 3) plugs into the same export layer too — a
  `DriftRecommender` that reuses AgenticLens's existing Markdown/JSON/CSV
  exporters.

Net effect: **one new package, one small adapter change in AgenticLens**, and
you get chaos reports, agent-resilience reports, and drift reports all coming
out of the analysis tool you've already built.

---

## Build Order (within the single `agentic-chaos` package)

Build the three modules in this order — each is releasable as a **minor
version bump** of the same package, so you get incremental PyPI releases
(good for showing sustained activity/impact) without splitting into separate
repos.

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
- [ ] AgenticLens `AgentResilienceRecommender` adapter + resilience score
- [x] README section + 1 example (LangGraph multi-agent demo) + demo GIF

### v0.3 — Prompt/Model Drift Detector (`agentic-chaos.drift`)
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

### v0.4 — Streaming Faults, Provider Patching & Chaos Profiles

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

### v0.5 — Pytest Plugin & Assertions

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

**Built-in assertions (pass/fail contracts):**
- `CompletesWithin(timeout_s)` — call finishes within time budget
- `NoUnhandledError()` — no unhandled exceptions escaped
- `MaxRetries(n)` — agent didn't exceed retry limit
- `RecoveredAfterFailure()` — agent produced a valid result despite injected fault
- `MaxCostImpact(factor)` — cost under chaos didn't exceed N× baseline

**Deliverables:**
- [ ] `pytest-agentic-chaos` plugin (separate small package or entry point)
- [ ] 5 assertion classes in `agentic_chaos.assertions`
- [ ] `--chaos` pytest flag for opt-in activation
- [ ] README section + CI example (GitHub Actions) + demo GIF

### v0.6 — Fault Cascades, Adaptive Intensity & Response Poisoning

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

### v0.7 — Chaos Workflows, Declarative Experiments & Explosion Radius

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

**Deliverables:**
- [ ] `agentic_chaos.workflows` module (`ChaosWorkflow`, `Step`, `HealthCheck`)
- [ ] `agentic-chaos chaos workflow run` CLI subcommand
- [ ] YAML experiment loader + schema validation
- [ ] `Scope` class for fault targeting (steps, providers, excludes)
- [ ] Cron-based scheduling support for continuous chaos testing
- [ ] README section + workflow example + demo GIF

### v0.8 — Resilience Probes & Resilience Score

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

Key difference from v0.5 assertions: assertions check *during* a chaos run;
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

### v0.9 — ChaosHub (Shared Experiment Registry)

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
- Experiments are standard YAML files (same format as v0.7 declarative experiments)

**Deliverables:**
- [ ] `agentic_chaos.hub` module (list, search, pull, push)
- [ ] `agentic-chaos hub` CLI subcommand group
- [ ] 6+ bundled experiment recipes (RAG, ReAct, multi-agent, support)
- [ ] GitHub-hosted remote registry with contribution workflow
- [ ] `--experiment` flag on `chaos run` to use hub recipes directly
- [ ] README section + "getting started in 30 seconds" guide + demo GIF

---

## Shared Data Contract

Document the `chaos_events`, `agent_topology`, and drift-report extensions as
a proper **spec**, not just implementation detail — `docs/workflow-schema-spec.md`
in the `agenticlens` repo, versioned (`v1.1` chaos_events, `v1.2`
agent_topology, `v1.3` drift). Each `agentic-chaos` module README links to it.

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
| 5 | v0.3 — Drift Detector | 2–4 weeks |
| 6 | PyPI release v0.3, publish the schema spec doc | ongoing |
| 7 | v0.4 — Streaming Faults, Provider Patching & Chaos Profiles | 3–5 weeks |
| 8 | PyPI release v0.4 | ongoing |
| 9 | v0.5 — Pytest Plugin & Assertions | 2–4 weeks |
| 10 | PyPI release v0.5 | ongoing |
| 11 | v0.6 — Fault Cascades, Adaptive Intensity & Response Poisoning | 4–6 weeks |
| 12 | PyPI release v0.6 | ongoing |
| 13 | v0.7 — Chaos Workflows, Declarative Experiments & Explosion Radius | 4–6 weeks |
| 14 | PyPI release v0.7 | ongoing |
| 15 | v0.8 — Resilience Probes & Resilience Score | 3–5 weeks |
| 16 | PyPI release v0.8 | ongoing |
| 17 | v0.9 — ChaosHub (Shared Experiment Registry) | 3–5 weeks |
| 18 | PyPI release v0.9 | ongoing |
| 19 | Blog post / talk: "one schema, one chaos toolkit, full AI-infra reliability stack" | after v0.9 ships |

