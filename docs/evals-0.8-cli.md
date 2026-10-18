# Evals 0.8.0 CLI interoperability

Evals 0.8.0 scores saved observations with `evaluate` or live targets with `live`, then computes release decisions with `gate`. Chaos contracts remain per-run resilience checks, not Evals scores. Convert observed outputs to native EvaluationSamples explicitly; this release adds no implicit Chaos adapter or runtime dependency.

```bash
agentic-evals evaluate suite.yaml samples.jsonl --out report.json
agentic-evals gate report.json --config gate.yaml --out gate.json
```

`evaluate`/`live` exit 0 when a report is produced, even if cases fail.
`gate` exits 0 on pass, 1 on failed policy, and 2 on invalid input or usage.
Use Evals 0.8.0 for these commands; see the [CLI guide and CI example](https://github.com/DeepAgentLabs/agentic-evals/blob/v0.8.0/docs/cli.md).

This is compatibility documentation only: no sibling runtime change,
dependency-floor increase or patch release is required.
