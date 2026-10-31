# Agentic Chaos

**Fault injection for LLM calls and agentic workflows.**

[![PyPI](https://img.shields.io/pypi/v/agentic-chaos.svg)](https://pypi.org/project/agentic-chaos/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/agentic-chaos.svg)](https://pypi.org/project/agentic-chaos/)

**Current version: 0.4.0**

`agentic-chaos` deliberately breaks your app, with hung completions, provider
rate-limit storms and silently corrupted output, and reports what happened. It is
a standalone toolkit with **no required dependency on any other package**, including
[AgenticLens](https://deepagentlabs.io/agenticlens/docs/). Install it with
`pip install agentic-chaos` and use it against any plain Python callable.

Within the broader DeepAgentLabs architecture, Agentic Chaos is the resilience and
failure-validation reference implementation for the **AI Operations Workflow
Specification**. It injects, validates, tests and proves resilience, while keeping its
workflow artifacts compatible with the shared operational model used by AgenticLens
and the MCP layer.

## What it does

| Capability | Introduced | What you get |
| --- | --- | --- |
| **LLM Chaos Toolkit** | v0.1 | Three LLM-level faults: `token_timeout`, `rate_limit_storm`, `silent_degradation` |
| **Agent Failure Injector** | v0.2 | Agent-level faults: `tool_failure`, `memory_corruption`, `infinite_loop` |
| **Fidelity Judges & Handoff Chaos** | v0.3.0 | Score whether corrupted output actually got worse; corrupt, drop or delay handoffs between agents; record workflow topology |
| **Prompt/Model Drift Detector** | v0.4.0 | Snapshot and compare prompts, models, outputs and retrieval results; fail CI on silent change |
| **AgenticLens integration** | optional extra | Merge chaos events into an AgenticLens `Workflow` so `agenticlens analyze` reports chaos impact |

## Why it matters

Production agent systems fail in ways that ordinary logs rarely reveal. A provider
returns 429s for thirty seconds. A completion hangs. A model update quietly changes
answers while latency and token counts look perfect. Agentic Chaos lets you cause
these failures on purpose, in a test or a staging run, and see whether your fallbacks,
retries and guardrails actually work.

The hardest failure to catch is **silent degradation**: nothing in cost or latency
telemetry looks wrong, but the output is worse. Fidelity judges and the drift detector
exist for exactly this case.

## A 30-second example

```python
from agentic_chaos.chaos import chaos_call, TokenTimeoutError

try:
    chunks = chaos_call(retriever.search, user_question, faults=["token_timeout"])
except TokenTimeoutError:
    chunks = []  # no fallback handled it -- this is exactly what we want to find
```

Outside a `chaos_session(...)`, `chaos_call()` is a transparent pass-through, so the
instrumented code path is safe to ship. Chaos only activates when you turn it on, in
code or from the CLI:

```bash
agentic-chaos chaos run my_app.py --inject token_timeout,rate_limit_storm --save chaos_run.json
```

## Documentation map

| Page | Read it when you want to... |
| --- | --- |
| [Getting Started](getting-started.md) | Install the package and run your first experiment |
| [Architecture](architecture.md) | Understand how sessions, faults, judges and drift fit together |
| [Features](features.md) | See every capability with usage |
| [Configuration](configuration.md) | Tune fault parameters, CLI flags and CI behavior |
| [API Reference](api-reference.md) | Look up Python functions, classes and exceptions |
| [CLI Reference](cli-reference.md) | Look up every `agentic-chaos` command and option |
| [Integrations](integrations.md) | Connect to AgenticLens, eval frameworks, MCP and CI |
| [Examples](examples.md) | Copy working recipes |
| [Output Formats](output-formats.md) | Read or consume the JSON the tool writes |
| [Troubleshooting](troubleshooting.md) | Fix common problems |
| [Limitations](limitations.md) | Know what the package does not do yet |
| [Roadmap](roadmap.md) | See what is planned |

## The DeepAgentLabs ecosystem

Each DeepAgentLabs project answers a different operational question, and each can be
adopted on its own.

| Project | Question it answers |
| --- | --- |
| [AgenticLens](https://github.com/DeepAgentLabs/agenticlens) | What did the agent do, and what happened? |
| **Agentic Chaos** | How does the agent behave when things go wrong? |
| Agentic MCP | How does the agent interact with tools and external capabilities? |
| AgenticOps Control Tower | What is deployed, and what governance posture exists across agents? |
| Agentic Sidecar | Should the agent continue with this decision, and is it still acting according to intent? |

## Current status

`agentic-chaos` is **early-stage (alpha) software**. Every milestone through
v0.9 has shipped. The latest is 0.9.0, which adds
[resilience probes and the resilience score](v0.9.md). Earlier milestones
added fault injection, agent faults, fidelity judges, drift detection,
streaming faults, safety rails, contracts, cascades, workflows and
experiments. APIs may change between minor versions. See the
[Roadmap](roadmap.md) and the
[changelog](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/CHANGELOG.md).

## License

MIT. See the [LICENSE](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/LICENSE).

## AIOS v0.6 compatibility

See [canonical examples and extension guidance](aios-v0.6.md) for draft
artifact validation and unchanged dependency boundaries.

## AIOS v0.6.1 compatibility

See [provenance records and the portable conformance suite](aios-0.6.1.md);
Chaos exports stay `0.4-draft` and dependency boundaries are unchanged.
