# agentic-chaos — Roadmap & Architecture

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
- [ ] `agentic-chaos.agents` module (LangGraph adapter)
- [ ] `agent_topology` schema extension
- [ ] AgenticLens `AgentResilienceRecommender` adapter + resilience score
- [ ] README section + 1 example (LangGraph multi-agent demo) + demo GIF

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
| 7 | Blog post / talk: "one schema, one chaos toolkit, full AI-infra reliability stack" | after v0.3 ships |

