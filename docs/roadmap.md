# Roadmap

This page lists **planned** capabilities only. Everything that works today is documented in [Features](features.md). The authoritative plan lives in [`ROADMAP.md`](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/ROADMAP.md) in the repository.

!!! warning "Planned means not implemented"
    Nothing on this page is available in the current release. Do not rely on it in tests or pipelines.

## Next: MCP Phase 6 coordinated containment release

Chaos containment scenarios and assertions will ship as a sibling release with
MCP Phase 6's Sidecar stop/revoke bridge, before ChaosHub. Test actual forbidden
dispatches after effective acknowledgement across queues, retries, existing
sessions and revoked/delegated credentials. Report in-flight effects separately.
A bypassed negative control must fail, and missing or unverified evidence cannot
pass. CI must exercise the real adapters on isolated synthetic targets.

Target a Chaos 0.9.x validation patch, or 0.10.0 if public APIs change, paired with
MCP 0.6.0; finalize versions during packaging. Evals v0.11 containment scoring
comes next. See the
[canonical acceptance criteria](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/ROADMAP.md#required-paired-release-acceptance).

## Planned capabilities

| Capability | Summary |
| --- | --- |
| **Structured experiment reports** | Every chaos run emits a report with hypothesis, injection-point provenance, observed behavior, and verdict. |
| **Synthetic test scenarios** | Prebuilt known-bad agent behaviors for consistent resilience validation. |
| **Streaming fault injection** | Fault injection at the streaming-token level for partial-stream failures. |
| **Provider patching and chaos profiles** | Patch an SDK client at import time so all calls go through chaos without wrapping each call manually. Declarative YAML/JSON experiment profiles. |
| **Pytest plugin and assertions** | First-class `pytest` fixtures and assertion helpers for inline resilience assertions. |
| **Circuit breaker and dry-run mode** | Safety rails: circuit breaker to halt chaos when error rates exceed a threshold, and a dry-run mode that reports what would fire. |
| **ChaosHub** | Shared experiment registry for reproducible resilience scenarios. |

## Direction

Agentic Chaos is the resilience and failure-validation reference implementation for the **AI Operations Workflow Specification**. It aims to inject, validate, test, and prove resilience, while keeping its workflow artifacts compatible with the operational model shared by AgenticLens, the MCP layer, and the future Control Tower control plane.

## Influence the roadmap

- Open an [issue](https://github.com/DeepAgentLabs/agentic-chaos/issues) to request a fault type or integration.
- Read [`CONTRIBUTING.md`](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/CONTRIBUTING.md) before sending a pull request.
- Track delivered work in the [`CHANGELOG.md`](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/CHANGELOG.md).

