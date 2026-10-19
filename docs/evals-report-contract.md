# Evals native contract compatibility

Agentic Evals 0.7.2 publishes native report (`schema_version: "1.0"`) and
gate-decision JSON Schemas, with offline `report_schema()` and
`gate_decision_schema()` accessors. Contract 1.x evolves additively; readers
should tolerate unknown fields. Chaos resilience reports and per-run contracts remain separate from Evals scores and release gates; fault execution and containment work are unchanged.

See the [contract, examples and compatibility policy](https://github.com/DeepAgentLabs/agentic-evals/blob/v0.7.2/docs/report-contract.md). Existing dependency
ranges remain sufficient; using the new accessors directly requires
`agentic-evals>=0.7.2`. This documentation alignment needs no sibling patch release.

These native Evals schemas do not establish AIOS conformance.
