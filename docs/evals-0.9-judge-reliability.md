# Evals 0.9.0 judge reliability and live resilience

[Agentic Evals 0.9.0](https://github.com/DeepAgentLabs/agentic-evals/releases/tag/v0.9.0) adds bounded live-target retries, per-case
timeouts, and an explicit `target_status` (`ok`, `timed_out`, `error`)
on each case of a live run, plus judge cost, retries and agreement.

## Evaluating a target under chaos

When Evals calls a target that Chaos is injecting faults into, Evals records
what it observed:

- `target_status` is the case's final outcome after retries. If every attempt
  exceeds the timeout (for example under an injected latency fault), the case
  is `timed_out`. If attempts are exhausted with any other failure, including a
  mix of injected exceptions and timeouts, it is `error`. Both are kept apart
  from wrong answers in `summary.live`, JUnit (`<error>`) and the gate
  (`max_timed_out_cases`, `max_target_error_cases`). If a later attempt answers,
  the case is `ok`, and only `target_attempts` and
  `summary.live.retried_cases` record the absorbed fault;
- Evals retries (`RetryPolicy`) can absorb transient injected faults. When the
  point of the run is to measure behavior under faults, keep the default single
  attempt, or read `target_attempts` and `summary.live.retried_cases`, so an
  absorbed fault is still visible.

A `timed_out` or `error` case is an evaluation-harness outcome, not a Chaos
fault record or a resilience verdict. Chaos events, contracts and workflow
statuses remain the resilience evidence. Convert observed outputs to native
`EvaluationSample`s explicitly, as before.

No adapter, shared schema, runtime dependency or Chaos release is introduced.
See the [Evals guide](https://github.com/DeepAgentLabs/agentic-evals/blob/v0.9.0/docs/judge-reliability.md).
