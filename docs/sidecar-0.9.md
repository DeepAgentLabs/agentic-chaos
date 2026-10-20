# Sidecar 0.9.0 compatibility

Sidecar 0.9.0 adds explicit task-authority tool bindings, narrowed delegation,
ancestor revocation, dispatch-time expiry checks, context reader permissions and
redacted evidence summaries. Private scope goals/values use explicit host delivery.

Chaos owns fault injection. Its 0.8 rate-limit fault is exercised at the Sidecar gate; native fault IDs remain attached to the measurement. Stop/revocation and dispatch counts are Sidecar-owned; a Chaos report alone does not prove containment.

The core package remains standalone. No new mandatory sibling dependency or
shared schema is introduced. Constraint-only guardians retain expiry WARN;
authority-bearing tasks BLOCK on expiry/revocation. Stop revokes descendants;
restart does not revive grants. Operator intent modification cannot reset a
delegated grant. Reader/actor identities must come from the trusted harness.

The fixed comparison has 24 offline synthetic runs (12 per variant): Agent Alone
dispatches 6/6 unsafe proposals; Sidecar dispatches 0/6, with 2/6 false interventions
on clean gate/provider-outage controls. Zero live inference cost/tokens are
synthetic accounting, not an economic or production-reliability claim. Raw
arguments/journals/operator views remain privileged; redaction is allowlisted,
not arbitrary secret detection or process isolation.

See the [Sidecar v0.9 guide](https://github.com/DeepAgentLabs/agentic-sidecar/blob/v0.9.0/website/docs/v0.9.md)
and [paired evidence](https://github.com/DeepAgentLabs/agentic-sidecar/blob/v0.9.0/tests/validation/v0_9_supervision.json).
