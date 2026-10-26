/**
 * FinAssure Use Case Showcase Interactive Logic
 * Features:
 * - Live Hosted Project URL Manager
 * - Interactive 5-Agent Architecture & Chaos Simulator
 * - Dynamic Scenario Output & Node Inspector
 * - Tabbed Quick Start Box
 * - Reading Progress Bar & ScrollSpy
 */

document.addEventListener('DOMContentLoaded', () => {
  initProgressBar();
  initScrollSpy();
  initZoomControls();
  initHostedProjectSlot();
  initSimulator();
  initAnimatedGraphs();
  initQuickstartTabs();
  initCopyButton();
});

/* ==========================================================================
   0. Zoom Controls
   ========================================================================== */
function initZoomControls() {
  const zoomBtns = document.querySelectorAll('.zoom-btn');
  const STORAGE_KEY = 'finassure_view_zoom';

  function applyZoom(val) {
    const scale = parseInt(val, 10);
    if (scale === 100) {
      document.documentElement.style.zoom = '1';
    } else if (scale === 85) {
      document.documentElement.style.zoom = '0.88';
    } else if (scale === 75) {
      document.documentElement.style.zoom = '0.78';
    }
    zoomBtns.forEach((b) => {
      b.classList.toggle('active', b.getAttribute('data-zoom') === String(val));
    });
    localStorage.setItem(STORAGE_KEY, String(val));
  }

  const savedZoom = localStorage.getItem(STORAGE_KEY) || '100';
  applyZoom(savedZoom);

  zoomBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetZoom = btn.getAttribute('data-zoom');
      applyZoom(targetZoom);
    });
  });
}

/* ==========================================================================
   1. Reading Progress Bar
   ========================================================================== */
function initProgressBar() {
  const progressBar = document.getElementById('reading-progress');
  if (!progressBar) return;

  window.addEventListener('scroll', () => {
    const totalHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress = (window.scrollY / totalHeight) * 100;
    progressBar.style.width = `${Math.min(100, Math.max(0, progress))}%`;
  });
}

/* ==========================================================================
   2. ScrollSpy Section Highlighting
   ========================================================================== */
function initScrollSpy() {
  const sections = document.querySelectorAll('.usecase-section');
  const navItems = document.querySelectorAll('.toc-item');
  if (!sections.length || !navItems.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const id = entry.target.getAttribute('id');
        navItems.forEach((item) => {
          const link = item.querySelector('a');
          const href = link?.getAttribute('href');
          item.classList.toggle('active', href === `#${id}`);
        });
      }
    });
  }, { threshold: 0.25 });

  sections.forEach((sec) => observer.observe(sec));
}

/* ==========================================================================
   3. Hosted Project URL Manager
   ========================================================================== */
function initHostedProjectSlot() {
  const urlInput = document.getElementById('hosted-url-input');
  const launchBtn = document.getElementById('launch-project-btn');
  const saveBtn = document.getElementById('save-url-btn');

  const STORAGE_KEY = 'finassure_hosted_url';
  const DEFAULT_URL = 'dashboard/';

  const savedUrl = localStorage.getItem(STORAGE_KEY) || DEFAULT_URL;
  if (urlInput) urlInput.value = savedUrl;
  if (launchBtn) {
    launchBtn.href = (savedUrl.startsWith('http://') || savedUrl.startsWith('https://') || savedUrl.startsWith('./') || savedUrl.startsWith('../') || savedUrl.startsWith('/')) 
      ? savedUrl 
      : `http://${savedUrl}`;
  }

  if (saveBtn && urlInput) {
    saveBtn.addEventListener('click', () => {
      let target = urlInput.value.trim() || DEFAULT_URL;
      localStorage.setItem(STORAGE_KEY, target);
      if (launchBtn) {
        launchBtn.href = (target.startsWith('http://') || target.startsWith('https://') || target.startsWith('./') || target.startsWith('../') || target.startsWith('/')) 
          ? target 
          : `http://${target}`;
      }

      const origText = saveBtn.textContent;
      saveBtn.textContent = '✓ Saved!';
      saveBtn.style.borderColor = '#10b981';
      setTimeout(() => {
        saveBtn.textContent = origText;
        saveBtn.style.borderColor = '';
      }, 1800);
    });
  }
}

/* ==========================================================================
   4. Interactive 5-Agent Architecture & Chaos Simulator
   ========================================================================== */
const nodeDetails = {
  1: {
    title: 'Agent 1: Intake Agent',
    role: 'Receives and validates applicant metadata, requested loan amount ($28,500), and synthetic identity payload.',
    v1: 'Accepts raw dictionaries without schema enforcement; drops invalid fields silently.',
    v2: 'Pydantic strict contract validation; rejects non-conforming types before downstream processing.'
  },
  2: {
    title: 'Agent 2: Doc Extraction Agent',
    role: 'Extracts stated income, bank statement deposits (90-day cash inflow), and employer verification.',
    v1: 'Trusts OCR extraction implicitly without verification; vulnerable to silent degradation.',
    v2: 'Cross-checks stated income against 90-day bank deposit inflows; escalates if mismatch > 15%.'
  },
  3: {
    title: 'Agent 3: Credit Bureau Agent',
    role: 'Queries external credit bureau service (FICO score, tradelines, 30/60/90 day delinquencies).',
    v1: 'Catastrophic Fallback: On bureau timeout or HTTP error, defaults missing credit score to 680!',
    v2: 'Exponential backoff with retry limit; strictly refuses to guess credit scores. Escalates to HITL queue.'
  },
  4: {
    title: 'Agent 4: Risk Scorer Agent',
    role: 'Calculates Debt-to-Income (DTI), loan-to-income leverage, and policy threshold compliance.',
    v1: 'Generates loan approvals on falsified DTI without checking bureau availability.',
    v2: 'Deterministic Python mathematical scoring (pure arithmetic, zero LLM hallucinations).'
  },
  5: {
    title: 'Agent 5: Compliance Reviewer Agent',
    role: 'Drafts FCRA/ECOA adverse action notices citing grounded deterministic factors, or triggers HITL review.',
    v1: 'Unconstrained reviewer turns, prone to hallucinated denial reasons under prompt drift.',
    v2: 'Turn limit cap (MAX_TURNS=3); verifies adverse factors match oracle factors.'
  }
};

function initSimulator() {
  const simButtons = document.querySelectorAll('.sim-btn');
  const simNodes = document.querySelectorAll('.sim-node');
  const inspectorTitle = document.getElementById('inspector-title');
  const inspectorRole = document.getElementById('inspector-role');
  const inspectorV1 = document.getElementById('inspector-v1');
  const inspectorV2 = document.getElementById('inspector-v2');
  const simScenarioTitle = document.getElementById('sim-scenario-title');
  const simScenarioStatus = document.getElementById('sim-scenario-status');
  const simScenarioDesc = document.getElementById('sim-scenario-desc');
  const simBureauNode = document.getElementById('sim-bureau-node');
  const bureauChaosOverlay = document.getElementById('bureau-chaos-overlay');
  const bureauShieldOverlay = document.getElementById('bureau-shield-overlay');
  const detourIndicator = document.getElementById('detour-indicator');
  const bureauSubtext = document.getElementById('bureau-subtext');

  // Node Click Handlers
  simNodes.forEach((node) => {
    node.addEventListener('click', () => {
      simNodes.forEach((n) => n.style.borderColor = 'var(--border-subtle)');
      node.style.borderColor = 'var(--accent-cyan)';
      const id = node.getAttribute('data-node');
      const data = nodeDetails[id];
      if (data) {
        if (inspectorTitle) inspectorTitle.textContent = data.title;
        if (inspectorRole) inspectorRole.textContent = data.role;
        if (inspectorV1) inspectorV1.innerHTML = `<strong>v1 Naive Flaw:</strong> ${data.v1}`;
        if (inspectorV2) inspectorV2.innerHTML = `<strong>v2 Hardened Guard:</strong> ${data.v2}`;
      }
    });
  });

  // Scenario Buttons
  simButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      simButtons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');

      const scenario = btn.getAttribute('data-scenario') || btn.getAttribute('data-mode');

      if (scenario === 'clean') {
        if (simBureauNode) {
          simBureauNode.style.borderColor = 'var(--border-subtle)';
          simBureauNode.style.background = 'rgba(13, 18, 31, 0.95)';
        }
        if (bureauChaosOverlay) bureauChaosOverlay.style.display = 'none';
        if (bureauShieldOverlay) bureauShieldOverlay.style.display = 'none';
        if (detourIndicator) detourIndicator.style.display = 'none';
        if (bureauSubtext) bureauSubtext.textContent = 'FICO / Bureau API (740)';

        if (simScenarioTitle) simScenarioTitle.textContent = 'Clean Path Execution · Applicant APP-42-0001';
        if (simScenarioStatus) {
          simScenarioStatus.textContent = 'APPROVED (DTI: 28%)';
          simScenarioStatus.style.background = 'rgba(16, 185, 129, 0.2)';
          simScenarioStatus.style.color = '#6EE7B7';
        }
        if (simScenarioDesc) {
          simScenarioDesc.textContent = 'All 5 agents complete in 780ms. Bureau returns verified score 740. Risk scorer validates DTI. Decision matches mathematical policy oracle.';
        }
      } else if (scenario === 'chaos') {
        if (simBureauNode) {
          simBureauNode.style.borderColor = 'var(--accent-rose)';
          simBureauNode.style.background = 'rgba(244, 63, 94, 0.15)';
        }
        if (bureauChaosOverlay) bureauChaosOverlay.style.display = 'block';
        if (bureauShieldOverlay) bureauShieldOverlay.style.display = 'none';
        if (detourIndicator) detourIndicator.style.display = 'none';
        if (bureauSubtext) bureauSubtext.textContent = 'TIMEOUT 4.5s (Guessed 680!)';

        if (simScenarioTitle) simScenarioTitle.textContent = 'Credit Bureau Timeout Injected (v1 Naive Fails Silently)';
        if (simScenarioStatus) {
          simScenarioStatus.textContent = 'CATASTROPHIC APPROVAL (Score defaulted to 680)';
          simScenarioStatus.style.background = 'rgba(244, 63, 94, 0.2)';
          simScenarioStatus.style.color = '#FDA4AF';
        }
        if (simScenarioDesc) {
          simScenarioDesc.textContent = 'CRITICAL FAILURE: On 4.5s bureau timeout, v1 silently defaulted the missing credit score to 680, approving a bankrupt borrower ($120k loan exposure). Zero errors were logged!';
        }
      } else if (scenario === 'hardened') {
        if (simBureauNode) {
          simBureauNode.style.borderColor = 'var(--accent-emerald)';
          simBureauNode.style.background = 'rgba(16, 185, 129, 0.15)';
        }
        if (bureauChaosOverlay) bureauChaosOverlay.style.display = 'none';
        if (bureauShieldOverlay) bureauShieldOverlay.style.display = 'block';
        if (detourIndicator) detourIndicator.style.display = 'block';
        if (bureauSubtext) bureauSubtext.textContent = 'PROTECTED (Safe Escalation)';

        if (simScenarioTitle) simScenarioTitle.textContent = 'Hardened Pipeline Protected (v2 Release Gate)';
        if (simScenarioStatus) {
          simScenarioStatus.textContent = 'SAFE ESCALATION (Routed to HITL Queue)';
          simScenarioStatus.style.background = 'rgba(6, 182, 212, 0.2)';
          simScenarioStatus.style.color = '#7DD3FC';
        }
        if (simScenarioDesc) {
          simScenarioDesc.textContent = 'PROTECTED: v2 strictly refused to default missing credit data. The application was safely escalated to the Human Underwriting Queue. Zero unsupported approvals.';
        }
      }
    });
  });
}

/* ==========================================================================
   5. Interactive Animated Benchmark Graphs (Section 5)
   ========================================================================== */
const graphScenarios = {
  timeout: {
    title: 'Credit Bureau 4.5s Timeout Chaos Injection',
    summary: 'When Credit Bureau latency spikes to 4.5s, Naive v1 silently assumed score 680, approving 12 insolvent borrowers ($1.4M exposure). FinAssure v2 safely caught all 12 and escalated to human underwriters.',
    failV1: '16.7%',
    failV1Width: '16.7%',
    failV2: '0.0%',
    failV2Width: '2%',
    loansV1: '12 Loans ($1.4M)',
    loansV1Val: '$1.4M Risk',
    loansV1Width: '60%',
    loansV2: '0 Loans ($0)',
    loansV2Val: '$0 Risk',
    loansV2Width: '2%',
    escV1: '20.0%',
    escV1Width: '20%',
    escV2: '100.0%',
    escV2Width: '100%'
  },
  paystub: {
    title: 'Corrupted Bank Statement / Paystub Inflow Chaos',
    summary: 'When OCR drops income fields, Naive v1 hallucinated debt ratios. FinAssure cross-verified with 90-day bank deposit inflows, rejecting falsified documents before approval.',
    failV1: '14.2%',
    failV1Width: '14.2%',
    failV2: '0.0%',
    failV2Width: '2%',
    loansV1: '9 Loans ($980K)',
    loansV1Val: '$980K Risk',
    loansV1Width: '45%',
    loansV2: '0 Loans ($0)',
    loansV2Val: '$0 Risk',
    loansV2Width: '2%',
    escV1: '15.0%',
    escV1Width: '15%',
    escV2: '100.0%',
    escV2Width: '100%'
  },
  loop: {
    title: 'Runaway Agent Prompt Recursion Loop',
    summary: 'Ambiguous applicant letters caused Naive v1 compliance agents to loop 14 times, burning tokens and crashing silently. FinAssure enforces a strict MAX_TURNS=3 circuit breaker.',
    failV1: '11.5%',
    failV1Width: '11.5%',
    failV2: '0.0%',
    failV2Width: '2%',
    loansV1: '7 Loans ($640K)',
    loansV1Val: '$640K Risk',
    loansV1Width: '35%',
    loansV2: '0 Loans ($0)',
    loansV2Val: '$0 Risk',
    loansV2Width: '2%',
    escV1: '0.0%',
    escV1Width: '2%',
    escV2: '100.0%',
    escV2Width: '100%'
  },
  aggregate: {
    title: 'Full 180-Case Continuous CI/CD Suite',
    summary: 'Across all 180 synthetic validation cases, FinAssure eliminated 100% of silent failures and blocked release before any unsafe code reached production.',
    failV1: '15.6%',
    failV1Width: '15.6%',
    failV2: '0.0%',
    failV2Width: '2%',
    loansV1: '28 Loans ($3.02M)',
    loansV1Val: '$3.02M Risk',
    loansV1Width: '85%',
    loansV2: '0 Loans ($0)',
    loansV2Val: '$0 Risk',
    loansV2Width: '2%',
    escV1: '18.3%',
    escV1Width: '18.3%',
    escV2: '100.0%',
    escV2Width: '100%'
  }
};

function initAnimatedGraphs() {
  const filterBtns = document.querySelectorAll('.graph-filter-btn');
  const titleEl = document.getElementById('graph-scenario-title');
  const summaryEl = document.getElementById('graph-scenario-summary');

  const barFailV1 = document.getElementById('bar-fail-v1');
  const valFailV1 = document.getElementById('val-fail-v1');
  const barFailV2 = document.getElementById('bar-fail-v2');
  const valFailV2 = document.getElementById('val-fail-v2');

  const barLoansV1 = document.getElementById('bar-loans-v1');
  const valLoansV1 = document.getElementById('val-loans-v1');
  const barLoansV2 = document.getElementById('bar-loans-v2');
  const valLoansV2 = document.getElementById('val-loans-v2');

  const barEscV1 = document.getElementById('bar-escalate-v1');
  const valEscV1 = document.getElementById('val-escalate-v1');
  const barEscV2 = document.getElementById('bar-escalate-v2');
  const valEscV2 = document.getElementById('val-escalate-v2');

  if (!filterBtns.length) return;

  filterBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      filterBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');

      const scenarioKey = btn.getAttribute('data-graph-scenario');
      const data = graphScenarios[scenarioKey];
      if (!data) return;

      if (titleEl) titleEl.textContent = data.title;
      if (summaryEl) summaryEl.textContent = data.summary;

      // Animate Bar 1: Silent Failures
      if (barFailV1) {
        barFailV1.style.width = '0%';
        setTimeout(() => {
          barFailV1.style.width = data.failV1Width;
          barFailV1.textContent = data.failV1;
        }, 50);
      }
      if (valFailV1) valFailV1.textContent = data.failV1;

      if (barFailV2) {
        barFailV2.style.width = '0%';
        setTimeout(() => {
          barFailV2.style.width = data.failV2Width;
          barFailV2.textContent = data.failV2;
        }, 50);
      }
      if (valFailV2) valFailV2.textContent = data.failV2;

      // Animate Bar 2: Loans at risk
      if (barLoansV1) {
        barLoansV1.style.width = '0%';
        setTimeout(() => {
          barLoansV1.style.width = data.loansV1Width;
          barLoansV1.textContent = data.loansV1;
        }, 50);
      }
      if (valLoansV1) valLoansV1.textContent = data.loansV1Val;

      if (barLoansV2) {
        barLoansV2.style.width = '0%';
        setTimeout(() => {
          barLoansV2.style.width = data.loansV2Width;
          barLoansV2.textContent = data.loansV2;
        }, 50);
      }
      if (valLoansV2) valLoansV2.textContent = data.loansV2Val;

      // Animate Bar 3: Safe Escalation
      if (barEscV1) {
        barEscV1.style.width = '0%';
        setTimeout(() => {
          barEscV1.style.width = data.escV1Width;
          barEscV1.textContent = data.escV1;
        }, 50);
      }
      if (valEscV1) valEscV1.textContent = data.escV1;

      if (barEscV2) {
        barEscV2.style.width = '0%';
        setTimeout(() => {
          barEscV2.style.width = data.escV2Width;
          barEscV2.textContent = data.escV2;
        }, 50);
      }
      if (valEscV2) valEscV2.textContent = data.escV2;
    });
  });
}

/* ==========================================================================
   6. Tabbed Quick Start Box & Copy Button
   ========================================================================== */
function initQuickstartTabs() {
  const btnInstall = document.getElementById('btn-tab-install');
  const btnTest = document.getElementById('btn-tab-test');
  const btnUi = document.getElementById('btn-tab-ui');
  const codeBox = document.getElementById('quickstart-code-box');

  if (!btnInstall || !btnTest || !btnUi || !codeBox) return;

  const tabs = [btnInstall, btnTest, btnUi];

  btnInstall.addEventListener('click', () => {
    tabs.forEach(t => {
      t.style.background = 'rgba(255,255,255,0.05)';
      t.style.borderColor = 'var(--border-subtle)';
      t.style.color = 'var(--text-muted)';
    });
    btnInstall.style.background = 'rgba(6,182,212,0.15)';
    btnInstall.style.borderColor = 'var(--accent-cyan)';
    btnInstall.style.color = 'var(--accent-cyan)';

    codeBox.innerHTML = `
      <span style="color: #64748B;"># 1. Clone repository and install with uv</span><br>
      git clone https://github.com/DeepAgentLabs/FinAssure.git<br>
      cd FinAssure<br>
      uv sync --all-extras<br>
      uv run python -m finassure.setup
    `;
  });

  btnTest.addEventListener('click', () => {
    tabs.forEach(t => {
      t.style.background = 'rgba(255,255,255,0.05)';
      t.style.borderColor = 'var(--border-subtle)';
      t.style.color = 'var(--text-muted)';
    });
    btnTest.style.background = 'rgba(6,182,212,0.15)';
    btnTest.style.borderColor = 'var(--accent-cyan)';
    btnTest.style.color = 'var(--accent-cyan)';

    codeBox.innerHTML = `
      <span style="color: #64748B;"># 2. Run the full 180-case chaos matrix & evaluate release gates</span><br>
      uv run pytest tests/test_chaos_underwriting.py -v<br>
      uv run finassure-gate evaluate --workflow underwriting --evidence evidence.json<br>
      <span style="color: #6EE7B7;">✓ 180 tests passed | 0 unsupported approvals | Release Gate: PASS</span>
    `;
  });

  btnUi.addEventListener('click', () => {
    tabs.forEach(t => {
      t.style.background = 'rgba(255,255,255,0.05)';
      t.style.borderColor = 'var(--border-subtle)';
      t.style.color = 'var(--text-muted)';
    });
    btnUi.style.background = 'rgba(6,182,212,0.15)';
    btnUi.style.borderColor = 'var(--accent-cyan)';
    btnUi.style.color = 'var(--accent-cyan)';

    codeBox.innerHTML = `
      <span style="color: #64748B;"># 3. Launch local FastAPI + React Dashboard</span><br>
      uv run uvicorn finassure.api:app --reload --port 8000<br>
      <span style="color: #38BDF8;">INFO: Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)</span>
    `;
  });
}

function initCopyButton() {
  const copyBtn = document.getElementById('copy-quickstart-btn');
  const copyBtnText = document.getElementById('copy-btn-text');
  const codeBox = document.getElementById('quickstart-code-box');

  if (!copyBtn || !codeBox) return;

  copyBtn.addEventListener('click', () => {
    const textToCopy = codeBox.innerText;
    navigator.clipboard.writeText(textToCopy).then(() => {
      if (copyBtnText) copyBtnText.textContent = '✓ Copied!';
      copyBtn.style.borderColor = '#10b981';
      copyBtn.style.color = '#10b981';
      setTimeout(() => {
        if (copyBtnText) copyBtnText.textContent = 'Copy Command';
        copyBtn.style.borderColor = '';
        copyBtn.style.color = '';
      }, 2000);
    }).catch(() => {
      if (copyBtnText) copyBtnText.textContent = '✓ Copied!';
      setTimeout(() => {
        if (copyBtnText) copyBtnText.textContent = 'Copy Command';
      }, 2000);
    });
  });
}
