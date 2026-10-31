# MCP 0.5.0 hosted access control

[MCP 0.5.0](https://github.com/DeepAgentLabs/mcp-server/releases/tag/v0.5.0) completes MCP Phase 5 with hosted access control. Each hosted key can carry allow and deny tool globs, an expiry and a task scope. The server enforces them at dispatch, outside the model: before each hosted handler runs, it re-authenticates the key and reloads its policy. Revocation, a narrower policy or expiry therefore stops queued calls, retries and calls on existing connections. Calls already running finish. Denied calls return an MCP-local `mcp.access-decision.v1` record, and every hosted call logs `dispatch`/`completion` records that share a `correlation_id`. These records are not AIOS artifacts. `core.access_status` reports a key's effective policy, and operators use `deep-agentic-core-mcp-admin` to narrow or revoke a key by user ID.

## What changes for Chaos

- Hosted HTTP still rejects `chaos.run_experiment`. A policy can narrow the
  hosted surface but cannot re-enable execution.
- `chaos.list_faults` and `chaos.export_aios_run` are subject to a key's policy
  like any other hosted tool. `chaos.*` in `deny` removes them.
- Local stdio is trusted and does not use policies, so local experiments are
  unchanged.

## Compatibility

No Chaos API change, dependency bump or release. MCP's hosted pins stay at
`agentic-chaos==0.9.0`. Chaos fixtures for revoked keys, denied tools and queued
dispatch are still open in MCP's access-containment validation list.

See the [MCP hosted access control guide](https://github.com/DeepAgentLabs/mcp-server/blob/v0.5.0/docs/access-control.md).
