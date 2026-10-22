/**
 * DeepAgentLabs - Dual-Mode Interactive Storytelling Experience
 * Modes:
 *   1. 'executive': CFO & Business Leader Comprehension (Dollars, Risk, Plain English, Digital Coworkers)
 *   2. 'technical': Engineering Architecture (Spans, JSON Schemas, CLI Sandbox, Python Decorators, OTLP)
 */

(function () {
  'use strict';

  // State Management
  let currentActIndex = 0;
  let viewMode = 'executive'; // 'executive' or 'technical'
  let isTourActive = false;
  let tourInterval = null;

  // Active Chaos Fault State
  const activeFaults = {
    bank_timeout: true,
    missing_income: false,
    corrupted_data: false,
    rate_throttle: false
  };

  // Full AI Ops Spec Data
  const RAW_SPEC = {
    "$schema": "https://deepagentlabs.io/schemas/ai-ops-spec-v1.json",
    "spec_version": "1.0.0",
    "metadata": {
      "spec_id": "spec_prod_pa_9042_c10",
      "generator": "AgenticLens v1.4.2",
      "captured_at": "2026-10-22T02:14:18.421Z",
      "environment": "production-us-east-cluster-04",
      "workload": "clinical-prior-authorization",
      "incident_tag": "INC-8842-SILENT-FAIL"
    },
    "workflow": {
      "name": "CardiologyPriorAuthPipeline",
      "version": "1.0.4-prod",
      "case_id": "PA-9042",
      "patient": {
        "patient_id": "SYN-PT-88219",
        "age": 58,
        "gender": "male",
        "urgency": "STAT",
        "requested_procedure": "Coronary Angioplasty with Stenting (CPT 92928)",
        "primary_dx": "Unstable Angina Pectoris (ICD-10 I20.0)"
      },
      "topology": [
        { "agent_id": "intake_agent", "model": "claude-3-5-sonnet", "status": "COMPLETED", "duration_ms": 780, "tokens": 1560 },
        { "agent_id": "ehr_retriever", "tool": "epic_fhir_retriever", "status": "DEGRADED_EMPTY", "duration_ms": 4210, "anomaly": "EPIC FHIR API 4.2s timeout; fallback returned empty array without error" },
        { "agent_id": "policy_judge", "model": "gpt-4o", "status": "COMPLETED", "duration_ms": 1120, "tokens": 4220, "failure_mode": "Silent Assumption: Evaluated empty array as 'no prior conservative therapy'" },
        { "agent_id": "decision_agent", "model": "gpt-4o-mini", "status": "COMPLETED", "duration_ms": 640, "tokens": 1100 }
      ],
      "execution_summary": {
        "total_duration_ms": 6750,
        "total_cost_usd": 0.0333,
        "total_tokens": 6880,
        "final_decision": "DENIED",
        "incident_type": "SILENT_ADVERSE_DECISION",
        "http_status": 200,
        "exceptions_logged": 0
      }
    }
  };

  // --- Story Data: Executive Mode ---
  const STORY_ACTS_EXECUTIVE = [
    {
      actNumber: 1,
      badge: "PHASE 1 · THE REALITY CHECK",
      heading: "The $500,000 Silent Mistake",
      impactTag: "⚠️ $500,000 Unverified Check Issued · 0 Alarms Raised",
      impactSafe: false,
      tickerExposure: "$500,000",
      tickerErrors: "1 (Catastrophic)",
      tickerStatus: "Silent Blindspot",
      tickerClass: "red",
      narrative: "Imagine your credit department has 4 digital workers. Alex scans the application, Sam checks the credit bureau, Jordan calculates debt, and Morgan signs the check. At 2:14 AM, the credit bureau has a 3-second network freeze. Instead of raising a hand or asking for a manager, Sam hands a blank folder to Jordan! Jordan thinks 'Great, zero debt!', and Morgan signs a $500,000 check to an applicant with massive hidden debt. The computer systems report 100% success because no code crashed.",
      takeawayTitle: "Why Traditional IT Monitoring Misses This:",
      takeawayDesc: "Standard IT dashboards only check if a server crashed. They never check if the business decision made any financial sense. You just lost half a million dollars in total silence.",
      media: "./assets/cfo_risk.jpg",
      mediaCaption: "The Executive Blindspot: Systems report green health while bad checks slip out the door.",
      nextBtnText: "See How DeepAgentLabs Catches This →"
    },
    {
      actNumber: 2,
      badge: "PHASE 2 · OBSERVE & CAPTURE",
      heading: "The Digital Flight Recorder",
      impactTag: "🔍 100% Complete Decision Audit Trail · Every Cent Accounted For",
      impactSafe: true,
      tickerExposure: "$500,000 Flagged",
      tickerErrors: "Audit Trail Captured",
      tickerStatus: "Incident Frozen",
      tickerClass: "gold",
      narrative: "When your leadership team discovers the bad approval the next morning, nobody has to spend three days in post-mortem meetings guessing what happened. Like an airplane's black box flight recorder, AgenticLens automatically recorded every single handoff, decision factor, and database query across your digital team. In one click, the entire event is captured into a standardized replay contract.",
      takeawayTitle: "The Executive Advantage:",
      takeawayDesc: "No more engineering excuses. You have verifiable, tamper-proof evidence of the exact second where digital communication broke down.",
      media: "./assets/relay_workers.jpg",
      mediaCaption: "AgenticLens acts like an omnipresent digital auditor across every automated employee.",
      nextBtnText: "Replay in Safe Simulator →"
    },
    {
      actNumber: 3,
      badge: "PHASE 3 · SAFE REPLAY",
      heading: "The Zero-Risk Flight Simulator",
      impactTag: "⚡ 100% Exact Reproduction in 1.8s · $0 Live Capital at Risk",
      impactSafe: true,
      tickerExposure: "$0 Real Money Exposed",
      tickerErrors: "Sandbox Repro Confirmed",
      tickerStatus: "Safe Sandbox Active",
      tickerClass: "gold",
      narrative: "You would never test an emergency airplane maneuver with paying passengers onboard. Similarly, DeepAgentLabs allows your developers to import the production failure into a secure digital simulator on their laptop. In under 2 seconds, the exact failure is reproduced with zero risk to your company's balance sheet, zero patient or customer privacy leakage, and zero live API costs.",
      takeawayTitle: "Why CFOs Love This:",
      takeawayDesc: "Fixing AI in production risks real customer dollars. A deterministic simulator lets your team test fixes unlimited times for free before touching real money.",
      media: "./assets/hero.jpg",
      mediaCaption: "Deterministic replay safely freezes and reproduces edge-case failures locally.",
      nextBtnText: "Run the Surprise Fire Drill →"
    },
    {
      actNumber: 4,
      badge: "PHASE 4 · STRESS TEST",
      heading: "The Automated Fire Drill",
      impactTag: "🌪️ 4 Real-World Surprises Injected · 3 Hidden Blindspots Caught",
      impactSafe: false,
      tickerExposure: "$1,850,000 Tested",
      tickerErrors: "3 Vulnerabilities Discovered",
      tickerStatus: "Stress Matrix Active",
      tickerClass: "red",
      narrative: "Fixing one bug isn't enough. What happens if a credit bureau goes down next Tuesday? What if an applicant's tax returns are blurry? Agentic-Chaos acts like an automated surprise fire drill. It deliberately throws realistic operational curveballs at your AI team to see where they guess or stumble before your real customers ever notice.",
      takeawayTitle: "Proactive Defense:",
      takeawayDesc: "Don't wait for regulators or customers to find your AI's blindspots. Find them yourself in a controlled stress lab.",
      media: "./assets/chaos.jpg",
      mediaCaption: "Agentic-Chaos tests how your autonomous systems behave under worst-case operational stress.",
      nextBtnText: "Install Safety Circuit Breakers →"
    },
    {
      actNumber: 5,
      badge: "PHASE 5 · AUDIT & HARDEN",
      heading: "Smart Business Circuit Breakers",
      impactTag: "🛡️ 100% Safe Escalation · 0 Unverified Approvals Across 120 Cases",
      impactSafe: true,
      tickerExposure: "$0 Capital Lost",
      tickerErrors: "0.0% Silent Failures",
      tickerStatus: "Guardrails Active",
      tickerClass: "green",
      narrative: "Armed with the chaos test findings, your team implements an inviolable business rule: 'If verified income or credit proof is missing, the AI is strictly forbidden from guessing. It must automatically route the file to Elena, our Human Underwriting Manager.' When tested across 120 worst-case scenarios, the hardened AI team performed with 100% compliance.",
      takeawayTitle: "The Balanced Workplace:",
      takeawayDesc: "AI handles 90% of routine work at lightning speed, but seamlessly escalates ambiguous edge cases to your human experts.",
      media: "./assets/relay_workers.jpg",
      mediaCaption: "Hardened guardrails automatically divert inconclusive applications to human managers.",
      nextBtnText: "Enforce the CFO Release Gate →"
    },
    {
      actNumber: 6,
      badge: "PHASE 6 · PRODUCTION RELEASE",
      heading: "The CFO Automated Quality Gate",
      impactTag: "✅ Release Approved (Score: 99.4/100) · Auto-Deployed to Production",
      impactSafe: true,
      tickerExposure: "$0 Exposure · 100% Protected",
      tickerErrors: "0 Unverified Approvals",
      tickerStatus: "Production Certified",
      tickerClass: "green",
      narrative: "In a world with strict compliance laws, no new AI model or prompt should go live without an executive seal of approval. The DeepAgentLabs Release Gate acts like an automated CFO audit signature: it evaluates the evidence pack against your risk tolerances and only greenlights deployment when compliance is 100% proven.",
      takeawayTitle: "The Continuous AgenticOps Flywheel:",
      takeawayDesc: "Every production incident makes your automated enterprise smarter, safer, and more resilient. You scale revenue without scaling risk.",
      media: "./assets/release_gate.jpg",
      mediaCaption: "Automated Release Gates guarantee only tested, compliant AI enters production.",
      nextBtnText: "Explore Full Technical Architecture & Harness →"
    }
  ];

  // --- Story Data: Technical Mode ---
  const STORY_ACTS_TECHNICAL = [
    {
      actNumber: 1,
      badge: "TRACE 01 · SPAN DEGRADATION",
      heading: "Silent EHR Boundary Timeout",
      impactTag: "⚡ HTTP 200 OK · Tool Latency: 4,210ms · Silent Adverse Decision",
      impactSafe: false,
      tickerExposure: "6,880 Tokens",
      tickerErrors: "Tool Timeout Fallback",
      tickerStatus: "Degraded Empty Payload",
      tickerClass: "red",
      narrative: "Execution trace run_prod_cardio_9042 initiated under STAT urgency. Intake Agent parsed clinical notes into JSON schema. During the third span, tool 'epic_fhir_retriever' suffered an ephemeral 4,210ms timeout and returned fallback array { stress_tests: [] } without raising an HTTP 500 error. Downstream GPT-4o policy evaluator evaluated empty array as negative evidence and triggered an unverified adverse denial.",
      takeawayTitle: "Architectural Failure Analysis:",
      takeawayDesc: "Lack of invariant schema contracts between tool outputs and prompt inputs allowed an unhandled tool degradation to propagate as verified clinical truth.",
      media: "./assets/incident.jpg",
      mediaCaption: "Production Telemetry Waterfall: Span 2 degraded without throwing an exception.",
      nextBtnText: "Generate AI Ops Spec JSON →"
    },
    {
      actNumber: 2,
      badge: "TRACE 02 · SPEC SERIALIZATION",
      heading: "Hermetic AI Ops Spec Capture",
      impactTag: "📦 AI Ops Spec Schema v1.0.0 · OTLP Instrumentation Exported",
      impactSafe: true,
      tickerExposure: "$0.0333 Compute",
      tickerErrors: "Spec Serialized",
      tickerStatus: "Hermetic Contract Ready",
      tickerClass: "gold",
      narrative: "AgenticLens intercepted the multi-agent execution at the OpenTelemetry layer. It captured model temperatures, input prompt tokens, raw tool invocation boundaries, and serialized execution states into a canonical AI Ops Spec JSON file. The entire multi-agent state space is preserved for deterministic shift-left replay.",
      takeawayTitle: "Open Specification Contract:",
      takeawayDesc: "The AI Ops Spec defines deterministic replay boundaries, mock fixtures, and policy oracle assertions without coupling to live backend infrastructure.",
      media: "./assets/hero.jpg",
      mediaCaption: "Standardized AI Ops Spec encapsulating topology, inputs, and intermediate states.",
      nextBtnText: "Execute Local Replay Sandbox →"
    },
    {
      actNumber: 3,
      badge: "TRACE 03 · DETERMINISTIC REPLAY",
      heading: "Local Sandbox Execution Engine",
      impactTag: "⚡ Replay Fidelity: 100% · Duration: 1.78s · Local Container",
      impactSafe: true,
      tickerExposure: "0 Remote APIs",
      tickerErrors: "Defect Reproduced",
      tickerStatus: "Local Replay Active",
      tickerClass: "gold",
      narrative: "Using 'agenticlens replay --spec spec_incident_9042.json', the incident was reproduced in Maya's local development environment in 1.78s. AgenticLens mocked the external EPIC FHIR boundary using captured payload parameters, eliminating cloud API latencies and preserving HIPAA/PII compliance.",
      takeawayTitle: "Shift-Left Engineering Advantage:",
      takeawayDesc: "Reproducing non-deterministic multi-agent edge cases locally accelerates mean time to resolution (MTTR) from days to minutes.",
      media: "./assets/hero.jpg",
      mediaCaption: "Deterministic replay sandbox reproducing production execution in 1.78s.",
      nextBtnText: "Inject Fault Matrix with Chaos →"
    },
    {
      actNumber: 4,
      badge: "TRACE 04 · CHAOS FAULT MATRIX",
      heading: "Agentic-Chaos Fault Injection",
      impactTag: "🌪️ 4 Chaos Primitives Tested · 3 Silent Invariant Failures Caught",
      impactSafe: false,
      tickerExposure: "4 Chaos Vectors",
      tickerErrors: "3 Silent Failures",
      tickerStatus: "Fault Matrix Active",
      tickerClass: "red",
      narrative: "Maya subjected the pipeline to the Agentic-Chaos Python suite: wrapping tool calls with ToolCallFailureFault(mode='timeout_empty'), extracting boundaries with SilentDegradationFault(drop_keys=['troponin']), and injecting HTTP 429 RateLimitStorms. 3 out of 4 tests proved the naive pipeline failed silently.",
      takeawayTitle: "Resilience Engineering Principle:",
      takeawayDesc: "Agent architectures must be stress-tested with intentional data degradation, API dropouts, and state corruptions prior to release.",
      media: "./assets/chaos.jpg",
      mediaCaption: "Agentic-Chaos testing tool outages, payload corruption, and rate limit storms.",
      nextBtnText: "Inspect Evals & Invariant Scoring →"
    },
    {
      actNumber: 5,
      badge: "TRACE 05 · INVARIANT AUDIT",
      heading: "Agentic-Evals Invariant Matrix",
      impactTag: "🛡️ Invariant Adherence: 100% · P99 Latency: 3.8s · Token Spend: -43.7%",
      impactSafe: true,
      tickerExposure: "120 Synthetic Runs",
      tickerErrors: "0 Unsupported Approvals",
      tickerStatus: "Evaluation Suite Passed",
      tickerClass: "green",
      narrative: "Maya hardened the pipeline (v2): adding strict Pydantic validation contracts, dual-source EHR cross-checking, and turn-capped reasoning loops. Agentic-Evals benchmarked 120 test cases against a deterministic policy oracle. Silent failures dropped to 0.0%, and unsupported denials dropped to zero.",
      takeawayTitle: "Deterministic Invariant Oracles:",
      takeawayDesc: "Rather than relying solely on subjective LLM-as-a-judge evaluation, Agentic-Evals scores objective mathematical invariants against verifiable ground truth.",
      media: "./assets/relay_workers.jpg",
      mediaCaption: "Hardened pipeline v2.0.0 benchmarked against 120 synthetic test cases.",
      nextBtnText: "Inspect CI/CD Release Gate →"
    },
    {
      actNumber: 6,
      badge: "TRACE 06 · GATE ENFORCEMENT",
      heading: "CI/CD Gate & Cryptographic Audit",
      impactTag: "✅ Release Gate: APPROVED · Score: 99.4/100 · SHA-256 Merkle Proof",
      impactSafe: true,
      tickerExposure: "PR #142 Merged",
      tickerErrors: "0 Gate Violations",
      tickerStatus: "Production Deployed",
      tickerClass: "green",
      narrative: "In GitHub Actions, the AgenticLens Release Gate evaluated PR #142 against the evidence pack. With 100% invariant adherence and 0 unsupported decisions, the release gate generated a cryptographic audit seal and auto-deployed v2.0.0 to US-East production with active OpenTelemetry tracing.",
      takeawayTitle: "Continuous AgenticOps Lifecycle:",
      takeawayDesc: "Production executions continuously become reusable test scenarios, creating a permanent hardening feedback loop.",
      media: "./assets/release_gate.jpg",
      mediaCaption: "Automated Release Gate approving hardened multi-agent pipeline for production.",
      nextBtnText: "Explore Full Technical Architecture & Harness →"
    }
  ];

  // --- DOM Elements ---
  const elStepCards = document.querySelectorAll(".step-card");
  const elStoryActTag = document.getElementById("story-act-tag");
  const elStoryHeading = document.getElementById("story-heading");
  const elStoryFinancialImpact = document.getElementById("story-financial-impact");
  const elStoryBodyText = document.getElementById("story-body-text");
  const elTakeawayTitle = document.getElementById("takeaway-title");
  const elTakeawayDesc = document.getElementById("takeaway-desc");
  const elSpotlightImg = document.getElementById("spotlight-img");
  const elSpotlightCaption = document.getElementById("spotlight-caption");
  const elBtnAdvance = document.getElementById("btn-advance-story");
  const elBtnPrev = document.getElementById("btn-prev-story");
  const elTourBtn = document.getElementById("btn-tour-toggle");
  const elCockpitTitle = document.getElementById("cockpit-main-title");
  const elCockpitPill = document.getElementById("cockpit-pill");
  const elCockpitDynamic = document.getElementById("cockpit-dynamic-area");
  const elBriefcaseText = document.getElementById("briefcase-text");

  // Hero DOM Elements
  const elHeroTagline = document.querySelector(".hero-tagline span:last-child");
  const elHeroTitle = document.querySelector(".hero-title");
  const elHeroDesc = document.querySelector(".hero-desc");
  const elAnalogyBox = document.querySelector(".cfo-analogy-box");

  // Ticker DOM Elements
  const elTickerExposure = document.getElementById("ticker-exposure");
  const elTickerErrors = document.getElementById("ticker-errors");
  const elTickerStatus = document.getElementById("ticker-status");
  const elTickerLabelExposure = document.querySelectorAll(".ticker-label")[0];
  const elTickerLabelErrors = document.querySelectorAll(".ticker-label")[1];
  const elTickerLabelStatus = document.querySelectorAll(".ticker-label")[2];

  // Mode buttons
  const elBtnModeExec = document.getElementById("btn-mode-exec");
  const elBtnModeTech = document.getElementById("btn-mode-tech");

  // Assembly / Topology Stage Header
  const elConveyorStageHeader = document.querySelector(".conveyor-stage div:first-child");

  // --- Render Act Function ---
  function renderAct(index) {
    if (index < 0 || index >= 6) return;
    currentActIndex = index;
    const act = (viewMode === 'executive') ? STORY_ACTS_EXECUTIVE[index] : STORY_ACTS_TECHNICAL[index];

    // Update Step Bar
    elStepCards.forEach((c, i) => {
      c.classList.toggle("active", i === index);
      c.classList.toggle("completed", i < index);
    });

    // Update Story Content
    elStoryActTag.textContent = act.badge;
    elStoryHeading.textContent = act.heading;
    elStoryFinancialImpact.textContent = act.impactTag;
    elStoryFinancialImpact.className = act.impactSafe ? "story-financial-impact safe" : "story-financial-impact";
    elStoryBodyText.textContent = act.narrative;
    elTakeawayTitle.textContent = act.takeawayTitle;
    elTakeawayDesc.textContent = act.takeawayDesc;
    elSpotlightImg.src = act.media;
    elSpotlightCaption.innerHTML = `<span>${act.mediaCaption}</span> <span style="font-weight: 800; color: var(--accent-cyan);">ACT ${act.actNumber} OF 6</span>`;
    elBtnAdvance.textContent = act.nextBtnText;

    // Prev Button Visibility
    elBtnPrev.style.display = index === 0 ? "none" : "block";

    // Update Ticker
    elTickerExposure.textContent = act.tickerExposure;
    elTickerExposure.className = `ticker-value ${act.tickerClass}`;
    elTickerErrors.textContent = act.tickerErrors;
    elTickerErrors.className = `ticker-value ${act.tickerClass}`;
    elTickerStatus.textContent = act.tickerStatus;
    elTickerStatus.className = `ticker-value ${act.tickerClass}`;

    // Update Visual Assembly Line vs DAG Topology
    updateConveyorWorkers(index);

    // Update Cockpit Dynamic Content
    renderCockpitView(index);
  }

  // --- Update Assembly Line vs DAG Topology ---
  function updateConveyorWorkers(actIndex) {
    const cardAlex = document.getElementById("card-worker-alex");
    const cardSam = document.getElementById("card-worker-sam");
    const cardJordan = document.getElementById("card-worker-jordan");
    const cardMorgan = document.getElementById("card-worker-morgan");
    const cardElena = document.getElementById("card-worker-elena");

    const cards = [cardAlex, cardSam, cardJordan, cardMorgan, cardElena];
    cards.forEach(c => {
      if (c) c.classList.remove("active-worker", "faulted-worker", "protected-worker");
    });

    if (viewMode === 'executive') {
      // Executive Conveyor Cards
      if (cardAlex) {
        cardAlex.querySelector(".worker-avatar").textContent = "📄";
        cardAlex.querySelector(".worker-name").textContent = "Alex";
        cardAlex.querySelector(".worker-job").textContent = "Document Reader";
        cardAlex.querySelector(".worker-status-badge").textContent = "Intake";
      }
      if (cardSam) {
        cardSam.querySelector(".worker-avatar").textContent = "🔍";
        cardSam.querySelector(".worker-name").textContent = "Sam ⚠️";
        cardSam.querySelector(".worker-job").textContent = "Credit Investigator";
        cardSam.querySelector(".worker-status-badge").textContent = "API Timed Out";
      }
      if (cardJordan) {
        cardJordan.querySelector(".worker-avatar").textContent = "⚖️";
        cardJordan.querySelector(".worker-name").textContent = "Jordan";
        cardJordan.querySelector(".worker-job").textContent = "Risk Calculator";
        cardJordan.querySelector(".worker-status-badge").textContent = "Assumed Zero Debt";
      }
      if (cardMorgan) {
        cardMorgan.querySelector(".worker-avatar").textContent = "✍️";
        cardMorgan.querySelector(".worker-name").textContent = "Morgan";
        cardMorgan.querySelector(".worker-job").textContent = "Check Signer";
        cardMorgan.querySelector(".worker-status-badge").textContent = "Approved $500k";
      }
      if (cardElena) {
        cardElena.querySelector(".worker-avatar").textContent = "👩‍💼";
        cardElena.querySelector(".worker-name").textContent = "Elena";
        cardElena.querySelector(".worker-job").textContent = "Human Supervisor";
        cardElena.querySelector(".worker-status-badge").textContent = "Safety Net Desk";
      }

      if (actIndex === 0) {
        if (cardSam) cardSam.classList.add("faulted-worker");
        if (cardMorgan) cardMorgan.classList.add("faulted-worker");
        elBriefcaseText.innerHTML = `<span style="color: var(--accent-rose);">🚨 CORRUPTED BRIEFCASE: Missing income proof! Moving directly to Morgan for $500k check approval!</span>`;
      } else if (actIndex === 1) {
        cards.forEach(c => c && c.classList.add("active-worker"));
        elBriefcaseText.innerHTML = `<span style="color: var(--accent-cyan);">📹 AGENTICLENS RECORDING: All digital handoffs and briefcase contents recorded into audit spec.</span>`;
      } else if (actIndex === 2) {
        if (cardSam) cardSam.classList.add("active-worker");
        if (cardJordan) cardJordan.classList.add("active-worker");
        elBriefcaseText.innerHTML = `<span style="color: var(--accent-gold);">⚡ ZERO-RISK REPLAY: Replaying the 2:14 AM failure in sandbox container. No money at risk.</span>`;
      } else if (actIndex === 3) {
        if (cardSam) cardSam.classList.add("faulted-worker");
        if (cardAlex) cardAlex.classList.add("faulted-worker");
        elBriefcaseText.innerHTML = `<span style="color: var(--accent-rose);">🌪️ CHAOS INJECTION: Testing digital workers against 4 realistic operational disasters.</span>`;
      } else if (actIndex >= 4) {
        cards.forEach(c => c && c.classList.add("protected-worker"));
        if (cardElena) cardElena.classList.add("active-worker");
        elBriefcaseText.innerHTML = `<span style="color: var(--accent-emerald);">🛡️ CIRCUIT BREAKER TRIPPED: Inconclusive file safely diverted to Elena (Human Manager Desk)!</span>`;
      }
    } else {
      // Technical Mode: Multi-Agent DAG Architecture
      if (cardAlex) {
        cardAlex.querySelector(".worker-avatar").textContent = "⚡";
        cardAlex.querySelector(".worker-name").textContent = "intake_agent";
        cardAlex.querySelector(".worker-job").textContent = "claude-3-5-sonnet";
        cardAlex.querySelector(".worker-status-badge").innerHTML = `<span class="dag-node-badge">780ms · 1.5k tok</span>`;
      }
      if (cardSam) {
        cardSam.querySelector(".worker-avatar").textContent = "🔧";
        cardSam.querySelector(".worker-name").textContent = "ehr_retriever ⚠️";
        cardSam.querySelector(".worker-job").textContent = "tool: epic_fhir_v4";
        cardSam.querySelector(".worker-status-badge").innerHTML = `<span class="dag-node-badge" style="color: #FDA4AF; border-color: #F43F5E;">4,210ms · Tool Error</span>`;
      }
      if (cardJordan) {
        cardJordan.querySelector(".worker-avatar").textContent = "🧠";
        cardJordan.querySelector(".worker-name").textContent = "policy_judge";
        cardJordan.querySelector(".worker-job").textContent = "gpt-4o · temp=0";
        cardJordan.querySelector(".worker-status-badge").innerHTML = `<span class="dag-node-badge">1,120ms · 4.2k tok</span>`;
      }
      if (cardMorgan) {
        cardMorgan.querySelector(".worker-avatar").textContent = "📋";
        cardMorgan.querySelector(".worker-name").textContent = "decision_agent";
        cardMorgan.querySelector(".worker-job").textContent = "gpt-4o-mini";
        cardMorgan.querySelector(".worker-status-badge").innerHTML = `<span class="dag-node-badge">640ms · 1.1k tok</span>`;
      }
      if (cardElena) {
        cardElena.querySelector(".worker-avatar").textContent = "🔀";
        cardElena.querySelector(".worker-name").textContent = "hitl_dlq";
        cardElena.querySelector(".worker-job").textContent = "SQS Dead-Letter";
        cardElena.querySelector(".worker-status-badge").innerHTML = `<span class="dag-node-badge" style="color: #6EE7B7; border-color: #10B981;">v2 Safe Fallback</span>`;
      }

      if (actIndex === 0) {
        if (cardSam) cardSam.classList.add("faulted-worker");
        if (cardMorgan) cardMorgan.classList.add("faulted-worker");
        elBriefcaseText.innerHTML = `<span style="font-family: var(--font-mono); color: #FDA4AF;">[SPAN_FAIL] ehr_retriever returned HTTP 200 with empty payload [] | Silent degradation unhandled</span>`;
      } else if (actIndex === 1) {
        cards.forEach(c => c && c.classList.add("active-worker"));
        elBriefcaseText.innerHTML = `<span style="font-family: var(--font-mono); color: #7DD3FC;">[OTEL_EXPORT] Traced 4 spans (6,880 tokens, 6,750ms). Serialized to spec_prod_pa_9042_c10.json</span>`;
      } else if (actIndex === 2) {
        if (cardSam) cardSam.classList.add("active-worker");
        if (cardJordan) cardJordan.classList.add("active-worker");
        elBriefcaseText.innerHTML = `<span style="font-family: var(--font-mono); color: #FDE68A;">[REPLAY_ENGINE] Loaded mock boundary fixtures. Local deterministic replay executed in 1,780ms.</span>`;
      } else if (actIndex === 3) {
        if (cardSam) cardSam.classList.add("faulted-worker");
        if (cardAlex) cardAlex.classList.add("faulted-worker");
        elBriefcaseText.innerHTML = `<span style="font-family: var(--font-mono); color: #FDA4AF;">[CHAOS_INJECT] ToolCallFailureFault & SilentDegradationFault active on 2 edge transitions.</span>`;
      } else if (actIndex >= 4) {
        cards.forEach(c => c && c.classList.add("protected-worker"));
        if (cardElena) cardElena.classList.add("active-worker");
        elBriefcaseText.innerHTML = `<span style="font-family: var(--font-mono); color: #6EE7B7;">[INVARIANT_GUARD] Invariant STAT_EMERGENCY_DATA_INCONCLUSIVE caught -> routed to DLQ queue.</span>`;
      }
    }
  }

  // --- Dynamic Cockpit Views (Executive vs Technical) ---
  function renderCockpitView(actIndex) {
    if (viewMode === 'executive') {
      renderCockpitExecutive(actIndex);
    } else {
      renderCockpitTechnical(actIndex);
    }
  }

  // =========================================================================
  // EXECUTIVE COCKPIT VIEWS
  // =========================================================================
  function renderCockpitExecutive(actIndex) {
    if (actIndex === 0) {
      elCockpitTitle.innerHTML = `<span>🚨</span> Live Risk Alert: Case #LOAN-9042`;
      elCockpitPill.className = "cockpit-pill danger";
      elCockpitPill.textContent = "SILENT FAILURE IN PROGRESS";

      elCockpitDynamic.innerHTML = `
        <div class="crisis-alarm-card">
          <div class="crisis-alarm-header">
            <div class="crisis-alarm-title">
              <span>⚠️</span> UNCHECKED APPROVAL STAMPED
            </div>
            <div class="crisis-dollar-tag">$500,000 EXPOSURE</div>
          </div>
          <p class="crisis-alarm-desc">
            <strong>The Incident:</strong> Sam's credit bureau lookup had a 3-second network freeze and returned an empty file. Morgan immediately signed a <strong>$500,000 prime commercial loan</strong> because Jordan assumed empty debts meant zero liabilities.
          </p>
          <div style="background: rgba(0,0,0,0.4); border-radius: 6px; padding: 0.85rem; font-size: 0.82rem; color: #FDA4AF; display: flex; justify-content: space-between; align-items: center;">
            <span>Status: <strong>No crashes. No logs raised. No alarms.</strong></span>
            <button id="btn-cfo-investigate" style="background: var(--accent-rose); border: none; color: #000; font-weight: 800; font-size: 0.78rem; padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer;">
              Investigate with AgenticLens →
            </button>
          </div>
        </div>
      `;
      document.getElementById("btn-cfo-investigate")?.addEventListener("click", advanceAct);

    } else if (actIndex === 1) {
      elCockpitTitle.innerHTML = `<span>📹</span> AgenticLens · The Digital Flight Recorder`;
      elCockpitPill.className = "cockpit-pill inspect";
      elCockpitPill.textContent = "FULL AUDIT TRAIL CAPTURED";

      elCockpitDynamic.innerHTML = `
        <div style="background: rgba(14,22,38,0.85); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1.25rem;">
          <div style="font-size: 0.88rem; font-weight: 800; color: #fff; margin-bottom: 0.75rem; display: flex; justify-content: space-between;">
            <span>Executive Decision Receipt (Case #LOAN-9042)</span>
            <span style="color: var(--accent-cyan); font-family: var(--font-mono);">SHA-256 VERIFIED</span>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; font-size: 0.82rem; margin-bottom: 1rem;">
            <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: 6px;">
              <div style="color: var(--text-muted);">Applicant Requested:</div>
              <div style="font-weight: 800; color: #fff; font-size: 1rem;">$500,000 Credit Facility</div>
              <div style="color: #94A3B8; margin-top: 4px;">Time: 02:14:18 UTC</div>
            </div>
            <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: 6px;">
              <div style="color: var(--text-muted);">Root Cause Flagged:</div>
              <div style="font-weight: 800; color: var(--accent-rose); font-size: 1rem;">Sam (Credit Investigator)</div>
              <div style="color: #FDA4AF; margin-top: 4px;">4,210ms timeout fallback</div>
            </div>
          </div>
          <div style="font-size: 0.82rem; color: var(--text-secondary); line-height: 1.5;">
            AgenticLens automatically exported the complete execution telemetry into a standardized <strong>AI Ops Spec</strong>. Your engineering team can now replay this exact crisis anytime.
          </div>
        </div>
      `;

    } else if (actIndex === 2) {
      elCockpitTitle.innerHTML = `<span>⚡</span> Zero-Risk Simulation Sandbox`;
      elCockpitPill.className = "cockpit-pill inspect";
      elCockpitPill.textContent = "HERMETIC SANDBOX READY";

      elCockpitDynamic.innerHTML = `
        <div style="background: rgba(14,22,38,0.85); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <div style="font-size: 0.88rem; font-weight: 800; color: #fff;">
              Local Replay Simulation (100% Deterministic)
            </div>
            <button id="btn-replay-demo" style="background: rgba(6,182,212,0.2); border: 1px solid var(--accent-cyan); color: var(--accent-cyan); font-weight: 800; font-size: 0.78rem; padding: 0.4rem 0.85rem; border-radius: 4px; cursor: pointer;">
              ▶ Test Replay Now
            </button>
          </div>
          <p style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 1rem;">
            The simulated execution reproduces the failure in <strong>1.8 seconds</strong> without making external API calls or using expensive AI tokens.
          </p>
          <div style="background: rgba(0,0,0,0.4); border-radius: 4px; height: 10px; overflow: hidden; margin-bottom: 0.75rem;">
            <div id="sim-progress-bar" style="background: linear-gradient(90deg, var(--accent-cyan), var(--accent-emerald)); width: 100%; height: 100%; transition: width 1.2s ease;"></div>
          </div>
          <div id="sim-log-text" style="font-family: var(--font-mono); font-size: 0.75rem; color: #6EE7B7;">
            ✓ Replay complete: Root-cause confirmed at Sam → Jordan handoff. Zero dollar exposure.
          </div>
        </div>
      `;
      document.getElementById("btn-replay-demo")?.addEventListener("click", () => {
        const bar = document.getElementById("sim-progress-bar");
        const txt = document.getElementById("sim-log-text");
        if (bar && txt) {
          bar.style.width = "0%";
          txt.textContent = "Replaying simulated decision...";
          setTimeout(() => { bar.style.width = "50%"; }, 250);
          setTimeout(() => {
            bar.style.width = "100%";
            txt.textContent = "✓ Replay complete: Confirmed 100% reproduction fidelity in 1.78s.";
          }, 900);
        }
      });

    } else if (actIndex === 3) {
      elCockpitTitle.innerHTML = `<span>🌪️</span> Try Breaking It: The CFO Stress Simulator`;
      elCockpitPill.className = "cockpit-pill danger";
      elCockpitPill.textContent = "CHAOS ACTIVE";

      elCockpitDynamic.innerHTML = `
        <div style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 0.85rem;">
          Click any stress scenario below to see how your digital workers react under realistic business surprises:
        </div>
        <div class="chaos-board-grid">
          <div class="chaos-trigger-card ${activeFaults.bank_timeout ? 'active-fault' : ''}">
            <div class="chaos-trigger-top">
              <div>
                <div class="chaos-trigger-title">5-Second Bureau Outage</div>
                <div class="chaos-trigger-subtitle">External API Timeout</div>
              </div>
              <span style="font-size: 1.3rem;">💥</span>
            </div>
            <div class="chaos-trigger-explanation">Simulates credit bureau servers taking 5s to respond and returning blank data.</div>
            <button class="chaos-trigger-btn" id="btn-fault-bureau">${activeFaults.bank_timeout ? '✓ Outage Injected' : 'Trigger Outage'}</button>
          </div>

          <div class="chaos-trigger-card ${activeFaults.missing_income ? 'active-fault' : ''}">
            <div class="chaos-trigger-top">
              <div>
                <div class="chaos-trigger-title">Missing Tax Return</div>
                <div class="chaos-trigger-subtitle">Corrupted Document Intake</div>
              </div>
              <span style="font-size: 1.3rem;">✂️</span>
            </div>
            <div class="chaos-trigger-explanation">Drops stated revenue from the intake packet ($120k drops to null).</div>
            <button class="chaos-trigger-btn" id="btn-fault-tax">${activeFaults.missing_income ? '✓ Document Missing' : 'Drop Tax Return'}</button>
          </div>

          <div class="chaos-trigger-card ${activeFaults.corrupted_data ? 'active-fault' : ''}">
            <div class="chaos-trigger-top">
              <div>
                <div class="chaos-trigger-title">Inverted Handoff Data</div>
                <div class="chaos-trigger-subtitle">Data Transmission Glitch</div>
              </div>
              <span style="font-size: 1.3rem;">🔄</span>
            </div>
            <div class="chaos-trigger-explanation">Flips the 'has_bankruptcy' flag from TRUE to FALSE in transmission.</div>
            <button class="chaos-trigger-btn" id="btn-fault-data">${activeFaults.corrupted_data ? '✓ Glitch Active' : 'Corrupt Handoff'}</button>
          </div>

          <div class="chaos-trigger-card ${activeFaults.rate_throttle ? 'active-fault' : ''}">
            <div class="chaos-trigger-top">
              <div>
                <div class="chaos-trigger-title">Peak-Hour Throttling</div>
                <div class="chaos-trigger-subtitle">AI Provider Rate Limits</div>
              </div>
              <span style="font-size: 1.3rem;">⚡</span>
            </div>
            <div class="chaos-trigger-explanation">Simulates OpenAI or Anthropic throttling requests with HTTP 429 errors.</div>
            <button class="chaos-trigger-btn" id="btn-fault-throttle">${activeFaults.rate_throttle ? '✓ Throttling Active' : 'Throttle Traffic'}</button>
          </div>
        </div>
      `;

      document.getElementById("btn-fault-bureau")?.addEventListener("click", () => {
        activeFaults.bank_timeout = !activeFaults.bank_timeout;
        renderCockpitExecutive(3);
        updateConveyorWorkers(3);
      });
      document.getElementById("btn-fault-tax")?.addEventListener("click", () => {
        activeFaults.missing_income = !activeFaults.missing_income;
        renderCockpitExecutive(3);
        updateConveyorWorkers(3);
      });
      document.getElementById("btn-fault-data")?.addEventListener("click", () => {
        activeFaults.corrupted_data = !activeFaults.corrupted_data;
        renderCockpitExecutive(3);
        updateConveyorWorkers(3);
      });
      document.getElementById("btn-fault-throttle")?.addEventListener("click", () => {
        activeFaults.rate_throttle = !activeFaults.rate_throttle;
        renderCockpitExecutive(3);
        updateConveyorWorkers(3);
      });

    } else if (actIndex === 4) {
      elCockpitTitle.innerHTML = `<span>📊</span> Agentic-Evals: The CFO Audit Scorecard`;
      elCockpitPill.className = "cockpit-pill safe";
      elCockpitPill.textContent = "120 STRESS TESTS PASSED";

      elCockpitDynamic.innerHTML = `
        <div class="cfo-scorecard-grid">
          <div class="cfo-metric-box">
            <div class="cfo-metric-label">Silent Error Rate</div>
            <div class="cfo-metric-numbers">
              <span class="cfo-val-old">18.4%</span>
              <span style="color: var(--text-muted);">→</span>
              <span class="cfo-val-new">0.0%</span>
            </div>
            <div style="font-size: 0.72rem; color: var(--accent-emerald); margin-top: 4px;">Target: 0% unverified</div>
          </div>

          <div class="cfo-metric-box">
            <div class="cfo-metric-label">Safe Human Escalation</div>
            <div class="cfo-metric-numbers">
              <span class="cfo-val-old">24.0%</span>
              <span style="color: var(--text-muted);">→</span>
              <span class="cfo-val-new">100%</span>
            </div>
            <div style="font-size: 0.72rem; color: var(--accent-emerald); margin-top: 4px;">Never guess on money</div>
          </div>

          <div class="cfo-metric-box">
            <div class="cfo-metric-label">Audit Turnaround</div>
            <div class="cfo-metric-numbers">
              <span class="cfo-val-old">3 Days</span>
              <span style="color: var(--text-muted);">→</span>
              <span class="cfo-val-new">5 Mins</span>
            </div>
            <div style="font-size: 0.72rem; color: var(--accent-emerald); margin-top: 4px;">99% faster compliance</div>
          </div>
        </div>

        <div style="background: rgba(14,22,38,0.85); border: 1px solid var(--accent-emerald); border-radius: var(--radius-md); padding: 1.1rem;">
          <div style="font-size: 0.88rem; font-weight: 800; color: #fff; margin-bottom: 0.4rem; display: flex; align-items: center; gap: 0.5rem;">
            <span style="color: var(--accent-emerald);">🛡️</span> The Guardrail in Action:
          </div>
          <p style="font-size: 0.82rem; color: #CBD5E1; line-height: 1.5;">
            When Sam's credit check timed out under chaos testing, the hardened workflow refused to let Morgan guess. The application was seamlessly rerouted to <strong>Elena (Human Underwriting Manager)</strong> with full context. <strong>Zero bad loans slipped through.</strong>
          </p>
        </div>
      `;

    } else if (actIndex === 5) {
      elCockpitTitle.innerHTML = `<span>🛡️</span> The Automated CFO Release Gate`;
      elCockpitPill.className = "cockpit-pill safe";
      elCockpitPill.textContent = "PRODUCTION GREENLIT";

      elCockpitDynamic.innerHTML = `
        <div class="cfo-approval-seal-card">
          <div>
            <div class="seal-headline">
              <span style="color: var(--accent-emerald); font-size: 1.8rem;">✔</span>
              RELEASE APPROVED FOR DEPLOYMENT
            </div>
            <p class="seal-text">
              All 120 automated chaos experiments passed with 100% compliance. Cryptographically verified evidence pack generated. Safe to deploy to live production.
            </p>
            <div style="margin-top: 0.85rem; font-family: var(--font-mono); font-size: 0.72rem; color: var(--accent-cyan); background: rgba(0,0,0,0.4); padding: 0.4rem 0.8rem; border-radius: 4px; display: inline-block;">
              EVIDENCE HASH: sha256:7f9a2e618bc3d891b0c091f893e4d9426f04b2e811c76943b
            </div>
          </div>

          <div class="seal-badge-large">
            <div class="seal-percent">100%</div>
            <div class="seal-label">Compliant</div>
          </div>
        </div>
      `;
    }
  }

  // =========================================================================
  // TECHNICAL COCKPIT VIEWS (Full Code, Terminal, JSON & Spans)
  // =========================================================================
  function renderCockpitTechnical(actIndex) {
    if (actIndex === 0) {
      elCockpitTitle.innerHTML = `<span>🔍</span> OTLP Multi-Span Waterfall Trace (v1.0.4)`;
      elCockpitPill.className = "cockpit-pill danger";
      elCockpitPill.textContent = "LATENCY SPIKE: 4,210ms";

      elCockpitDynamic.innerHTML = `
        <div class="tech-waterfall-box">
          <div style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono); margin-bottom: 0.85rem;">
            Trace ID: <span style="color: #38BDF8;">trc_8842_prod_c10</span> · Parent Context: <span style="color: #A7F3D0;">root_span</span> · Sampler: AlwaysOn
          </div>
          <div class="tech-trace-item">
            <span class="tech-span-name">intake_agent</span>
            <div class="tech-span-track"><div class="tech-span-bar cyan" style="width: 20%;"></div></div>
            <span class="tech-span-time">780ms (1.5k tok)</span>
          </div>
          <div class="tech-trace-item">
            <span class="tech-span-name" style="color: #FDA4AF;">ehr_retriever [TOOL] ⚠️</span>
            <div class="tech-span-track"><div class="tech-span-bar red" style="width: 85%;"></div></div>
            <span class="tech-span-time" style="color: #FDA4AF;">4,210ms (Timeout)</span>
          </div>
          <div class="tech-trace-item">
            <span class="tech-span-name">policy_judge</span>
            <div class="tech-span-track"><div class="tech-span-bar cyan" style="width: 30%;"></div></div>
            <span class="tech-span-time">1,120ms (4.2k tok)</span>
          </div>
          <div class="tech-trace-item">
            <span class="tech-span-name">decision_agent</span>
            <div class="tech-span-track"><div class="tech-span-bar cyan" style="width: 18%;"></div></div>
            <span class="tech-span-time">640ms (1.1k tok)</span>
          </div>

          <div style="margin-top: 1rem; background: #050811; border: 1px solid rgba(244,63,94,0.3); border-radius: 6px; padding: 0.85rem; font-family: var(--font-mono); font-size: 0.72rem; line-height: 1.5; color: #FDA4AF;">
            <strong>[ANOMALY INTERCEPTED]</strong> tool.name="epic_fhir_retriever" duration_ms=4210 status_code=200 payload="{ stress_tests: [] }".<br>
            <strong>Root cause:</strong> Client fallback silently swallowed timeout exception and returned empty array, misinforming downstream policy invariants.
          </div>
        </div>
      `;

    } else if (actIndex === 1) {
      elCockpitTitle.innerHTML = `<span>📦</span> AI Ops Spec Schema Inspector (JSON)`;
      elCockpitPill.className = "cockpit-pill inspect";
      elCockpitPill.textContent = "AI-OPS-SPEC v1.0.0";

      const jsonStr = JSON.stringify(RAW_SPEC, null, 2);

      elCockpitDynamic.innerHTML = `
        <div class="tech-code-box">
          <div class="tech-code-bar">
            <span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--accent-cyan);">
              📄 spec_incident_9042.json (Canonical Contract)
            </span>
            <div style="display: flex; gap: 0.5rem;">
              <button id="btn-tech-copy" style="background: rgba(255,255,255,0.06); border: 1px solid var(--border-subtle); color: #fff; font-size: 0.7rem; padding: 0.25rem 0.6rem; border-radius: 4px; cursor: pointer;">Copy JSON</button>
              <button id="btn-tech-dl" style="background: rgba(255,255,255,0.06); border: 1px solid var(--border-subtle); color: #fff; font-size: 0.7rem; padding: 0.25rem 0.6rem; border-radius: 4px; cursor: pointer;">Download</button>
            </div>
          </div>
          <pre class="tech-code-pre" id="tech-pre"><code>${escapeHtml(jsonStr)}</code></pre>
        </div>
      `;

      document.getElementById("btn-tech-copy")?.addEventListener("click", () => {
        navigator.clipboard?.writeText(jsonStr);
        const b = document.getElementById("btn-tech-copy");
        if (b) { b.textContent = "Copied!"; setTimeout(() => b.textContent = "Copy JSON", 2000); }
      });
      document.getElementById("btn-tech-dl")?.addEventListener("click", () => {
        const blob = new Blob([jsonStr], { type: "application/json" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "spec_incident_9042.json";
        a.click();
      });

    } else if (actIndex === 2) {
      elCockpitTitle.innerHTML = `<span>⚡</span> Interactive Sandbox Terminal (CLI)`;
      elCockpitPill.className = "cockpit-pill inspect";
      elCockpitPill.textContent = "LOCAL CONTAINER SHELL";

      elCockpitDynamic.innerHTML = `
        <div class="terminal-window">
          <div class="terminal-header">
            <div class="terminal-dots">
              <span class="dot-red"></span>
              <span class="dot-yellow"></span>
              <span class="dot-green"></span>
            </div>
            <div class="terminal-title">agenticlens-cli v1.4.2 — dev-container@x86_64</div>
          </div>
          <div class="terminal-body" id="tech-term-body">
            <div><span class="cli-prompt">developer@workspace:~$</span> <span class="cli-cmd">agenticlens replay --spec spec_incident_9042.json --mock-boundaries</span></div>
            <div class="cli-info">[00:00.080] Loading AI Ops Spec contract: spec_prod_pa_9042_c10</div>
            <div class="cli-info">[00:00.140] Initializing mock SQLite storage & synthetic PII scrubber...</div>
            <div class="cli-info">[00:00.410] [SPAN 1/4] intake_agent executed in 780ms (prompt=1,240, compl=320)</div>
            <div class="cli-warn">[00:01.210] [SPAN 2/4] ehr_retriever boundary mocked (simulated_latency=4210ms, empty_payload=[])</div>
            <div class="cli-warn">[00:01.440] [SPAN 3/4] policy_judge invariant evaluation triggered...</div>
            <div class="cli-error">[00:01.780] [INVARIANT_BREACH] PolicyJudge assumed zero ischemic history without verification!</div>
            <div class="cli-info">[00:01.810] Decision: DENIED (Reproduced in 1.78s · Zero Live Tokens Consumed)</div>
            <div style="margin-top: 0.85rem;"><span class="cli-prompt">developer@workspace:~$</span> <span style="animation: pulseGold 1s infinite;">█</span></div>
          </div>
        </div>
      `;

    } else if (actIndex === 3) {
      elCockpitTitle.innerHTML = `<span>🌪️</span> Agentic-Chaos Python Test Suite`;
      elCockpitPill.className = "cockpit-pill danger";
      elCockpitPill.textContent = "CHAOS INJECTION SPEC";

      elCockpitDynamic.innerHTML = `
        <div class="tech-code-box">
          <div class="tech-code-bar">
            <span style="font-family: var(--font-mono); font-size: 0.75rem; color: #FDA4AF;">
              🐍 test_cardiology_chaos.py (Chaos Session Decorators)
            </span>
            <span style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono);">agentic-chaos==0.8.4</span>
          </div>
          <pre class="tech-code-pre"><code><span style="color: #F43F5E;">@chaos_session</span>(suite=<span style="color: #A5F3FC;">"cardiology_stress_matrix"</span>, intensity=0.85)
<span style="color: #38BDF8;">def</span> <span style="color: #FBBF24;">test_pipeline_under_bureau_failure</span>():
    <span style="color: #64748B;"># Injects simulated 4.5s latency and empty array fallback</span>
    wrap_tool(
        target=<span style="color: #A5F3FC;">"ehr_retriever.epic_fhir_retriever"</span>,
        fault=ToolCallFailureFault(mode=<span style="color: #A5F3FC;">"timeout_empty"</span>, delay_ms=4500)
    )

    <span style="color: #64748B;"># Injects silent troponin biomarker dropping from intake</span>
    wrap_agent(
        target=<span style="color: #A5F3FC;">"intake_agent"</span>,
        fault=SilentDegradationFault(drop_keys=[<span style="color: #A5F3FC;">"troponin"</span>])
    )

    <span style="color: #64748B;"># Execute workflow & assert invariant adherence</span>
    result = run_pipeline(fixture=<span style="color: #A5F3FC;">"case_pa_9042.json"</span>)
    <span style="color: #38BDF8;">assert</span> result.status != <span style="color: #A5F3FC;">"UNSUPPORTED_DENIAL"</span>, <span style="color: #FDA4AF;">"Silent failure detected!"</span></code></pre>
        </div>
      `;

    } else if (actIndex === 4) {
      elCockpitTitle.innerHTML = `<span>📊</span> Agentic-Evals Deterministic Oracle Benchmark`;
      elCockpitPill.className = "cockpit-pill safe";
      elCockpitPill.textContent = "120 CASES BENCHMARKED";

      elCockpitDynamic.innerHTML = `
        <div style="background: rgba(14,22,38,0.85); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1.25rem;">
          <div style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono); margin-bottom: 0.75rem;">
            EVALUATION SUITE: <span style="color: #6EE7B7;">cardiology_invariant_suite_v2</span> (120 Synthetic Patient Trajectories)
          </div>

          <table style="width: 100%; border-collapse: collapse; font-size: 0.78rem; font-family: var(--font-mono); text-align: left;">
            <thead>
              <tr style="border-bottom: 1px solid var(--border-subtle); color: var(--text-muted);">
                <th style="padding: 0.4rem 0;">METRIC</th>
                <th style="padding: 0.4rem 0;">v1 (NAIVE)</th>
                <th style="padding: 0.4rem 0;">v2 (HARDENED)</th>
                <th style="padding: 0.4rem 0;">GATE SPEC</th>
                <th style="padding: 0.4rem 0;">STATUS</th>
              </tr>
            </thead>
            <tbody>
              <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td style="padding: 0.5rem 0; color: #fff;">Invariant Adherence</td>
                <td style="color: #FDA4AF;">71.2%</td>
                <td style="color: #6EE7B7; font-weight: 700;">100.0%</td>
                <td>&gt;= 98.0%</td>
                <td style="color: #6EE7B7;">PASS</td>
              </tr>
              <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td style="padding: 0.5rem 0; color: #fff;">Silent Failure Rate</td>
                <td style="color: #FDA4AF;">18.4%</td>
                <td style="color: #6EE7B7; font-weight: 700;">0.0%</td>
                <td>&lt;= 1.0%</td>
                <td style="color: #6EE7B7;">PASS</td>
              </tr>
              <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td style="padding: 0.5rem 0; color: #fff;">Safe Degradation to DLQ</td>
                <td style="color: #FDA4AF;">24.0%</td>
                <td style="color: #6EE7B7; font-weight: 700;">100.0%</td>
                <td>&gt;= 95.0%</td>
                <td style="color: #6EE7B7;">PASS</td>
              </tr>
              <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td style="padding: 0.5rem 0; color: #fff;">P99 Latency (Tail)</td>
                <td style="color: #FBBF24;">9.4s</td>
                <td style="color: #6EE7B7; font-weight: 700;">3.8s</td>
                <td>&lt;= 5.0s</td>
                <td style="color: #6EE7B7;">PASS</td>
              </tr>
              <tr>
                <td style="padding: 0.5rem 0; color: #fff;">Cost per Case (USD)</td>
                <td>$0.048</td>
                <td style="color: #6EE7B7; font-weight: 700;">$0.027 (-43.7%)</td>
                <td>&lt;= $0.035</td>
                <td style="color: #6EE7B7;">PASS</td>
              </tr>
            </tbody>
          </table>
        </div>
      `;

    } else if (actIndex === 5) {
      elCockpitTitle.innerHTML = `<span>🛡️</span> Cryptographic Evidence Pack & CI/CD Pipeline`;
      elCockpitPill.className = "cockpit-pill safe";
      elCockpitPill.textContent = "GATE VERIFIED: PASS";

      elCockpitDynamic.innerHTML = `
        <div class="tech-code-box">
          <div class="tech-code-bar">
            <span style="font-family: var(--font-mono); font-size: 0.75rem; color: #6EE7B7;">
              ⚙️ .github/workflows/agentic_release_gate.yml (Continuous Deployment)
            </span>
            <span style="font-size: 0.7rem; color: var(--accent-cyan); font-family: var(--font-mono);">Run #412 · Merged</span>
          </div>
          <pre class="tech-code-pre"><code><span style="color: #38BDF8;">name</span>: AgenticLens Automated Release Gate
<span style="color: #38BDF8;">on</span>:
  <span style="color: #38BDF8;">pull_request</span>:
    <span style="color: #38BDF8;">branches</span>: [ main ]

<span style="color: #38BDF8;">jobs</span>:
  <span style="color: #FBBF24;">verify_agent_invariants</span>:
    <span style="color: #38BDF8;">runs-on</span>: ubuntu-latest
    <span style="color: #38BDF8;">steps</span>:
      - <span style="color: #38BDF8;">name</span>: Run Chaos &amp; Invariant Suites
        <span style="color: #38BDF8;">run</span>: |
          uv run agentic-chaos run --matrix full_cardiology_suite.yaml
          uv run agentic-evals evaluate --workflow v2 --export-evidence evidence.json
      - <span style="color: #38BDF8;">name</span>: Enforce Gate Check
        <span style="color: #38BDF8;">run</span>: |
          uv run agenticlens gate enforce --evidence evidence.json --threshold 98.0
          <span style="color: #64748B;"># SHA-256 Merkle Evidence Hash: 7f9a2e618bc3d891b0c091f893e4d9426f04b2e8</span></code></pre>
        </div>
      `;
    }
  }

  // Helper escape
  function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // --- Step Navigation Handlers ---
  function advanceAct() {
    if (currentActIndex < 5) {
      renderAct(currentActIndex + 1);
    } else {
      window.location.href = "technical.html";
    }
  }

  function prevAct() {
    if (currentActIndex > 0) {
      renderAct(currentActIndex - 1);
    }
  }

  function toggleTour() {
    isTourActive = !isTourActive;
    if (isTourActive) {
      elTourBtn.classList.add("touring");
      elTourBtn.innerHTML = `<span>⏸</span> Pause Tour`;
      tourInterval = setInterval(() => advanceAct(), 10000);
    } else {
      elTourBtn.classList.remove("touring");
      elTourBtn.innerHTML = `<span>▶</span> Auto Tour`;
      clearInterval(tourInterval);
      tourInterval = null;
    }
  }

  // --- Worker / Node Click Inspector ---
  function initWorkerClicks() {
    const cardAlex = document.getElementById("card-worker-alex");
    const cardSam = document.getElementById("card-worker-sam");
    const cardJordan = document.getElementById("card-worker-jordan");
    const cardMorgan = document.getElementById("card-worker-morgan");
    const cardElena = document.getElementById("card-worker-elena");

    const mapping = [
      {
        el: cardAlex,
        exec: { title: "Alex (Document Reader)", role: "Intake Specialist", desc: "Extracts customer income, ID, and tax filings from incoming paperwork.", risk: "If tax forms are blurry, naive Alex drops the number and says nothing." },
        tech: { title: "intake_agent", role: "Model: claude-3-5-sonnet", desc: "Extracts clinical urgency, CPT code 92928, and troponin biomarkers into JSON payload.", risk: "Unvalidated Pydantic extraction allows missing fields to propagate downstream as null." }
      },
      {
        el: cardSam,
        exec: { title: "Sam (Credit Investigator)", role: "Database Inquirer", desc: "Queries external credit bureaus and bank account databases in real time.", risk: "When credit bureau APIs freeze for 3 seconds, naive Sam passes a blank folder." },
        tech: { title: "ehr_retriever", role: "Tool: epic_fhir_v4 (REST)", desc: "Queries FHIR DiagnosticReport for prior stress tests and nuclear SPECT scans.", risk: "Client fallback returns empty array [] on HTTP 4.2s timeout without throwing an exception." }
      },
      {
        el: cardJordan,
        exec: { title: "Jordan (Risk Calculator)", role: "Financial Analyst", desc: "Computes debt-to-income ratio and policy eligibility rules.", risk: "Treats Sam's blank folder as 'zero debts' instead of 'data missing'." },
        tech: { title: "policy_judge", role: "Model: gpt-4o (temp=0.0)", desc: "Adjudicates clinical necessity against ACC/AHA Revascularization Guidelines.", risk: "Prompt assumes absence of ischemic records equals absence of documented disease." }
      },
      {
        el: cardMorgan,
        exec: { title: "Morgan (Check Signer)", role: "Final Decisioner", desc: "Automatically stamps loan approval or denial letters.", risk: "Cuts a $500,000 check based on unverified, incomplete calculations." },
        tech: { title: "decision_agent", role: "Model: gpt-4o-mini", desc: "Formats adverse notice determination letter and logs determination verdict.", risk: "Final adverse letter generated with 0 human audit reviews." }
      },
      {
        el: cardElena,
        exec: { title: "Elena (Human Supervisor)", role: "Human-in-the-Loop", desc: "Senior Underwriting Manager who reviews escalated edge cases.", risk: "In naive v1, Elena was bypassed. In hardened v2, all anomalies route to her!" },
        tech: { title: "hitl_dlq", role: "Queue: SQS Dead-Letter Review", desc: "Asynchronous human-in-the-loop escalation topic with full telemetry context.", risk: "Essential safety net ensuring zero unverified decisions ever reach production." }
      }
    ];

    mapping.forEach(item => {
      if (item.el) {
        item.el.addEventListener("click", () => {
          const data = (viewMode === 'executive') ? item.exec : item.tech;
          showInspectionModal(data);
        });
      }
    });
  }

  function showInspectionModal(data) {
    let modal = document.getElementById("worker-cfo-modal");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "worker-cfo-modal";
      modal.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0, 0, 0, 0.75); backdrop-filter: blur(8px);
        display: flex; align-items: center; justify-content: center;
        z-index: 1000; animation: fadeIn 0.25s ease;
      `;
      document.body.appendChild(modal);
    }

    modal.innerHTML = `
      <div style="background: #0E1626; border: 1px solid var(--accent-cyan); border-radius: 16px; padding: 2rem; max-width: 520px; width: 90%; box-shadow: 0 25px 60px rgba(0,0,0,0.8); position: relative;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.25rem;">
          <div>
            <h3 style="font-size: 1.25rem; font-weight: 800; color: #fff;">${data.title}</h3>
            <span style="font-size: 0.78rem; color: var(--accent-cyan); font-weight: 700; font-family: var(--font-mono);">${data.role}</span>
          </div>
          <button id="btn-close-worker-modal" style="background: none; border: none; color: var(--text-muted); font-size: 1.4rem; cursor: pointer;">✕</button>
        </div>

        <div style="margin-bottom: 1.25rem;">
          <div style="font-size: 0.78rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.35rem;">
            ${viewMode === 'executive' ? 'Business Responsibility:' : 'Component Architecture:'}
          </div>
          <p style="font-size: 0.92rem; color: #E2E8F0; line-height: 1.5;">${data.desc}</p>
        </div>

        <div style="background: rgba(244,63,94,0.12); border: 1px solid rgba(244,63,94,0.3); border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem;">
          <div style="font-size: 0.78rem; font-weight: 800; color: #FDA4AF; text-transform: uppercase; margin-bottom: 0.35rem;">
            ${viewMode === 'executive' ? 'The Hidden Risk Without DeepAgentLabs:' : 'Failure Vulnerability:'}
          </div>
          <p style="font-size: 0.88rem; color: #FECDD3; line-height: 1.5;">${data.risk}</p>
        </div>

        <button id="btn-modal-understand" style="width: 100%; background: linear-gradient(135deg, var(--accent-cyan), #0284C7); border: none; color: #000; font-weight: 800; padding: 0.75rem; border-radius: 8px; cursor: pointer;">
          Close Inspector
        </button>
      </div>
    `;

    document.getElementById("btn-close-worker-modal")?.addEventListener("click", () => modal.remove());
    document.getElementById("btn-modal-understand")?.addEventListener("click", () => modal.remove());
    modal.addEventListener("click", (e) => { if (e.target === modal) modal.remove(); });
  }

  // --- Executive ROI Calculator Logic ---
  function initRoiCalculator() {
    const elSliderDecisions = document.getElementById("slider-decisions");
    const elLabelDecisions = document.getElementById("label-decisions-count");
    const elStatErrorsSaved = document.getElementById("stat-errors-saved");
    const elStatDollarsSaved = document.getElementById("stat-dollars-saved");
    if (!elSliderDecisions) return;

    function updateCalculator() {
      const monthlyCount = parseInt(elSliderDecisions.value, 10);
      elLabelDecisions.textContent = monthlyCount.toLocaleString();

      const annualDecisions = monthlyCount * 12;
      const annualErrorsPrevented = Math.round(annualDecisions * 0.184 * 0.05);
      const capitalProtected = (annualErrorsPrevented * 45000);

      elStatErrorsSaved.textContent = annualErrorsPrevented.toLocaleString();
      elStatDollarsSaved.textContent = `$${(capitalProtected / 1000000).toFixed(1)}M`;
    }

    elSliderDecisions.addEventListener("input", updateCalculator);
    updateCalculator();
  }

  // --- Audience Mode Switcher (Seamless In-Place Transformation) ---
  function initModeSwitch() {
    if (!elBtnModeExec || !elBtnModeTech) return;

    elBtnModeExec.addEventListener("click", () => {
      if (viewMode === 'executive') return;
      viewMode = 'executive';
      elBtnModeExec.classList.add("active");
      elBtnModeTech.classList.remove("active");

      // Transform Hero Content
      if (elHeroTagline) elHeroTagline.textContent = "THE 30-SECOND EXECUTIVE EXPLAINER";
      if (elHeroTitle) elHeroTitle.textContent = "The $500,000 Silent Mistake";
      if (elHeroDesc) elHeroDesc.innerHTML = "How autonomous AI teams pass bad work without anyone noticing—and how the <strong>DeepAgentLabs ecosystem</strong> safeguards your enterprise balance sheet from invisible automated errors.";
      if (elAnalogyBox) {
        elAnalogyBox.innerHTML = `
          <div class="analogy-title"><span>💡</span> The Relay Race Analogy in Plain English:</div>
          <p class="analogy-text">
            Think of an AI system like a relay team of digital assistants: <strong>Alex</strong> reads the paperwork, <strong>Sam</strong> checks credit, <strong>Jordan</strong> calculates debt, and <strong>Morgan</strong> signs the loan. But if Sam's database freezes for 3 seconds, Sam hands a blank folder to Jordan! Jordan thinks <em>"No debts found!"</em>, and Morgan cuts a <strong>$500,000 check</strong> to a bankrupt company. <strong>No computer crashed. Zero alerts went off. Your company just lost half a million dollars silently.</strong>
          </p>
        `;
      }

      // Update Ticker Labels
      if (elTickerLabelExposure) elTickerLabelExposure.textContent = "Potential Exposure:";
      if (elTickerLabelErrors) elTickerLabelErrors.textContent = "Silent System Errors:";
      if (elTickerLabelStatus) elTickerLabelStatus.textContent = "Operational State:";

      // Update Stage Header
      if (elConveyorStageHeader) {
        elConveyorStageHeader.innerHTML = `<span>Digital Worker Assembly Line</span><span>Click any worker to see their role</span>`;
      }

      // Rerender Act
      renderAct(currentActIndex);
    });

    elBtnModeTech.addEventListener("click", () => {
      if (viewMode === 'technical') return;
      viewMode = 'technical';
      elBtnModeTech.classList.add("active");
      elBtnModeExec.classList.remove("active");

      // Transform Hero Content
      if (elHeroTagline) elHeroTagline.textContent = "AI OPS SPECIFICATION & MULTI-AGENT OBSERVABILITY";
      if (elHeroTitle) elHeroTitle.textContent = "Deterministic AgenticOps Lifecycle Engine";
      if (elHeroDesc) elHeroDesc.innerHTML = "Hermetically capture production multi-agent trajectories, serialize universal <strong>AI Ops Spec</strong> schemas, inject multi-vector chaos faults, and enforce cryptographic CI/CD release gates.";
      if (elAnalogyBox) {
        elAnalogyBox.innerHTML = `
          <div class="analogy-title" style="color: var(--accent-cyan);"><span>⚙️</span> Distributed Agentic Topology Architecture:</div>
          <p class="analogy-text" style="font-family: var(--font-mono); font-size: 0.82rem; color: #CBD5E1;">
            DAG Topology: [intake_agent (claude-3-5)] ──► [ehr_retriever (tool: epic_fhir)] ──► [policy_judge (gpt-4o)] ──► [decision_agent (gpt-4o-mini)].<br>
            Root Cause: Invariant contract breach at tool boundary returned unhandled empty payload [] under 4,210ms latency.
          </p>
        `;
      }

      // Update Ticker Labels
      if (elTickerLabelExposure) elTickerLabelExposure.textContent = "Token Telemetry:";
      if (elTickerLabelErrors) elTickerLabelErrors.textContent = "Trace Diagnostic:";
      if (elTickerLabelStatus) elTickerLabelStatus.textContent = "Boundary Contract:";

      // Update Stage Header
      if (elConveyorStageHeader) {
        elConveyorStageHeader.innerHTML = `<span style="font-family: var(--font-mono); color: var(--accent-cyan);">Multi-Agent DAG Topology Spans</span><span>Click any node to inspect payload</span>`;
      }

      // Rerender Act
      renderAct(currentActIndex);
    });
  }

  // --- Day / Night Theme Controller ---
  function initThemeToggle() {
    const elBtnTheme = document.getElementById("btn-theme-toggle");
    const elThemeIcon = document.getElementById("theme-icon");
    const elThemeText = document.getElementById("theme-text");
    if (!elBtnTheme) return;

    // Check saved theme
    const savedTheme = localStorage.getItem("deepagentlabs_theme") || "dark";
    if (savedTheme === "light") {
      document.documentElement.setAttribute("data-theme", "light");
      if (elThemeIcon) elThemeIcon.textContent = "🌙";
      if (elThemeText) elThemeText.textContent = "Night Mode";
    }

    elBtnTheme.addEventListener("click", () => {
      const currentTheme = document.documentElement.getAttribute("data-theme");
      if (currentTheme === "light") {
        document.documentElement.removeAttribute("data-theme");
        localStorage.setItem("deepagentlabs_theme", "dark");
        if (elThemeIcon) elThemeIcon.textContent = "☀️";
        if (elThemeText) elThemeText.textContent = "Day Mode";
      } else {
        document.documentElement.setAttribute("data-theme", "light");
        localStorage.setItem("deepagentlabs_theme", "light");
        if (elThemeIcon) elThemeIcon.textContent = "🌙";
        if (elThemeText) elThemeText.textContent = "Night Mode";
      }
    });
  }

  // --- Global Event Bindings ---
  elBtnAdvance.addEventListener("click", advanceAct);
  elBtnPrev.addEventListener("click", prevAct);
  elTourBtn.addEventListener("click", toggleTour);

  elStepCards.forEach((c, idx) => {
    c.addEventListener("click", () => renderAct(idx));
  });

  window.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") advanceAct();
    if (e.key === "ArrowLeft") prevAct();
  });

  // --- Initialize ---
  initWorkerClicks();
  initRoiCalculator();
  initModeSwitch();
  initThemeToggle();
  renderAct(0);

})();

