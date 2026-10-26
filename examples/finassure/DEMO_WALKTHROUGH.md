# FinAssure: 5-Minute Live Demo Script & Walkthrough
**Target Audience:** Risk, Compliance, Engineering Leaders, and Evaluators  
**Estimated Duration:** 5 minutes (300 seconds)  
**Deliverable:** Proving that multi-agent financial systems can fail silently, catching them with Agentic Chaos & AgenticLens, and blocking unsafe releases with automated gates.

---

## ⏱️ Timeline & Step-by-Step Script

### [00:00 - 00:45] Step 1: The Illusion of Reliability (v1 Clean Run)
* **Action:** Open Dashboard (`http://localhost:8000`), select **Loan Underwriting**, version **v1 (Naive)**, click **Run & Trace Explorer**.
* **What to show:** Select a clean baseline run for applicant `APP-42-0001`.
* **Talking point:**
  > *"At first glance, our naive 5-agent underwriting pipeline looks completely healthy. Intake passes to Document Extraction, Credit Bureau lookup succeeds, Risk Scorer calculates DTI, and Compliance Reviewer generates adverse notices. Spans are clean, tokens are low (~180 tokens), and decisions match the policy oracle. But in financial decisioning, clean-path health is an illusion."*

---

### [00:45 - 01:30] Step 2: The Silent Failure (Agentic Chaos Injection)
* **Action:** Switch to a run under the `silent_income_corruption` scenario.
* **What to show:**
  - Trace waterfall highlighting the red **Chaos Fault Marker** on `doc_extraction_agent -> extraction.income`.
  - The extracted annual income was silently halved ($120,000 → $60,000) or digits dropped.
  - Show the decision: Candidate was **DECLINED** or approved on falsified DTI with **zero exceptions thrown**, **zero logs raised**, and **no alerts triggered**.
* **Talking point:**
  > *"Notice what happened here: Agentic Chaos injected a silent degradation into the extraction boundary. In v1, downstream agents trust upstream handoffs implicitly. The risk scorer computed an inflated DTI and declined a prime borrower. The system operated without errors, yet failed silently and catastrophically."*

---

### [01:30 - 02:15] Step 3: Automated Release Gate Enforcement (v1 Fails)
* **Action:** Click on the **Release Gate Overview** tab for v1.
* **What to show:**
  - Red **RELEASE GATE: BLOCKED** banner.
  - KPI tiles:
    - **Unsupported Approvals:** 12 (Hard Fail triggered)
    - **Silent Failure Rate:** 16.7% (Max allowed: 2.0%)
    - **Gate Checklist:** Fails on zero unsupported approvals and silent failure rate.
* **Talking point:**
  > *"When we run the complete chaos matrix across bureau outages, timeouts, empty payloads, and handoff drops, the release gate immediately blocks release v1. It provides cryptographic evidence: 12 candidates were approved without verified credit bureau files because v1 defaulted missing scores to 680."*

---

### [02:15 - 03:15] Step 4: The Hardened Pipeline (v2 Passes the Gate)
* **Action:** Toggle the version dropdown in the top header from **v1 (Naive)** to **v2 (Hardened)**.
* **What to show:**
  - Green **RELEASE GATE: PASSED** banner with **99.2% overall score**.
  - **Unsupported Approvals:** 0.
  - **Safe Degradation Rate:** 100.0% (target ≥ 95%).
  - Open **Decision Audit** tab and inspect `APP-42-0006`:
    - Show the **Income Cross-Check**: Stated income vs 90-day bank deposit inflows caught the discrepancy.
    - Status: Safely escalated to `HITL Review Queue` with reason `INCOME_VERIFICATION_DISCREPANCY`.
* **Talking point:**
  > *"In v2, we introduced a systematic hardening layer: strict contract schemas at every handoff, dual-source income cross-checking against bank statements, rate-limit backoff, reviewer turn caps, and a human-in-the-loop escalation queue. When the bureau goes down or income is corrupted, v2 never guesses or defaults—it safely degrades to human review."*

---

### [03:15 - 04:00] Step 5: Version Comparison & Reliability ROI
* **Action:** Click the **Compare v1 vs v2** tab.
* **What to show:**
  - **Reliability Gained:**
    - Silent failure reduction: **-16.7%**
    - Safe degradation gain: **+33.3%**
    - Unsupported approvals eliminated: **12 → 0**
  - **Operational Overhead:**
    - Compute cost delta: **+$0.0013 / application** ($0.0015 → $0.0028)
    - Latency delta: **+55 ms** (well below the 4,000 ms SLA)
* **Talking point:**
  > *"FinAssure doesn't just judge reliability; it quantifies the engineering trade-off. By adding contract validation, our cost increased by a fraction of a cent per application, while eliminating 100% of catastrophic unsupported approvals."*

---

### [04:00 - 04:45] Step 6: Domain Genericity (KYC Onboarding Pack)
* **Action:** Switch the Pack dropdown from **Loan Underwriting** to **KYC Onboarding**.
* **What to show:**
  - Show the KYC pipeline (Identity Check → Sanctions/PEP Screening → Risk Rating → Reviewer).
  - Open the **Topology** tab to show the multi-agent graph with watchlist fault interceptors.
  - Show the KYC v2 gate verdict: **PASSED** with 100% safe degradation.
* **Talking point:**
  > *"FinAssure is not a bespoke lending app. It is a domain-neutral reliability harness. Here is our second workflow pack: KYC and Sanctions Onboarding. It plugged into the exact same harness core, evaluators, runner, and release gate without changing a single line of harness core code."*

---

### [04:45 - 05:00] Step 7: Conclusion & Audit Evidence Export
* **Action:** Click **Download HTML Report** in the top right.
* **Talking point:**
  > *"With one command, FinAssure exports audit-ready evidence packs mapped to DORA operational resilience and EU AI Act human-oversight principles. You now have automated verification that your financial agents fail safely before shipping to production."*
