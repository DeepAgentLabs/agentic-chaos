# Limitations

Agentic Chaos is early-stage software. This page lists what it does not do today so you can plan around it.

## Maturity

- The package is **early-stage (PyPI classifier: Alpha)** and supports Python 3.10 to 3.13.
- Every module through ChaosHub (0.11.0) has shipped; see the [overview](index.md#what-it-does) for the full capability list. Version 1.x is a coordinated ecosystem milestone, not a stability or production-readiness certification.
- Draft and candidate schema markers (such as the `0.4-draft` AIOS Run export) keep their own maturity, independent of the package version.
- APIs may change between releases. Pin your version in production test suites.
- Planned work is tracked only in the [Roadmap](roadmap.md).

## What it simulates, and what it does not

- **Client-side simulation.** Faults are injected at the Python call boundary. They do not touch the network, so they cannot reproduce provider-side behavior such as real latency distributions or TLS and DNS errors. Streaming faults cut, stall or slow a stream at the client wrapper; they do not reproduce a provider's own partial-stream failures.
- **Explicit opt-in per call site.** Only code wrapped with `chaos_call()`, `chaos_acall()`, `chaos_stream()`, `wrap_tool()` or `wrap_node()`, or a client patched with `patch_openai()`/`patch_anthropic()`/`patch_google()`, can be affected. Calls you did not wrap are never faulted.
- **No framework interception.** The LangGraph adapter is the same `wrap_tool()`/`wrap_node()` wrappers; nothing hooks a framework automatically. `--framework` is an informational hint.
- **Python only.** The toolkit targets Python callables. Other languages and remote services are out of scope.
- **Not a load-testing tool.** The rate-limit storm is a deterministic burst of errors, not traffic generation.

## Fault-specific notes

| Fault | Limitation |
| --- | --- |
| `token_timeout` | Hangs by sleeping for `hang_seconds`, so it slows the process for that long. In `mode="delay"` the real call still runs. For streams, use `stream_hang`, `slow_ttft` or `slow_chunks`. |
| `rate_limit_storm` | Fails the first `burst_count` calls and then clears. There is no random or time-windowed pattern. |
| `silent_degradation` | The built-in corruption only handles `.content`, `.text`, or a raw string. Other shapes need a custom `degrade_fn`. |
| `tool_failure` | Matches by tool name. Tools not wrapped with `wrap_tool()` are not affected. |
| `memory_corruption` | Operates on the shared agent state you expose to it. It cannot see state hidden inside a framework. |
| `infinite_loop` | Replaces the return value with a continue signal for `force_turns` calls. Your agent must interpret that signal for the test to be meaningful. |
| `handoff_corruption` | Targets edges recorded in a `TopologyTracker`. Edges you never registered cannot be targeted. |
| Streaming faults | Only affect streams consumed inside the session through `chaos_stream()`/`chaos_astream()` or a patched provider stream. |
| Provider patches | Patch one explicit client instance and need an active session. Module-level SDK state and other clients are untouched. |
| `poisoned_response` | Payloads are fixed synthetic text per strategy. They test handling of bad output; embedded instructions are never executed. |
| Cascades and `find_breaking_point()` | The breaking-point search assumes recovery is deterministic and monotonic over the range. Flaky targets give misleading thresholds. |

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

## Safety rails

- The cost limit only sees cost you record with `record_cost()` or `record_usage()`. Prices are never guessed, and a call can overshoot the budget by its own cost.
- Limits are cooperative. They are checked at call, stream and completion boundaries; nothing kills code that is already running. Already-running calls can finish after an abort.
- Dry runs still execute target calls, so they can still incur API spend.

See [Safety rails](safety.md#limits-and-accounting).

## Contracts, workflows and experiments

- A contract that lacks the evidence it needs is `inconclusive`, and inconclusive never passes. Retry detection needs `step_name`/`step_id` on calls.
- Resuming a workflow after a `Suspend` gate re-runs the definition from that gate; it does not restore process state.
- `experiment schedule` prints cron and GitHub Actions snippets; the package does not run a scheduler.
- The topology fuzzer places one fault per trial. A trial whose fault never fires is reported as unreached, not as a pass.

## Containment assertions

- Assertions need a verified, authenticated observation snapshot from AgenticLens (`agentic-chaos[containment]`). Failed, unknown or incomplete evidence cannot pass.
- Authentication does not prove exhaustive capture; coverage remains producer-declared. Already-dispatched side effects are not cancelled.

See [MCP Phase 6 containment](phase6-containment.md).

## ChaosHub and plugins

- Recipes are generic instrumented-call scenarios. Add quality and recovery assertions for your app; a recipe name does not prove every scenario it describes.
- Remote recipes require a full commit SHA. A pin fixes the bytes but does not vouch for their author, so review remote recipes before running them.
- Plugins run arbitrary code once loaded. Load only trusted plugins, explicitly with `--plugins` or `load_plugins()`.

## Reporting

- The native `ChaosReport` and `WorkflowReport` record events, calls, contracts, probes and scores. Per-experiment hypothesis/verdict reports are still planned (see the [Roadmap](roadmap.md)).
- The AIOS Run export is a `0.4-draft` mapping, not a claim of schema conformance.
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

- The `[agenticlens]` extra installs the published `agenticlens` package. Only the source repository's development setup resolves it from a sibling checkout.
- Interop relies on the shared JSON shapes (workflow schema v1.1 for `chaos_events`, v1.4 for drift reports). Changes to those schemas may require upgrading both packages.

## Safety

!!! danger "Do not run chaos against production data without safeguards"
    Faults can raise exceptions, corrupt text, and alter agent state. Run experiments in test or staging environments, and ensure wrapped tools do not perform irreversible actions (for example real refunds) while a fault is active.
