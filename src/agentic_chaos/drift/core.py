from datetime import datetime, timedelta, timezone

from agentic_chaos.drift.models import (
    DriftAlertState,
    DriftFinding,
    DriftReport,
    DriftSnapshot,
    compute_list_distance,
    compute_text_distance,
    summarize_diff,
)


def compare_snapshots(
    baseline: DriftSnapshot,
    current: DriftSnapshot,
    *,
    output_distance_threshold: float = 0.18,
    retrieval_distance_threshold: float = 0.4,
) -> DriftReport:
    findings: list[DriftFinding] = []

    if baseline.prompt_text is not None or current.prompt_text is not None:
        prompt_changed = baseline.prompt_hash != current.prompt_hash
        findings.append(
            DriftFinding(
                kind="prompt",
                changed=prompt_changed,
                message=(
                    "Prompt template changed." if prompt_changed else "Prompt template unchanged."
                ),
                detail={
                    "baseline_hash": baseline.prompt_hash,
                    "current_hash": current.prompt_hash,
                    "diff": summarize_diff(baseline.prompt_text or "", current.prompt_text or ""),
                },
            )
        )

    if any(
        value is not None
        for value in (
            baseline.model_name,
            baseline.model_fingerprint,
            current.model_name,
            current.model_fingerprint,
        )
    ):
        model_changed = (
            baseline.model_name != current.model_name
            or baseline.model_fingerprint != current.model_fingerprint
            or baseline.embedding_model != current.embedding_model
        )
        findings.append(
            DriftFinding(
                kind="model",
                changed=model_changed,
                message="Model metadata changed." if model_changed else "Model metadata unchanged.",
                detail={
                    "baseline_model": baseline.model_name,
                    "current_model": current.model_name,
                    "baseline_fingerprint": baseline.model_fingerprint,
                    "current_fingerprint": current.model_fingerprint,
                    "baseline_embedding_model": baseline.embedding_model,
                    "current_embedding_model": current.embedding_model,
                },
            )
        )

    if baseline.output_text is not None or current.output_text is not None:
        output_distance = compute_text_distance(
            baseline.output_text or "",
            current.output_text or "",
        )
        output_changed = output_distance >= output_distance_threshold
        findings.append(
            DriftFinding(
                kind="output",
                changed=output_changed,
                score=output_distance,
                threshold=output_distance_threshold,
                message=(
                    f"Output distribution drift detected (distance={output_distance:.3f})."
                    if output_changed
                    else f"Output distribution within threshold (distance={output_distance:.3f})."
                ),
                detail={
                    "baseline_hash": baseline.output_hash,
                    "current_hash": current.output_hash,
                },
            )
        )

    if baseline.retrieval_items or current.retrieval_items:
        retrieval_distance = compute_list_distance(
            baseline.retrieval_items,
            current.retrieval_items,
        )
        retrieval_changed = retrieval_distance >= retrieval_distance_threshold
        findings.append(
            DriftFinding(
                kind="retrieval",
                changed=retrieval_changed,
                score=retrieval_distance,
                threshold=retrieval_distance_threshold,
                message=(
                    f"Retrieval set drift detected (distance={retrieval_distance:.3f})."
                    if retrieval_changed
                    else f"Retrieval set within threshold (distance={retrieval_distance:.3f})."
                ),
                detail={
                    "baseline_items": baseline.retrieval_items,
                    "current_items": current.retrieval_items,
                },
            )
        )

    has_drift = any(finding.changed for finding in findings)
    return DriftReport(
        name=current.name,
        baseline_snapshot_id=baseline.id,
        current_snapshot_id=current.id,
        has_drift=has_drift,
        findings=findings,
        baseline={
            "captured_at": baseline.captured_at,
            "model_name": baseline.model_name,
            "model_fingerprint": baseline.model_fingerprint,
            "embedding_model": baseline.embedding_model,
        },
        current={
            "captured_at": current.captured_at,
            "model_name": current.model_name,
            "model_fingerprint": current.model_fingerprint,
            "embedding_model": current.embedding_model,
        },
    )


def should_emit_report(
    report: DriftReport,
    state: DriftAlertState,
    *,
    cooldown_minutes: int,
    emit_only_on_change: bool = True,
    now: datetime | None = None,
) -> bool:
    now = now or datetime.now(timezone.utc)
    fingerprint = report.fingerprint()

    if state.last_report_fingerprint != fingerprint:
        return True

    if emit_only_on_change:
        return False

    if state.last_emitted_at is None:
        return True

    return now - state.last_emitted_at >= timedelta(minutes=cooldown_minutes)


def update_alert_state(
    report: DriftReport,
    *,
    emitted_at: datetime | None = None,
) -> DriftAlertState:
    emitted_at = emitted_at or datetime.now(timezone.utc)
    return DriftAlertState(
        last_report_fingerprint=report.fingerprint(),
        last_emitted_at=emitted_at,
    )
