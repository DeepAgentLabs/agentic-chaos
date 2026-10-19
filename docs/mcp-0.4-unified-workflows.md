# MCP 0.4.0 unified workflows

[MCP 0.4.0](https://github.com/DeepAgentLabs/mcp-server/releases/tag/v0.4.0) completes Phase 4 with its unified workflows: `core.compare_runs`, a fail-closed `core.release_check`, `core.incident_summary` and `core.export_report`. MCP judges nothing itself; it composes Lens comparisons, the Evals release gate and Chaos run reports. Malformed or failed-call evidence always blocks readiness, and so does missing evidence of a required kind; all three kinds are required by default and `required_evidence` narrows that.

## What MCP reads

- The chaos report produced by MCP's `chaos.run_experiment` (stored in the
  session) or one supplied as `chaos_report`.
- It must carry `crashed`, `timed_out` and `chaos_events`. An AIOS run from
  `chaos.export_aios_run` is not chaos evidence for the release check.

## What blocks a release

- `crashed` or `timed_out`.
- `ok: false` without a crash or timeout.
- Injected fault events alone are expected under chaos and do not block, and
  `core.incident_summary` does not report them as incidents.

## Compatibility

No Chaos API change, dependency bump or release. Hosted MCP still rejects
`chaos.run_experiment`; pass a local report or leave `chaos` out of
`required_evidence`.

See the [MCP unified workflows guide](https://github.com/DeepAgentLabs/mcp-server/blob/v0.4.0/docs/unified-workflows.md).
