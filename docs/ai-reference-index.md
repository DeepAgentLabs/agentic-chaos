# AI Reference capability index

This index opens the generated [AI Reference (robust)](https://deepagentlabs.io/agentic-chaos/docs/llms-full.md). In that raw Markdown file, **Full reference** points to an included topic section and **Source** identifies its maintained document. Use the [Developer Guide (simple)](developer-guide.md#capability-index) for short task workflows.

## Capability index

| Capability | Included scope | Detailed reference |
| --- | --- | --- |
| Core fault injection | Simulate timeouts, rate limits and degraded responses at explicit call boundaries. | <a href="#core-features">Full reference</a> · [Source](features.md) |
| Agent faults and topology | Exercise tool, memory, loop and handoff failures; record agent/tool edges. | <a href="#core-features">Full reference</a> · [Source](features.md) |
| LangGraph adapter | Wrap LangGraph tools and graph nodes with `wrap_tool()`/`wrap_node()`; no LangGraph dependency. | <a href="#api-reference">Full reference</a> · [Source](api-reference.md#langgraph-adapter) |
| Async calls | Inject into async callables with cancellation-aware execution. | <a href="#streaming-async-calls-provider-patches-and-profiles">Full reference</a> · [Source](v0.5.md) |
| Streaming faults | Cut or hang streams, delay first tokens or slow chunk delivery. | <a href="#streaming-async-calls-provider-patches-and-profiles">Full reference</a> · [Source](v0.5.md) |
| Provider patching | Patch explicit OpenAI, Anthropic or Google Gen AI client instances. | <a href="#streaming-async-calls-provider-patches-and-profiles">Full reference</a> · [Source](v0.5.md) |
| Probability and profiles | Control seeded sampling and load reusable TOML fault profiles. | <a href="#streaming-async-calls-provider-patches-and-profiles">Full reference</a> · [Source](v0.5.md) |
| Safety and dry runs | Bound instrumented injections, failure rate, duration and caller-reported cost; preview faults. | <a href="#safety-and-accounting">Full reference</a> · [Source](safety.md) |
| Fidelity judges | Score fault-event fidelity using heuristic or external evaluator adapters. | <a href="#core-features">Full reference</a> · [Source](features.md) |
| Drift detection | Compare prompt, model, output and retrieval snapshots with emission controls. | <a href="#reports-and-export-formats">Full reference</a> · [Source](output-formats.md) |
| Pytest plugin | Activate fault markers, fixtures, baseline runs, contracts and saved reports. | <a href="#pytest-plugin-and-contracts">Full reference</a> · [Source](v0.6.md) |
| Chaos contracts | Assert completion, recovery, retry limits, cost impact and topology traversal. | <a href="#pytest-plugin-and-contracts">Full reference</a> · [Source](v0.6.md) |
| Cascades and breaking-point search | Compose fault stages and search for a deterministic recovery threshold. | <a href="#cascades-breaking-points-poisoning-and-estimates">Full reference</a> · [Source](v0.7.md) |
| Response poisoning | Simulate wrong answers, fabricated references, malformed formats and adversarial instructions. | <a href="#cascades-breaking-points-poisoning-and-estimates">Full reference</a> · [Source](v0.7.md) |
| Explicit cost estimates | Model failure/retry budget scenarios from caller-supplied assumptions. | <a href="#cascades-breaking-points-poisoning-and-estimates">Full reference</a> · [Source](v0.7.md) |
| Scope controls | Limit injection to included steps/providers and apply exclusions before sampling. | <a href="#scopes-workflows-declarative-experiments-and-fuzzing">Full reference</a> · [Source](v0.8.md) |
| Chaos workflows | Compose Step, Parallel, HealthCheck, Suspend and Template nodes with stage reports. | <a href="#scopes-workflows-declarative-experiments-and-fuzzing">Full reference</a> · [Source](v0.8.md) |
| Declarative experiments and schedules | Validate/run JSON, TOML or optional YAML; print cron/CI scheduling snippets. | <a href="#scopes-workflows-declarative-experiments-and-fuzzing">Full reference</a> · [Source](v0.8.md) |
| Topology fuzzing | Discover topology, place seeded single faults and report reached/unreached trials. | <a href="#scopes-workflows-declarative-experiments-and-fuzzing">Full reference</a> · [Source](v0.8.md) |
| Resilience probes | Check HTTP, function, response-quality and latency signals before/during/after faults. | <a href="#probes-resilience-scores-and-history">Full reference</a> · [Source](v0.9.md) |
| Scores, CI gates and history | Recompute evidence-based resilience scores, inspect trends and prune retained runs. | <a href="#probes-resilience-scores-and-history">Full reference</a> · [Source](v0.9.md) |
| Authenticated containment assertions | Verify scoped observations and check dispatch after stop/revocation acknowledgements. | <a href="#authenticated-containment">Full reference</a> · [Source](phase6-containment.md) |
| ChaosHub recipes and exchange | Discover bundled recipes, bind scripts and exchange pinned remote recipes explicitly. | <a href="#chaoshub-and-fault-plugins">Full reference</a> · [Source](v0.11.md) |
| Fault plugins | Discover installed entry points and explicitly load trusted custom fault implementations. | <a href="#chaoshub-and-fault-plugins">Full reference</a> · [Source](v0.11.md) |
| Reporting, AIOS and ecosystem integrations | Save native reports/topology, export draft AIOS Runs and correlate Lens evidence. | <a href="#integrations-and-ecosystem-boundaries">Full reference</a> · [Source](integrations.md) |
| Configuration and limitations | Choose fault parameters, optional extras, host-owned targets and evidence boundaries. | <a href="#configuration">Full reference</a> · [Source](configuration.md) |

## How to use the robust reference

1. Choose a capability and read the workflow, prerequisites, expected evidence and limitations.
2. Consult **Source declarations: src/...** for statically extracted signatures, declared fields and exported names from both `agentic_chaos` and `pytest_agentic_chaos`. Source extraction never imports the package. Undocumented helpers remain internal; extraction does not make them stable public APIs.
3. Consult **CLI reference** for the complete command inventory, including dynamically registered experiment/workflow run commands. Their options are documented explicitly because their shared implementation has an internal Python name.
4. Native reports are Pydantic model contracts; declarative experiment documents are compiled by `agentic_chaos.experiments.schema`. This repository does not distribute a standalone JSON Schema bundle. AIOS Run exports remain `0.4-draft`; their normative schema belongs to `ai-operations-spec`. Do not invent a stable schema from a package version.
5. Release-labelled topic guides describe when a feature shipped. Historical compatibility notes apply to their stated versions; prefer the included source declarations and package metadata for the current checkout. In particular, current AIOS export support supersedes historical notes that called it future work.
6. Verify the adjacent `ai-docs-manifest.json`, which records normalized source hashes and the generated reference checksum. Fault presence, recovery, quality, operational health and authenticated containment are distinct evidence claims.

## Maintaining coverage

`docs/ai-docs.json` selects topic guides, integration notes and both distributed packages' Python modules. Add a new capability to both indexes and keep the CLI inventory aligned when adding commands. Regenerate from this repository root using the shared sibling checkout (Python 3.11 or newer):

```bash
python3 ../deepagentlabs.github.io/scripts/build_ai_docs.py --sources .. --project agentic-chaos
python3 ../deepagentlabs.github.io/scripts/build_ai_docs.py --sources .. --project agentic-chaos --check
```

The documentation deployment publishes the robust pack as a raw Markdown download. Its source manifest includes downloadable tutorial files as well as selected declarations and prose.
