# FinAssure: Regulatory & Resilience Framework Mapping

> **Disclaimer:** This document provides an architectural mapping of automated testing techniques to regulatory resilience and oversight themes. FinAssure operates exclusively on synthetic data and deterministic policy rules. This document does not constitute legal, credit, or regulatory compliance certification.

---

## 1. DORA (Digital Operational Resilience Act - EU 2022/2554)

### Background & Requirement
Under DORA Chapter IV (Digital Operational Resilience Testing) and Articles 24–27, financial entities must establish comprehensive digital resilience testing programs. Systems relying on third-party ICT services (such as credit reporting agencies, AML databases, or external AI providers) must prove their capacity to withstand disruptions without critical service degradation.

### FinAssure Architectural Mapping
| DORA Theme | FinAssure Implementation | Verification Evidence |
|---|---|---|
| **ICT Dependency Outage Testing (Art. 25)** | Injected `ToolCallFailureFault` (mode: `error`, `timeout`, `empty`) into Credit Bureau (`bureau_lookup`) and Sanctions APIs. | Release gate blocks any release where an ICT dependency outage results in unverified approvals (`unsupported_approvals = 0`). |
| **Silent Degradation & Data Integrity (Art. 26)** | Injected `SilentDegradationFault` (halving stated income) and `MemoryCorruptionFault` (state decay). | Hardened v2 schema contracts detect type mutations and data drift, safely escalating to manual review. |
| **Resilience Reporting (Art. 28)** | Automated evidence package generator exporting machine-readable (JSON/CSV) and human-auditable (HTML/Markdown) experiment summaries. | Per-release audit trails capturing scenario hypotheses, fault parameters, execution latencies, and gate verdicts. |

---

## 2. EU AI Act (High-Risk AI Systems - Regulation EU 2024/1689)

### Background & Requirement
Annex III, Point 5 classifies AI systems intended to be used to evaluate creditworthiness or establish credit scores as **High-Risk AI Systems**. Article 14 establishes strict mandates for **Human Oversight (HITL)**, while Article 15 mandates accuracy, robustness, and cybersecurity resilience against anomalous inputs.

### FinAssure Architectural Mapping
| AI Act Mandate | FinAssure Implementation | Verification Evidence |
|---|---|---|
| **Human Oversight (Article 14)** | Human-in-the-Loop (HITL) escalation queue triggered whenever contract validation fails, income discrepancies emerge, or sanctions match. | Gate rule `min_safe_degradation_rate >= 0.95` guarantees faulted runs escalate to human oversight rather than deciding autonomously. |
| **Over-Escalation Prevention (Article 14.4)** | Gate rule `max_escalation_rate <= 0.35` on clean baseline traffic. | Prevents naive hardening systems from passing compliance by simply escalating all routine traffic to human queues. |
| **Robustness Against Faults (Article 15)** | Chaos scenario library testing edge cases: runaway reviewer loops (`infinite_loop`), throttling (`rate_limit_storm`), and handoff drops. | Enforces turn limits (`MAX_TURNS = 3`), retry backoff, and trace-aware tool execution auditing. |
| **Explainability & Transparency (Article 13)** | Grounding adverse action notices in actual deterministic factors (`oracle.reason_factors`), evaluated via LLM Judge (`eval_reason_fidelity`). | Eliminates hallucinated rejection reasons; verified by factor intersection checks. |

---

## 3. Fair Lending & Adverse Action Notice Compliance (US ECOA / FCRA)

### Background & Requirement
The Equal Credit Opportunity Act (ECOA, 15 U.S.C. 1691 et seq.) and Regulation B (12 CFR Part 1002) require creditors to provide specific principal reasons for adverse action (denial or unfavorable terms). Reasons must accurately reflect the factors considered and must not be hallucinated or generic.

### FinAssure Architectural Mapping
| Fair Lending Principle | FinAssure Implementation | Verification Evidence |
|---|---|---|
| **Factor Groundedness** | Decoupling: Arithmetic credit scoring and factor extraction are performed by deterministic Python functions (`underwriting_oracle`), never by generative LLMs. | `eval_reason_fidelity` LLM Judge checks that compliance narratives cite only factors present in the calculated factor list. |
| **Disparate Resilience Parity** | `eval_disparate_resilience` calculates the difference in silent failure rates across synthetic demographic/credit-history cohorts (`established`, `thin_file`, `gig_economy`). | Release gate flags releases if resilience disparity gap exceeds the policy threshold (`max_gap <= 0.15`). |
| **No Discriminatory Model Inputs** | Synthetic group tags (`synthetic_group`) are isolated for post-hoc bias auditing only; they are never passed into agent prompts or decisioning schemas. | Code audit confirms `group` is excluded from agent pipeline payloads. |

---

## 4. Summary of Evidence Packaging for Auditors

FinAssure releases generate an audit evidence package (JSON, CSV, HTML and Markdown) containing:
1. **Scenario Registry:** Hypotheses, fault injection types, targets, and expected unsafe outcomes.
2. **Execution Traces:** Span-level token consumption, latency, and chaos event intercept markers.
3. **Deterministic Oracle Alignment:** Ground-truth baseline decision comparisons for all synthetic cases.
4. **Gate Rule Checklist:** Pass/fail status on all 7 reliability thresholds.
