"""Offline real Sidecar dispatch with native Chaos assertions and Lens authentication.

Install agentic-chaos[containment] and agentic-sidecar>=0.9.2. Seed 601 is
scenario metadata; there are no live providers or real external credentials.
"""

from agentic_sidecar import Sidecar, SidecarBlockedError, TaskRuntime
from agentic_sidecar.adapters.langgraph import attach
from agenticlens.integrity import Coverage, seal

from agentic_chaos import PoisonedResponseFault
from agentic_chaos.containment import assert_contained


def main():
    runtime = TaskRuntime("task-601")
    sidecar = Sidecar(runtime=runtime, mode="govern", on_sidecar_failure="fail_closed")
    effects = []

    def target():
        effects.append("effect")

    wrapped = attach(sidecar, [target])[0]
    wrapped()
    receipt = runtime.control("stop", "synthetic-operator")
    payload = PoisonedResponseFault(strategy="policy_bypass", seed=601).trigger(
        lambda: "tool output", step_id="tool", step_name="target"
    )
    records = []
    for event in runtime.journal.export():
        if event["kind"] in {"executed", "completed"}:
            records.append(
                {
                    "event_id": event["event_id"],
                    "kind": "dispatched" if event["kind"] == "executed" else "completed",
                    "subject": "isolated-user",
                    "task_id": runtime.task_id,
                    "correlation_id": event["payload"]["invocation_id"],
                }
            )
    records.append(
        {
            "event_id": "ack",
            "kind": "stop_acknowledged",
            "outcome": "acknowledged",
            "subject": "isolated-user",
            "task_id": runtime.task_id,
            "receipt": receipt,
            "seed": 601,
            "payload": payload.result,
        }
    )
    try:
        wrapped()
    except SidecarBlockedError:
        records.append(
            {
                "event_id": "retry",
                "kind": "denied",
                "correlation_id": "retry",
                "subject": "isolated-user",
                "task_id": runtime.task_id,
            }
        )
    key = b"synthetic-local-demo-key-at-least32"
    manifest = seal(
        records,
        coverage=Coverage(
            stream_id="demo-601", description="instrumented local target", complete=True
        ),
        key_id="demo",
        key=key,
    )
    result = assert_contained(
        records,
        manifest=manifest.model_dump(),
        trusted_keys={"demo": key},
        expected_stream_id="demo-601",
        acknowledgement_id="ack",
        subject="isolated-user",
        task_id=runtime.task_id,
        attempted_call_ids={"retry"},
    )
    assert effects == ["effect"]
    print(result)


if __name__ == "__main__":
    main()
