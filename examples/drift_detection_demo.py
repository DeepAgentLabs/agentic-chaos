from pathlib import Path

from agentic_chaos.drift import DriftSnapshot, compare_snapshots, save_report, save_snapshot

out_dir = Path("/tmp/agentic-chaos-drift-demo")
out_dir.mkdir(parents=True, exist_ok=True)

baseline = DriftSnapshot.create(
    name="support-agent",
    prompt_text="You are a careful support agent. Cite the refund policy.",
    model_name="gpt-5-mini",
    model_fingerprint="provider-fp-001",
    output_text="Refund approved under policy section 4.",
    retrieval_items=["kb/refunds/v1", "kb/orders/v1"],
    embedding_model="text-embed-1",
)
current = DriftSnapshot.create(
    name="support-agent",
    prompt_text="You are a fast support agent. Keep answers short.",
    model_name="gpt-5-mini",
    model_fingerprint="provider-fp-002",
    output_text="Refunds may be available. Please contact support.",
    retrieval_items=["kb/refunds/v2", "kb/orders/v1"],
    embedding_model="text-embed-2",
)

save_snapshot(out_dir / "baseline.json", baseline)
save_snapshot(out_dir / "current.json", current)

report = compare_snapshots(baseline, current)
save_report(out_dir / "drift_report.json", report)

print(f"Drift detected: {report.has_drift}")
print(f"Wrote demo artifacts to {out_dir}")
