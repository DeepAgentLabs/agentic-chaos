# Evals 0.10.0 evaluation evidence on Chaos runs

[Agentic Evals 0.10.0](https://github.com/DeepAgentLabs/agentic-evals/releases/tag/v0.10.0)
exports its evaluation reports as AI Operations Specification `0.4-draft`
`evaluation` evidence and attaches them to an existing `run` artifact. The
Run that `agentic_chaos.export.to_aios_run` derives from a `ChaosReport` is a
natural target: the evaluation of what the agent answered under faults then
travels with the faults that were injected.

## Map cases to Chaos steps

`to_aios_run` generates Step IDs (`<run>:step:<n>`) and keeps the native
correlation in `attributes.native_step_id` / `native_step_name`. Map each
Evals case to the generated ID:

```python
from agentic_chaos.export import to_aios_run
from agentic_evals import attach_aios_evidence, to_aios_evidence

run = to_aios_run(chaos_report)
step_for = {s["attributes"].get("native_step_id"): s["id"] for s in run["steps"]}
export = to_aios_evidence(
    evals_report, run_id=run["id"], targets={"refund-answer": step_for["answer"]}, gate=decision
)
merged = attach_aios_evidence(run, export)
```

The merged Run passes MCP's `spec.validate_artifact` with
`conformance.aligned = true`; this was checked with Chaos 0.8.0, Evals 0.10.0 and
MCP 0.4. Evals rejects a target that is not in the Run, so a case cannot be
attached to a step Chaos never recorded.

## Ownership

- Chaos still owns the Run's steps, occurrences, `reliability_event`
  evidence and run status. Evals adds only `evaluation` evidence, `evaluates`
  relationships and `aiops.evaluation.*` events.
- A live case whose target timed out or errored under an injected fault has no
  observed output. Evals reports it in `unobserved_cases` rather than exporting
  an evaluation of the Run. The Chaos `reliability_event` remains the evidence
  of what happened.
- A passing evaluation next to a `reliability_event` shows that the answer was
  scored as correct. It does not prove recovery or containment, which remain
  separate (Evals roadmap v0.11).

No adapter, shared schema, runtime dependency or Chaos release is introduced.
See the [Evals guide](https://github.com/DeepAgentLabs/agentic-evals/blob/v0.10.0/docs/aios-evidence.md).
