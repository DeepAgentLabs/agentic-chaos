# FinAssure

**A reliability and release-gate harness for agentic financial decisioning, built on AgenticLens and Agentic Chaos.**

FinAssure proves that multi-agent financial workflows can fail silently under edge cases and third-party disruptions, detects those failures with fault injection and span tracing, and automatically blocks unsafe releases with a quantifiable release gate.

---

## 🏛️ System Architecture

FinAssure separates the **domain-neutral harness core** from domain-specific **workflow packs**:

```
 ┌───────────────────────────── Workflow packs (plug-ins) ─────────────────────────────┐
 │  Underwriting pack (v1 naive / v2 hardened)        KYC onboarding pack              │
 │  agents · tools · oracle · invariants · synthetic applicant generator               │
 └───────────────────────────────────────┬─────────────────────────────────────────────┘
                                         │ pack contract
 ┌───────────────────────────────────────▼─────────────────────────────────────────────┐
 │ Harness core (domain-neutral)                                                        │
 │  Scenario loader → Experiment runner ──► Agentic Chaos (chaos_session / wrap_tool)   │
 │                         │               AgenticLens (profile / step / trace)         │
 │                         ▼                                                            │
 │  Evaluator registry (deterministic + LLM judge) → Gate engine → Evidence pack        │
 └───────────────────────────────────────┬─────────────────────────────────────────────┘
                                         │ JSON artifacts + SQLite index
 ┌───────────────────────────────────────▼─────────────────────────────────────────────┐
 │ API (FastAPI)  ◄────────►  Clean Interactive Dashboard (HTML5 / Tailwind / SPA)     │
 └──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Configuration & Gemini AI Setup

FinAssure uses the official Google GenAI SDK (`google-genai`). **No API keys or outputs are hardcoded.**

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Paste your Gemini API key in `.env`:
   ```ini
   GEMINI_API_KEY=your_actual_gemini_api_key
   ```
*(Note: If no API key is set yet, FinAssure uses an offline deterministic parser/judge fallback so test suites and local experiments run without error).*

---

## 🚀 Quickstart

Run everything from `examples/finassure` in an agentic-chaos checkout:

```bash
cd examples/finassure
pip install -e ../.. -r requirements.txt pytest
```

### 1. Run the Test Suite
```bash
python -m pytest -v
```

### 2. Seed the Release Gate Baseline
```bash
python scripts/seed_baseline.py
```
This runs every pack's v1 and v2 under the chaos matrix and writes evidence packs to `artifacts/evidence_packs/`.

### 3. Start the Server & Dashboard
```bash
python main.py
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

---

## 📊 Core Features & Workflow

### 1. Loan Underwriting Pack (`packs/underwriting`)
* **5 Agents**: Intake &rarr; Document Extraction &rarr; Bureau Lookup &rarr; Risk Scorer &rarr; Compliance Reviewer.
* **Deterministic Policy Oracle**: Absolute ground truth for every synthetic case; numerical decisions come from deterministic code, not LLMs.
* **v1 (Naive)**: Trusts handoffs blindly; defaults credit scores to 680 on bureau outage, causing **unsupported approvals** and silent failures.
* **v2 (Hardened)**: Schema validation at handoffs, stated-vs-deposit cross-checks, retry with backoff, and strictly escalates to human review (HITL) on missing/corrupted data.

### 2. KYC Onboarding Pack (`packs/kyc`)
* Proves domain neutrality with **zero changes to harness core**.
* 4 Agents: Identity Check &rarr; Sanctions Screening &rarr; Risk Rating &rarr; Reviewer.

### 3. AML Triage Pack (`packs/aml`)
* High-assurance financial workflow pack for transaction monitoring and suspicious activity report (SAR) triage.
* 4 Agents: Transaction Ingestion &rarr; FATF Jurisdiction Screening &rarr; AML Structuring Triage &rarr; Compliance Reviewer.
* Injects FATF greylist outages, halved SWIFT transaction amounts, and dropped jurisdiction handoffs.

### 4. Agentic Chaos & AgenticLens Integration
* **Agentic Chaos**: Injects `ToolCallFailureFault` (bureau outages / timeouts), `SilentDegradationFault` (income manipulation), and `HandoffCorruptionFault`.
* **AgenticLens**: Profiles every agent span (`step`), records tokens, cost, and latency, and links chaos events natively via `attach_events(session, wf)`.

### 4. Automated Release Gate
Enforces 7 strict criteria before allowing code into production:
1. `zero_unsupported_approvals`: Hard-fail if approved without verified bureau/income data.
2. `min_average_score >= 0.90`
3. `max_silent_failure_rate <= 2.0%`
4. `min_safe_degradation_rate >= 95.0%`
5. `max_escalation_rate <= 35.0%` (Prevents "escalate everything" escape hatch).
6. `max_p95_latency <= 4000ms`
7. `max_cost_per_application <= $0.05`

---

## 🧭 5-Minute Demo Walkthrough

1. **Inspect v1 Run in Dashboard**: Select **Loan Underwriting** &rarr; **v1 (Naive)**. View the **Release Gate: BLOCKED** banner with evidence `HARD FAIL: unsupported approval(s) detected`.
2. **Trace Explorer**: Click a faulted run to inspect the **AgenticLens Span Waterfall** with red **`[Agentic Chaos Event Injected]`** badges on `bureau_lookup`.
3. **Switch to v2 (Hardened)**: Select **v2 (Hardened)**. View **Release Gate: PASSED** with 0% silent failures and 100% safe degradation.
4. **Compare View**: Examine the Delta Table showing reliability gained vs operational latency/cost overhead.
5. **Switch to KYC Pack**: Select **KYC Onboarding** to show the harness running a distinct compliance workflow without core changes.
