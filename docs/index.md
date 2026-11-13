# Agentic Chaos

## Agentic Chaos overview

How does the application behave when a dependency fails?

A wrapped callable or experiment target plus fault configuration. Fault events, experiment reports, and resilience evidence.

**When to start here**

Inject a timeout into a local dummy search call.

## Inputs and outputs

| You provide | You receive |
| --- | --- |
| A wrapped callable or experiment target plus fault configuration. | Fault events, experiment reports, and resilience evidence. |

## Execution boundary

A fault being injected does not prove successful recovery. Inspect application behavior and define recovery assertions.

[Start the Agentic Chaos quickstart →](guide/quickstart.md)

## Capabilities

Use these capabilities to address stress-test tasks in your application.

| Capability | What it provides |
| --- | --- |
| Call-level faults | Inject timeouts, rate limiting, or output degradation around a selected callable. |
| Agent-level faults | Exercise tool failure, memory corruption, forced continuation, and handoff failure. |
| Explicit sessions | Activate faults within a bounded experiment instead of changing normal execution. |
| Fidelity evaluation | Compare the quality implications of corrupted outputs with configured judges. |
| Drift detection | Snapshot and compare prompts, outputs, model identity, and retrieval evidence. |
| Integration evidence | Export recorded faults and optionally correlate them with Lens observations. |

## Supported scope

A fault being injected does not prove successful recovery. Inspect application behavior and define recovery assertions.

## Core concepts

| Concept | Meaning |
| --- | --- |
| Call wrapper | chaos_call forwards to the real function unless an active session selects a relevant fault. |
| Fault configuration | Names use default settings; fault instances allow explicit parameter values. |
| Event | A record of injected behavior and its outcome; not a declaration that recovery was adequate. |
| Experiment target | The application path being stressed, including its error handling and fallback behavior. |
| Fidelity vs drift | Fidelity concerns degraded-output quality; drift concerns changes between recorded snapshots. |

## Recommended workflow

## Establish a normal baseline

Run the application without an active fault session. Record its useful output and the time/cost constraints you expect recovery to preserve.

## Select a failure hypothesis

For example: if retrieval times out, the application should return an explicit fallback within the allowed duration. Select the specific call site and fault rather than injecting unrelated failures everywhere.

```
agentic-chaos chaos list-faults
agentic-chaos chaos run chaos_quickstart.py --inject token_timeout --save chaos_run.json
```

## Inspect recovery

The recorded event establishes that the fault occurred. Separately check whether the caller retried, switched providers, returned useful fallback content, or surfaced a clear error.

## Make the experiment repeatable

Use explicit fault parameters and seeds when available. Retain normal output, fault settings, the resulting report, and the recovery assertion. Add compound scenarios only after individual failure modes are understood.

## Next steps

Inject a timeout into a local dummy search call.

[Open the developer quickstart →](guide/quickstart.md)
