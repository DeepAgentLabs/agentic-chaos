# FinAssure: Execution Plan
**A reliability harness for agentic financial decisioning, built on AgenticLens and Agentic Chaos**

Working name: *FinAssure*. Domain: fintech. First packs: loan underwriting (deep) and KYC onboarding (lighter). Data: synthetic only.

---

## 1. Goal and success criteria

**Goal:** Prove that a multi-agent financial workflow can fail silently, detect those failures with fault injection and tracing, and block unsafe releases with an automated gate.

**The deliverable is not a lending app.** It is a domain-neutral harness where lending and KYC are two plug-in "workflow packs".

| Success criterion | Target |
|---|---|
| Naive workflow (v1) fails the release gate with specific evidence | Yes |
| Hardened workflow (v2) passes the gate | Yes |
| Second pack (KYC) runs on the same harness with no changes to harness core | Yes |
| Every experiment has a written hypothesis, result, and verdict | 100% |
| Dashboard shows verdict, trace, comparison, and evidence pack | Yes |

## 2. The two tools and where they fit

| Tool | Links | Role in this project |
|---|---|---|
| **AgenticLens** | [Landing page](https://deepagentlabs.io/agenticlens/) · [Docs](https://deepagentlabs.io/agenticlens/docs/) · [GitHub](https://github.com/DeepAgentLabs/agenticlens) | **Measure and judge.** Traces every run, records tokens, cost, and latency, runs evaluation suites, compares v1 vs v2, enforces the release gate, and exports JSON/CSV/Markdown/HTML. |
| **Agentic Chaos** | [GitHub](https://github.com/DeepAgentLabs/agentic-chaos) | **Break things on purpose.** Injects faults into tool calls, LLM calls, agent state, and handoffs, and records a `ChaosEvent` for each. |

Division of labour in one line: **Agentic Chaos creates the failure, AgenticLens records what happened and decides whether it is acceptable.** Their outputs meet through the shared `chaos_events` JSON schema, using the optional `agentic-chaos[agenticlens]` integration (`attach_events`, `step_kwargs`).

> **Verify before building.** Both tools are early-stage. Confirm exact API names against the [docs](https://deepagentlabs.io/agenticlens/docs/) (especially *Evaluation and Release Gates* and *Trace and Comparison*) and the chaos repo's `examples/`. The chaos README says the AgenticLens integration extra was, at the time of reading, pointed at a sibling checkout rather than a published release, so plan to install both from source.

## 3. System architecture

```
 ┌───────────────────────────── Workflow packs (plug-ins) ─────────────────────────────┐
 │  Underwriting pack        KYC onboarding pack        (stretch) AML triage pack       │
 │  agents · tools · oracle · invariants · synthetic case generator                     │
 └───────────────────────────────────────┬─────────────────────────────────────────────┘
                                         │ pack contract
 ┌───────────────────────────────────────▼─────────────────────────────────────────────┐
 │ Harness core (domain-neutral)                                                        │
 │  Scenario loader → Experiment runner ──► Agentic Chaos (chaos_session / wrap_tool)   │
 │                         │               AgenticLens (profile / step / trace)         │
 │                         ▼                                                            │
 │  Evaluator registry (deterministic + LLM judge) → Gate engine → Evidence pack        │
 └───────────────────────────────────────┬─────────────────────────────────────────────┘
                                         │ JSON artifacts + SQLite index
 ┌───────────────────────────────────────▼─────────────────────────────────────────────┐
 │ API (FastAPI)  ◄────────►  Dashboard (React)                                        │
 └──────────────────────────────────────────────────────────────────────────────────────┘
```

### Tech stack
| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Both tools are Python |
| Agent orchestration | Plain Python functions first, optionally LangGraph later | Keeps spans and fault points explicit |
| Package manager | `uv` | Matches the chaos repo |
| Storage | JSON artifacts on disk + SQLite index | Local-first, matches AgenticLens philosophy |
| API | FastAPI | Simple, typed |
| Dashboard | React + Vite + Tailwind + Recharts (fallback: Streamlit for speed) | Rich charts, easy static build |
| CI | GitHub Actions | Runs the gate on every pull request |

## 4. Features and how each is built

### F1. Underwriting workflow pack (v1 naive, v2 hardened)
Agents: **Intake → Document Extraction → Bureau Lookup → Risk Scorer → Compliance Reviewer.**
- Each agent is a Python function wrapped in an AgenticLens `step(...)` with `agent_name`, `agent_role`, and handoff metadata.
- **Bureau Lookup** is a mock API wrapped with `wrap_tool(..., tool_name="bureau_lookup")` so faults can target it.
- **Risk Scorer** uses deterministic rules (DTI, score bands) plus an LLM only for edge-case narrative. Numbers never come from the LLM.
- **v1** trusts every handoff and defaults on missing data. **v2** adds the hardening in F6.

### F2. Deterministic policy oracle (ground truth)
A pure-Python function `oracle(case) -> {approve | refer | decline, reason_factors}`. It defines the correct answer for every synthetic case, so every experiment is scored objectively. No LLM is involved.

### F3. Synthetic data generator
- About 200 applicants: clear approvals, clear declines, and roughly 40% **borderline** cases near thresholds.
- Documents are generated as text (pay stubs, bank statement summaries) with messiness: missing fields, monthly/annual mix-ups.
- A synthetic `group` attribute (e.g. thin-file vs established) supports the fairness view. It is fake and used only for analysis, never as a model input.
- An LLM (F-LLM below) writes document text variants. Seeds are fixed for reproducibility.

### F4. Chaos scenario library
Scenarios are YAML files (this format is ours, not an agentic-chaos feature) mapped to chaos primitives:

| Scenario | Fault | Target |
|---|---|---|
| Bureau outage / empty / timeout | `ToolCallFailureFault` (`error`/`empty`/`timeout`) | `bureau_lookup` |
| Silent income corruption | `SilentDegradationFault(degrade_fn=...)` (halve, drop digit, monthly↔annual) | Extraction output |
| Handoff corruption / drop | `handoff_corruption` (`corrupt`/`drop`) | Extraction → Scorer edge |
| State decay | `memory_corruption` (`truncate`/`inject`/`decay`) | Shared application state |
| Runaway reviewer | `infinite_loop` | Compliance Reviewer |
| LLM throttling | `rate_limit_storm` | Any LLM call |

```yaml
scenario: silent_income_corruption
pack: underwriting
fault: silent_degradation
target: extraction.income
params: {corruption: halve}
hypothesis: "Income cross-check flags the mismatch and escalates to a human"
unsafe_outcomes: [approval_without_verified_income, flip_without_flag]
runs_per_case: 5
```

### F5. Experiment runner
For each scenario × case × run: open a chaos session, run the pack inside an AgenticLens profile, attach chaos events, evaluate, and store artifacts. Illustrative sketch (confirm real signatures first):

```python
for sc in scenarios:
    for case in cases:
        for _ in range(sc.runs_per_case):
            with chaos_session(sc.faults) as session:
                with profile(f"{pack.name}:{version}:{sc.id}") as wf:
                    outcome = pack.run(case)
                attach_events(session, wf)
            results.append(evaluate(outcome, pack.oracle(case), wf, session))
```
Runs are repeated because LLM behaviour varies. Report **rates**, not single results.

### F6. Hardening layer (v2)
- Schema validation at every handoff (types, ranges, required fields).
- Income cross-check: stated income vs. bank-statement deposits.
- Missing or null data means **refer to human**, never a default.
- Retry cap with backoff for rate limits and timeouts.
- Turn limit for reviewer loops.
- Reason-code generator that reads the scorer's actual factor list, not free text.

### F7. Human-in-the-loop (HITL) gate
Any refer/escalate outcome goes to a simulated reviewer queue. The reviewer is a scripted function with a configurable accuracy, and its assumptions are stated in the report. Escalation is counted as a **safe** outcome, but its rate is tracked so the system cannot pass by escalating everything.

### F8. Evaluator suite (AgenticLens evaluation framework)
| Evaluator | Type | Checks |
|---|---|---|
| Decision consistency | Deterministic | Clean-run decision equals oracle |
| Chaos-decision stability | Deterministic | Faulted decision equals clean decision, or run is flagged/escalated |
| Required tools called | Trace-aware | `bureau_lookup` present in trace before any approval |
| Unsupported approval | Deterministic, **hard-fail** | Approval without valid bureau result or verified income |
| Reason fidelity | LLM judge | Adverse-action reasons are grounded in actual factors |
| Fidelity score | Chaos `HeuristicJudge` | Text degradation severity (text fields only) |
| Latency / cost thresholds | Operational | From AgenticLens traces |
| Disparate resilience | Deterministic | Silent-failure rate difference across synthetic groups |

### F9. Release gate
```yaml
gate:
  min_average_score: 0.90
  hard_fail: [unsupported_approval > 0]
  max_silent_failure_rate: 0.02
  min_safe_degradation_rate: 0.95
  max_escalation_rate: 0.35      # stops "escalate everything" hardening
  max_p95_latency_ms: 4000
  max_cost_per_application_usd: 0.05
```
Enforced with the AgenticLens gate command in CI, so a failing gate blocks the pull request. Thresholds are starting points to tune after v1 results.

### F10. Version comparison
AgenticLens comparison of v1 vs v2 across success, tokens, latency, cost, variability, and regression deltas, plus the harness's own silent-failure and safe-degradation deltas.

### F11. Second pack: KYC onboarding
Agents: **Identity Check → Sanctions/PEP Screening → Risk Rating → Reviewer.** Reuses the same fault vocabulary (sanctions-list outage, altered name field, dropped screening handoff). Purpose: prove genericity. No harness core changes allowed.

### F12. Evidence pack generator
One command produces a Markdown/HTML report per release: scenario list with hypotheses, per-scenario results, gate verdict, trace links, cost and latency, known limitations, and a mapping of experiments to resilience-testing and human-oversight themes (DORA-style scenario testing, AI Act-style oversight). It is worded as *mapping*, not certification.

### F13. CI integration
GitHub Action: run a fast smoke subset on every pull request, the full matrix nightly, and fail the build if the gate fails.

## 5. How LLMs are used

LLMs are used where language matters and never where correctness must be guaranteed.

| Purpose | Suggested model | Notes |
|---|---|---|
| Intake and Document Extraction agents | A small, fast model (e.g. Claude Haiku 4.5) | High volume, structured output, low cost |
| Compliance Reviewer and edge-case narrative | A mid-tier model (e.g. Claude Sonnet 5.5) | Better reasoning for policy text |
| **LLM judge** (reason fidelity) | A **different, stronger model or provider** (e.g. Claude Opus 5.5) | Avoids a model grading its own family's output |
| Synthetic document generation | Any mid-tier model | Run once offline, cache outputs |
| Evidence-pack narrative summary | Mid-tier model, optional | Summarizes computed numbers only |

Rules:
1. **Numbers and decisions come from code, not LLMs.** The policy oracle and scorer arithmetic are deterministic.
2. Structured (JSON-schema) outputs with validation. Malformed output counts as a failure the harness records.
3. Temperature 0 for agents and judge. Fixed seeds for data.
4. The judge receives the actual factor list and the stated reason, and returns a score plus rationale. It is registered in the AgenticLens `EvaluatorRegistry` as a provider-neutral judge.
5. Spot-check about 30 judge outputs by hand and report the agreement rate.
6. Confirm current model IDs and pricing in Anthropic's docs before running, and cache LLM responses during development to control cost.

## 6. Dashboard

**Purpose:** answer three questions in order: *Can we ship? Why or why not? What changed?*

**Data source:** the API reads run artifacts (AgenticLens JSON, chaos reports, evaluation reports) and a SQLite index. No hosted backend beyond your own machine.

### Pages and components

| # | Page | Components |
|---|---|---|
| 1 | **Overview** | Release verdict banner (PASS/FAIL with reason), KPI tiles (silent-failure rate, safe-degradation rate, unsupported approvals, escalation rate, cost/app, p95 latency), score trend by release, gate-rule checklist |
| 2 | **Experiment matrix** | Heatmap (scenario × pack version, colour = silent-failure rate), filter bar (pack, version, fault type), hypothesis-vs-verdict table |
| 3 | **Run explorer** | Run list, trace tree or waterfall of agent spans, chaos-event markers on the affected step, token/cost/latency per span, raw JSON drawer |
| 4 | **Compare v1 vs v2** | Delta table with regression flags, before/after bars for silent-failure and cost, hardening-overhead card |
| 5 | **Decision audit** | Case inspector: inputs, oracle answer, system answer, policy version, reason codes vs. actual factors, human-review outcome |
| 6 | **Fairness / disparate resilience** | Grouped bars of failure rate by synthetic group and scenario, gap threshold line |
| 7 | **Topology** | Agent graph (nodes/edges from `TopologyTracker`) with fault-impact colouring |
| 8 | **Cost & performance** | Tokens by agent, cost per application, latency distribution |
| 9 | **Scenario launcher** | Scenario picker, parameter form, run button, live progress |
| 10 | **Evidence pack** | Generate/download report (HTML, Markdown, JSON, CSV) |

### Overview wireframe

```
┌──────────────────────────────────────────────────────────────────────────┐
│ FinAssure   Pack: [Underwriting ▾]  Version: [v2 ▾]  Compare: [v1 ▾]     │
├──────────────────────────────────────────────────────────────────────────┤
│  ● RELEASE GATE: PASSED   score 0.93 (req 0.90)  · 0 unsupported approvals│
├───────────┬───────────┬───────────┬───────────┬───────────┬──────────────┤
│ Silent    │ Safe      │ Unsupp.   │ Escalation│ Cost/app  │ p95 latency  │
│ failure   │ degrad.   │ approvals │ rate      │           │              │
│ 1.4%      │ 96.8%     │ 0         │ 28%       │ $0.031    │ 3.2 s        │
├───────────┴───────────┴───────────┴───────────┴───────────┴──────────────┤
│ Score trend by release (line)          │ Gate rules (✓/✗ checklist)      │
│  ▁▂▃▅▆▇  v0.1 → v2                     │ ✓ silent ≤ 2%   ✓ hard-fail = 0 │
├────────────────────────────────────────┴─────────────────────────────────┤
│ Experiment heatmap: scenarios (rows) × versions (cols)                   │
│ bureau_outage      [■ v1 red] [■ v2 green]                               │
│ income_corruption  [■ v1 red] [■ v2 green]                               │
│ handoff_drop       [■ v1 amber][■ v2 green]                              │
└──────────────────────────────────────────────────────────────────────────┘
```
Values above are placeholders, not results. Design language: light and dark themes, green/amber/red used only for gate status, monospace for IDs and traces.

### API endpoints (FastAPI)
`GET /releases`, `GET /experiments`, `GET /runs/{id}`, `GET /runs/{id}/trace`, `GET /compare?a=&b=`, `GET /cases/{id}`, `GET /fairness`, `POST /experiments/run`, `POST /evidence-pack`.

## 7. Timeline (6 weeks)

| Week | Work | Exit check |
|---|---|---|
| 1 | Repo setup, synthetic generator, policy oracle, clean underwriting v1 with AgenticLens spans | Clean run matches oracle on all cases |
| 2 | Agentic Chaos wiring (`wrap_tool`, sessions, degrade functions), scenario loader, runner | Each scenario produces chaos events in traces |
| 3 | Evaluators, LLM judge, gate, v1 failure report | Gate fails v1 with specific evidence |
| 4 | Hardening v2, comparison, HITL queue | Gate passes v2, overhead measured |
| 5 | Dashboard (pages 1–5, API) | Verdict, matrix, explorer, compare working |
| 6 | KYC pack, fairness and topology pages, evidence pack, CI, README, demo | KYC runs with zero core changes; 5-minute demo rehearsed |

## 8. Testing the harness itself
- Unit tests for oracle, generator, degrade functions, gate logic.
- A "known-bad" fixture workflow that must always fail the gate, and a "known-good" one that must pass, to prove the gate itself works.
- Reproducibility test: same seed and cached LLM outputs produce identical results.

## 9. Risks and mitigations
| Risk | Mitigation |
|---|---|
| Tool APIs change (early-stage) | Pin versions, isolate behind a thin adapter module |
| LLM nondeterminism | Repeated runs, report rates with confidence ranges, cached responses |
| Judge bias or error | Different-family judge, manual spot checks, deterministic checks first |
| Scope creep | Two packs only; AML triage is stretch |
| API cost | Small model for high-volume steps, caching, smoke subset in CI |
| Misreading results as real credit or compliance advice | Clear disclaimers, synthetic data only, no fairness or compliance certification claims |

## 10. Demo script (5 minutes)
1. Show v1 run in the trace explorer: looks healthy.
2. Inject silent income corruption: decision flips, nothing alerts.
3. Run the matrix: gate fails v1 with named evidence.
4. Show v2 hardening and rerun: gate passes.
5. Compare view: reliability gained vs. cost and latency added.
6. Switch to the KYC pack on the same dashboard to show it is generic.

## 11. Open items to confirm before Week 1
- Exact AgenticLens evaluation-suite and gate configuration format.
- Whether span metadata can carry a policy version and input hashes.
- Installable versions of both tools and the integration extra.
- Current LLM model IDs, pricing, and rate limits.
- Whether the project needs an India-specific or EU-specific regulatory framing (verify any regulatory claims from primary sources before citing).
