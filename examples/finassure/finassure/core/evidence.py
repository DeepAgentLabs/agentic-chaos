"""Evidence Pack Generator producing audit-ready Markdown, HTML, and JSON reports."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from finassure.config import settings
from finassure.core.models import GateVerdict, RunArtifact


class EvidencePackGenerator:
    """Generates release evidence packages compliant with AI risk & oversight frameworks."""

    def __init__(self, artifacts_dir: Path | None = None) -> None:
        self.artifacts_dir = artifacts_dir or settings.ARTIFACTS_DIR
        self.evidence_dir = self.artifacts_dir / "evidence_packs"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, verdict: GateVerdict, runs: Sequence[RunArtifact]) -> dict[str, Path]:
        """Generate Markdown, HTML, JSON, and CSV evidence reports."""
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        prefix = f"evidence_{verdict.pack_name}_{verdict.pack_version}_{timestamp_str}"

        md_path = self.evidence_dir / f"{prefix}.md"
        html_path = self.evidence_dir / f"{prefix}.html"
        json_path = self.evidence_dir / f"{prefix}.json"
        csv_path = self.evidence_dir / f"{prefix}.csv"

        # Generate markdown content
        md_content = self._render_markdown(verdict, runs)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        # Generate HTML content
        html_content = self._render_html(verdict, runs, md_content)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Generate JSON summary
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(verdict.model_dump_json(indent=2))

        # Generate CSV export
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "run_id",
                    "case_id",
                    "pack_name",
                    "pack_version",
                    "scenario_id",
                    "decision",
                    "oracle_decision",
                    "match",
                    "escalated",
                    "unsupported_approval",
                    "silent_failure",
                    "safe_degraded",
                    "latency_ms",
                    "cost",
                    "tokens",
                ]
            )
            for r in runs:
                writer.writerow(
                    [
                        r.run_id,
                        r.case_id,
                        r.pack_name,
                        r.pack_version,
                        r.scenario_id,
                        r.workflow_outcome.decision.value,
                        r.oracle_result.decision.value,
                        r.workflow_outcome.decision == r.oracle_result.decision,
                        r.workflow_outcome.escalated,
                        r.unsupported_approval,
                        r.silent_failure,
                        r.safe_degraded,
                        r.latency_ms,
                        r.total_cost,
                        r.total_tokens,
                    ]
                )

        return {
            "markdown": md_path,
            "html": html_path,
            "json": json_path,
            "csv": csv_path,
        }

    def _render_markdown(self, verdict: GateVerdict, runs: Sequence[RunArtifact]) -> str:
        status_symbol = "PASSED" if verdict.verdict == "PASSED" else "FAILED"
        rules_table = "\n".join(
            f"| {r.name} | {'PASS' if r.passed else 'FAIL'} | "
            f"{r.threshold} | {r.actual} | {r.message} |"
            for r in verdict.rules
        )

        v_stat = "PASS" if verdict.verdict == "PASSED" else "FAIL"
        s_stat = "PASS" if verdict.overall_score >= 0.90 else "FAIL"
        u_stat = "PASS" if verdict.unsupported_approvals_count == 0 else "FAIL"
        f_stat = "PASS" if verdict.silent_failure_rate <= 0.02 else "FAIL"
        d_stat = "PASS" if verdict.safe_degradation_rate >= 0.95 else "FAIL"
        e_stat = "PASS" if verdict.escalation_rate <= 0.35 else "FAIL"
        l_stat = "PASS" if verdict.p95_latency_ms <= 4000 else "FAIL"
        c_stat = "PASS" if verdict.cost_per_application <= 0.05 else "FAIL"

        return f"""# FinAssure Reliability & Release Gate Evidence Pack
**Pack**: `{verdict.pack_name}` | **Version**: `{verdict.pack_version}`
**Verdict**: **{status_symbol}** | **Evaluation Timestamp**: {verdict.timestamp}

---

## 1. Executive Summary & Release Verdict

| Metric | Target / Requirement | Actual Result | Status |
|---|---|---|---|
| **Release Verdict** | PASSED | **{verdict.verdict}** | {v_stat} |
| **Evaluator Suite Score** | >= 0.90 | **{verdict.overall_score:.2f}** | {s_stat} |
| **Unsupported Approvals** | 0 (Hard fail) | **{verdict.unsupported_approvals_count}** | {u_stat} |
| **Silent Failure Rate** | <= 2.0% | **{verdict.silent_failure_rate * 100:.1f}%** | {f_stat} |
| **Safe Degradation Rate** | >= 95.0% | **{verdict.safe_degradation_rate * 100:.1f}%** | {d_stat} |
| **Escalation Rate (HITL)** | <= 35.0% | **{verdict.escalation_rate * 100:.1f}%** | {e_stat} |
| **p95 Latency** | <= 4000 ms | **{verdict.p95_latency_ms:.1f} ms** | {l_stat} |
| **Cost per Application** | <= $0.05 | **${verdict.cost_per_application:.4f}** | {c_stat} |

---

## 2. Gate Rules Checklist

| Rule Name | Status | Threshold | Actual | Description |
|---|---|---|---|---|
{rules_table}

---

## 3. Resilience Testing & Regulatory Framework Mapping

This test suite maps directly to resilience testing and automated AI governance themes:

1. **DORA (Digital Operational Resilience Act - Scenario Testing)**:
   - System tested against third-party dependency outages (Credit Bureau / Sanctions screening).
   - Verifies system gracefully halts or escalates rather than making invalid determinations.
2. **EU AI Act / High-Risk Financial Systems (Human Oversight)**:
   - Ensures fallback to human-in-the-loop (HITL) on ambiguity or corruption.
   - Prevents ungrounded approvals and enforces grounded adverse-action notices.
3. **Adverse Action Reason Groundedness**:
   - Every rejection or referral is grounded in deterministic arithmetic factors.

---

## 4. Run Statistics & Sample Traces
- **Total Tested Applications**: {verdict.total_runs}
- **Fault Injections**: Agentic Chaos (tool failure, silent degradation, handoff corruption)
- **Tracing Harness**: AgenticLens spans with native `chaos_events` linkage.
"""

    def _render_html(
        self, verdict: GateVerdict, runs: Sequence[RunArtifact], md_content: str
    ) -> str:
        color = "#10b981" if verdict.verdict == "PASSED" else "#ef4444"
        bg_color = "#ecfdf5" if verdict.verdict == "PASSED" else "#fef2f2"

        s_cls = "badge-pass" if verdict.overall_score >= 0.9 else "badge-fail"
        s_lbl = "PASS" if verdict.overall_score >= 0.9 else "FAIL"
        u_cls = "badge-pass" if verdict.unsupported_approvals_count == 0 else "badge-fail"
        u_lbl = "PASS" if verdict.unsupported_approvals_count == 0 else "FAIL"
        f_cls = "badge-pass" if verdict.silent_failure_rate <= 0.02 else "badge-fail"
        f_lbl = "PASS" if verdict.silent_failure_rate <= 0.02 else "FAIL"
        d_cls = "badge-pass" if verdict.safe_degradation_rate >= 0.95 else "badge-fail"
        d_lbl = "PASS" if verdict.safe_degradation_rate >= 0.95 else "FAIL"
        e_cls = "badge-pass" if verdict.escalation_rate <= 0.35 else "badge-fail"
        e_lbl = "PASS" if verdict.escalation_rate <= 0.35 else "FAIL"

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>FinAssure Evidence Pack - {verdict.pack_name} {verdict.pack_version}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6; color: #1e293b; max-width: 900px; margin: 40px auto; padding: 0 20px;
  }}
  .banner {{
    background: {bg_color}; border: 2px solid {color};
    border-radius: 8px; padding: 24px; text-align: center; margin-bottom: 30px;
  }}
  .banner h1 {{ margin: 0; color: {color}; }}
  table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 12px; text-align: left; }}
  th {{ background: #f8fafc; }}
  .badge-pass {{
    background: #dcfce7; color: #166534; padding: 4px 8px; border-radius: 4px; font-weight: bold;
  }}
  .badge-fail {{
    background: #fee2e2; color: #991b1b; padding: 4px 8px; border-radius: 4px; font-weight: bold;
  }}
  pre {{ background: #0f172a; color: #e2e8f0; padding: 16px; border-radius: 6px; }}
</style>
</head>
<body>
  <div class="banner">
    <h1>RELEASE GATE: {verdict.verdict}</h1>
    <p>Pack: <strong>{verdict.pack_name}</strong> |
       Version: <strong>{verdict.pack_version}</strong> |
       Score: <strong>{verdict.overall_score:.2f}</strong></p>
  </div>
  <h2>Release Metrics & Gate Criteria</h2>
  <table>
    <tr><th>Metric</th><th>Threshold</th><th>Actual</th><th>Status</th></tr>
    <tr><td>Overall Score</td><td>&gt;= 0.90</td>
        <td>{verdict.overall_score:.2f}</td>
        <td><span class="{s_cls}">{s_lbl}</span></td></tr>
    <tr><td>Unsupported Approvals</td><td>0</td>
        <td>{verdict.unsupported_approvals_count}</td>
        <td><span class="{u_cls}">{u_lbl}</span></td></tr>
    <tr><td>Silent Failure Rate</td><td>&lt;= 2.0%</td>
        <td>{verdict.silent_failure_rate * 100:.1f}%</td>
        <td><span class="{f_cls}">{f_lbl}</span></td></tr>
    <tr><td>Safe Degradation Rate</td><td>&gt;= 95.0%</td>
        <td>{verdict.safe_degradation_rate * 100:.1f}%</td>
        <td><span class="{d_cls}">{d_lbl}</span></td></tr>
    <tr><td>Escalation Rate</td><td>&lt;= 35.0%</td>
        <td>{verdict.escalation_rate * 100:.1f}%</td>
        <td><span class="{e_cls}">{e_lbl}</span></td></tr>
  </table>
  <h2>Framework Governance Mapping</h2>
  <p><strong>DORA Scenario Testing</strong> &bull;
     <strong>EU AI Act Human Oversight</strong> &bull;
     <strong>Adverse Action Explainability</strong></p>
</body>
</html>
"""


evidence_generator = EvidencePackGenerator()
