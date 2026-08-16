from datetime import datetime, timedelta, timezone

from agentic_chaos.drift import (
    DriftAlertState,
    DriftFinding,
    DriftReport,
    DriftSnapshot,
    compare_snapshots,
    should_emit_report,
)


def test_compare_snapshots_detects_prompt_and_model_drift() -> None:
    baseline = DriftSnapshot.create(
        name="support-agent",
        prompt_text="You are a careful support agent.",
        model_name="gpt-5-mini",
        model_fingerprint="fp-a",
        output_text="Refund approved for order 123.",
        retrieval_items=["kb/refunds", "policy/returns"],
        embedding_model="text-embed-1",
    )
    current = DriftSnapshot.create(
        name="support-agent",
        prompt_text="You are a fast support agent.",
        model_name="gpt-5-mini",
        model_fingerprint="fp-b",
        output_text="Refund approved for order 123.",
        retrieval_items=["kb/refunds", "policy/returns"],
        embedding_model="text-embed-1",
    )

    report = compare_snapshots(baseline, current)

    assert report.has_drift is True
    assert {finding.kind for finding in report.findings if finding.changed} == {"prompt", "model"}


def test_compare_snapshots_detects_output_and_retrieval_drift() -> None:
    baseline = DriftSnapshot.create(
        name="qa-agent",
        output_text="The capital of France is Paris.",
        retrieval_items=["doc-1", "doc-2", "doc-3"],
    )
    current = DriftSnapshot.create(
        name="qa-agent",
        output_text="I cannot verify the capital city from the current context.",
        retrieval_items=["doc-9", "doc-10"],
    )

    report = compare_snapshots(
        baseline,
        current,
        output_distance_threshold=0.05,
        retrieval_distance_threshold=0.2,
    )

    changed = {finding.kind for finding in report.findings if finding.changed}
    assert "output" in changed
    assert "retrieval" in changed


def test_should_emit_report_suppresses_unchanged_fingerprint_inside_cooldown() -> None:
    baseline = DriftSnapshot.create(name="support-agent", prompt_text="A")
    current = DriftSnapshot.create(name="support-agent", prompt_text="B")
    report = compare_snapshots(baseline, current)
    now = datetime.now(timezone.utc)

    state = DriftAlertState(
        last_report_fingerprint=report.fingerprint(),
        last_emitted_at=now - timedelta(minutes=5),
    )

    assert (
        should_emit_report(
            report,
            state,
            cooldown_minutes=60,
            emit_only_on_change=True,
            now=now,
        )
        is False
    )


def test_should_emit_report_allows_repeat_when_emit_always_and_cooldown_elapsed() -> None:
    baseline = DriftSnapshot.create(name="support-agent", prompt_text="A")
    current = DriftSnapshot.create(name="support-agent", prompt_text="B")
    report = compare_snapshots(baseline, current)
    now = datetime.now(timezone.utc)

    state = DriftAlertState(
        last_report_fingerprint=report.fingerprint(),
        last_emitted_at=now - timedelta(minutes=120),
    )

    assert (
        should_emit_report(
            report,
            state,
            cooldown_minutes=60,
            emit_only_on_change=False,
            now=now,
        )
        is True
    )


def test_fingerprint_ignores_small_output_score_noise_below_threshold() -> None:
    report1 = DriftReport(
        name="support-agent",
        baseline_snapshot_id="baseline",
        current_snapshot_id="current-1",
        has_drift=False,
        findings=[
            DriftFinding(
                kind="output",
                changed=False,
                score=0.101,
                threshold=0.18,
                message="Output distribution within threshold (distance=0.101).",
            )
        ],
    )
    report2 = DriftReport(
        name="support-agent",
        baseline_snapshot_id="baseline",
        current_snapshot_id="current-2",
        has_drift=False,
        findings=[
            DriftFinding(
                kind="output",
                changed=False,
                score=0.109,
                threshold=0.18,
                message="Output distribution within threshold (distance=0.109).",
            )
        ],
    )
    now = datetime.now(timezone.utc)

    assert report1.fingerprint() == report2.fingerprint()
    assert (
        should_emit_report(
            report2,
            DriftAlertState(
                last_report_fingerprint=report1.fingerprint(),
                last_emitted_at=now - timedelta(minutes=1),
            ),
            cooldown_minutes=60,
            emit_only_on_change=True,
            now=now,
        )
        is False
    )


def test_fingerprint_ignores_small_retrieval_score_noise_above_threshold() -> None:
    report1 = DriftReport(
        name="support-agent",
        baseline_snapshot_id="baseline",
        current_snapshot_id="current-1",
        has_drift=True,
        findings=[
            DriftFinding(
                kind="retrieval",
                changed=True,
                score=0.61,
                threshold=0.4,
                message="Retrieval set drift detected (distance=0.610).",
            )
        ],
    )
    report2 = DriftReport(
        name="support-agent",
        baseline_snapshot_id="baseline",
        current_snapshot_id="current-2",
        has_drift=True,
        findings=[
            DriftFinding(
                kind="retrieval",
                changed=True,
                score=0.63,
                threshold=0.4,
                message="Retrieval set drift detected (distance=0.630).",
            )
        ],
    )

    assert report1.fingerprint() == report2.fingerprint()


def test_fingerprint_changes_when_discrete_prompt_drift_changes() -> None:
    report1 = DriftReport(
        name="support-agent",
        baseline_snapshot_id="baseline",
        current_snapshot_id="current-1",
        has_drift=True,
        findings=[
            DriftFinding(
                kind="prompt",
                changed=True,
                message="Prompt template changed.",
                detail={"baseline_hash": "a", "current_hash": "b", "diff": ["-old", "+new"]},
            )
        ],
    )
    report2 = DriftReport(
        name="support-agent",
        baseline_snapshot_id="baseline",
        current_snapshot_id="current-2",
        has_drift=True,
        findings=[
            DriftFinding(
                kind="prompt",
                changed=True,
                message="Prompt template changed.",
                detail={"baseline_hash": "a", "current_hash": "c", "diff": ["-old", "+newer"]},
            )
        ],
    )

    assert report1.fingerprint() != report2.fingerprint()
