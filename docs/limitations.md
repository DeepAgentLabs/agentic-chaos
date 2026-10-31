# Limitations

Agentic Chaos is early-stage software. This page lists what it does not do today so you can plan around it.

## Maturity

- The package is **early-stage (PyPI classifier: Alpha)** and supports Python 3.10 to 3.13.
- Released modules: **LLM Chaos Toolkit** (v0.1), **Agent Failure Injector** (v0.2), **Fidelity Judges & Handoff Chaos** (v0.3.0) and **Prompt/Model Drift Detector** (v0.4.0).
- APIs may change between early releases. Pin your version in production test suites.
- Planned work is tracked only in the [Roadmap](roadmap.md).

## What it simulates, and what it does not

- **Client-side simulation.** Faults are injected at the Python call boundary. They do not touch the network, so they cannot reproduce provider-side behavior such as real latency distributions, partial streaming failures, or TLS and DNS errors.
- **Explicit opt-in per call site.** Only code wrapped with `chaos_call()`, `wrap_tool()` or `wrap_node()` (or run through the CLI against instrumented code) can be affected. Calls you did not wrap are never faulted.
- **Python only.** The toolkit targets Python callables. Other languages and remote services are out of scope.
- **Not a load-testing tool.** The rate-limit storm is a deterministic burst of errors, not traffic generation.

## Fault-specific notes

| Fault | Limitation |
| --- | --- |
| `token_timeout` | Hangs by sleeping for `hang_seconds`, so it slows the process for that long. In `mode="delay"` the real call still runs. It does not model streaming token timeouts. |
| `rate_limit_storm` | Fails the first `burst_count` calls and then clears. There is no random or time-windowed pattern. |
| `silent_degradation` | The built-in corruption only handles `.content`, `.text`, or a raw string. Other shapes need a custom `degrade_fn`. |
| `tool_failure` | Matches by tool name. Tools not wrapped with `wrap_tool()` are not affected. |
| `memory_corruption` | Operates on the shared agent state you expose to it. It cannot see state hidden inside a framework. |
| `infinite_loop` | Replaces the return value with a continue signal for `force_turns` calls. Your agent must interpret that signal for the test to be meaningful. |
| `handoff_corruption` | Targets edges recorded in a `TopologyTracker`. Edges you never registered cannot be targeted. |

## Fidelity judging

- `HeuristicJudge` is a lightweight, dependency-free heuristic. It is a signal, not a ground-truth quality metric.
- `DeepEvalJudge` and `PydanticEvalsJudge` wrap evaluator objects that you construct. Their scoring quality, cost and any API keys are your responsibility.
- Judges need a baseline to compare against. For pure downstream functions you may need to capture it manually.

## Drift detector

- Compares **local files and metadata you provide** (prompt file, output file, retrieval file, model name and fingerprint). It does not call a model or provider itself.
- Output drift uses a lightweight text-distance score. It is a change signal, not a semantic quality judgment.
- Retrieval drift is a set-distance over *fixed* retrieval results.
- `drift compare` exits with code `2` when drift is detected. CI steps must expect that code.
- Scheduling is external (cron, CI). The package does not run a scheduler.

## Reporting

- The standalone `ChaosReport` records what happened, but experiment reports with hypothesis, provenance and verdict are not yet available (see the [Roadmap](roadmap.md)).
- There are no built-in HTML dashboards. Use the JSON report, or AgenticLens for analysis.

## Resilience score

- The score summarizes evidence in the report. It is not a guarantee: a run
  that never exercised a failure path cannot show how that path recovers.
- Recovery is inferred from the call log. A failure counts as recovered when
  a later call to the same step succeeded, or when nothing escaped and the
  step was not retried. Instrument the steps you care about with `step_name`.
- Silent degradation counts only when a fidelity judge scored it. Otherwise it
  is reported as `unverified` and left out.
- Latency and cost need a baseline report, and latency compares wall-clock
  run durations, which are noisy for very short runs.
- The run history is a local JSON file with no locking. Give concurrent jobs
  separate files.

## Integrations

- The AgenticLens extra is currently resolved from a sibling checkout in the source repository until a compatible AgenticLens release is published.
- Interop relies on the shared JSON shape (schema v1.1). Changes to that schema may require upgrading both packages.

## Safety

!!! danger "Do not run chaos against production data without safeguards"
    Faults can raise exceptions, corrupt text, and alter agent state. Run experiments in test or staging environments, and ensure wrapped tools do not perform irreversible actions (for example real refunds) while a fault is active.
