# Capabilities

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
