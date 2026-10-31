# Lens optimization and fault evidence

## AgenticLens 0.11.0 optimization compatibility

AgenticLens 0.11.0 implements roadmap v0.9 Optimization Intelligence:
evidence-backed recommendations from recorded traces for prompts (caching,
compression), retrieval (top-k pruning, reranking), memory (summarization,
retention), tools (result caching, non-retryable errors), workflows (redundant
steps, handoffs that add no work) and models (quality-cost trade-offs between
variants). Projected benefit, confidence and quality risk stay separate; an
append-only ledger tracks accepted, rejected, adopted and reverted
recommendations; and adopted changes are evaluated against later traces, with
projected and observed outcomes side by side. Recommendations are advisory.
MCP 0.4.3 exposes read-only `lens.optimization_analyze` and pins hosted Lens
0.11.0. See the [optimization guide](https://github.com/DeepAgentLabs/agenticlens/blob/v0.11.0/docs/optimization.md)
and [offline example](https://github.com/DeepAgentLabs/agenticlens/blob/v0.11.0/examples/optimization_demo.py).

The existing optional `agenticlens>=0.7.0` extra already admits 0.11.0.
Chaos does not emit the structured `Run.spans` that Lens analyses: the agent
must be instrumented with Lens tracing, recording its own `retry` spans and
failure `error_type`s, and `mark_span()` only annotates spans the caller
creates. With that instrumentation, `retry_policy` can show whether an error
type injected by a fault ever recovers. Treat recommendations from
fault-injected traces as evidence about the injected faults, not production
traffic. Fault injection and resilience
contracts remain Chaos-owned. No dependency change or Chaos patch release is
required.
