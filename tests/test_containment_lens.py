"""Optional Lens adapter tests; MCP's paired wheel job requires it without skips."""

import pytest

lens = pytest.importorskip("agenticlens.integrity")

from agentic_chaos.containment import assert_contained  # noqa: E402


def test_authentication_covers_exact_ordered_snapshot():
    rows = [
        dict(
            event_id="ack",
            kind="stop_acknowledged",
            outcome="acknowledged",
            subject="u",
            task_id="t",
        ),
        dict(event_id="deny", kind="denied", correlation_id="retry", subject="u", task_id="t"),
    ]
    key = b"synthetic-containment-key-at-least32"
    manifest = lens.seal(
        rows,
        coverage=lens.Coverage(stream_id="s", description="test", complete=True),
        key_id="k",
        key=key,
    )
    kwargs = dict(
        manifest=manifest.model_dump(),
        trusted_keys={"k": key},
        expected_stream_id="s",
        acknowledgement_id="ack",
        subject="u",
        task_id="t",
        attempted_call_ids={"retry"},
    )
    assert assert_contained(rows, **kwargs)["forbidden_dispatches"] == 0
    with pytest.raises(AssertionError):
        assert_contained(list(reversed(rows)), **kwargs)
    rows[-1]["kind"] = "dispatched"
    with pytest.raises(AssertionError):
        assert_contained(rows, **kwargs)


def test_caller_mutation_during_verification_cannot_change_checked_snapshot(monkeypatch):
    import agenticlens.integrity as integrity

    rows = [
        dict(
            event_id="ack",
            kind="stop_acknowledged",
            outcome="acknowledged",
            subject="u",
            task_id="t",
        ),
        dict(event_id="deny", kind="dispatched", correlation_id="retry", subject="u", task_id="t"),
    ]
    key = b"synthetic-containment-key-at-least32"
    manifest = lens.seal(
        rows,
        coverage=lens.Coverage(stream_id="s", description="test", complete=True),
        key_id="k",
        key=key,
    )
    original = integrity.verify

    def mutate_after_verification(*args, **kwargs):
        result = original(*args, **kwargs)
        rows[-1]["kind"] = "denied"
        return result

    monkeypatch.setattr(integrity, "verify", mutate_after_verification)
    with pytest.raises(AssertionError, match="Forbidden"):
        assert_contained(
            rows,
            manifest=manifest.model_dump(),
            trusted_keys={"k": key},
            expected_stream_id="s",
            acknowledgement_id="ack",
            subject="u",
            task_id="t",
            attempted_call_ids={"retry"},
        )
