/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';

export default function App() {
  // Desktop state
  const [desktopTourTab, setDesktopTourTab] = useState<1 | 2 | 3>(1);
  const [desktopCodeTab, setDesktopCodeTab] = useState<'py' | 'yaml'>('py');
  const [desktopPipCopied, setDesktopPipCopied] = useState(false);
  const [desktopSnippetCopied, setDesktopSnippetCopied] = useState(false);

  // Mobile state
  const [mobileTourTab, setMobileTourTab] = useState<'inject' | 'corrupt' | 'score'>('inject');
  const [mobilePipCopied, setMobilePipCopied] = useState(false);
  const [mobileCodeCopied, setMobileCodeCopied] = useState(false);
  const [mobileActiveNav, setMobileActiveNav] = useState<'overview' | 'scenarios' | 'telemetry' | 'docs'>('overview');

  const logoUrl =
    'https://lh3.googleusercontent.com/aida/AEtjO1Xey5kSUdodaoN55XlpdOdw-Zi4DsNq6w0PRF7F8S8mQT3tUVlAGfZ6jqPvv59k0Fdb0ZqeNqXkniVxqGpf0DI-hkGBZ56QOAA0x-9TWC8wM7EHn4vJUSde9bJLvznhBNv2Qic7eya7ElMUZIYHXnBxN49vYON4DC1ywZSlWloRH7kf09bIo7mWXa2mw0EhDRieYnw66NUfPWAhToIvB-_7QQ4ACYwJnPLntABRIoebFou_ID67jUsmpgEx';

  // Desktop copy pip
  const handleDesktopCopyPip = () => {
    navigator.clipboard.writeText('pip install agentic-chaos');
    setDesktopPipCopied(true);
    setTimeout(() => setDesktopPipCopied(false), 2000);
  };

  // Desktop copy snippet
  const handleDesktopCopySnippet = () => {
    const text =
      desktopCodeTab === 'py'
        ? `from agentic_chaos.chaos import chaos_call, chaos_session, TokenTimeoutFault\nfrom agentic_chaos.agents import ToolCallFailureFault, wrap_tool\n\n# Wrap external tool and stress with simulated failure\nsearch = wrap_tool(search_fn, tool_name="web_search")\nwith chaos_session([\n    ToolCallFailureFault(tool_name="web_search", timeout_seconds=3.0),\n    TokenTimeoutFault(hang_seconds=2.0)\n]) as session:\n    result = search("AAPL quarterly filing")\n    print(session.events[0].outcome)  # 'errored' / 'degraded'`
        : `agentic-chaos chaos run my_agent.py \\\n  --inject token_timeout,rate_limit_storm,tool_failure \\\n  --save chaos_report.json`;
    navigator.clipboard.writeText(text);
    setDesktopSnippetCopied(true);
    setTimeout(() => setDesktopSnippetCopied(false), 2000);
  };

  // Mobile copy pip
  const handleMobileCopyPip = () => {
    navigator.clipboard.writeText('pip install agentic-chaos');
    setMobilePipCopied(true);
    setTimeout(() => setMobilePipCopied(false), 2000);
  };

  // Mobile copy snippet
  const handleMobileCopySnippet = () => {
    const snippet = `from agentic_chaos.chaos import chaos_session, TokenTimeoutFault\nfrom agentic_chaos.agents import MemoryCorruptionFault\n\nwith chaos_session([\n    TokenTimeoutFault(hang_seconds=4.0),\n    MemoryCorruptionFault(variable_name="scratchpad", mode="decay")\n]) as session:\n    result = supervisor_agent.run("Reconcile invoice #889")\n    assert len(session.events) > 0`;
    navigator.clipboard.writeText(snippet);
    setMobileCodeCopied(true);
    setTimeout(() => setMobileCodeCopied(false), 2000);
  };

  // Mobile bottom tab navigation scroll
  const handleMobileNavClick = (tab: 'overview' | 'scenarios' | 'telemetry' | 'docs') => {
    setMobileActiveNav(tab);
    if (tab === 'overview') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else if (tab === 'scenarios') {
      const el = document.getElementById('mobile-failure-matrix');
      el?.scrollIntoView({ behavior: 'smooth' });
    } else if (tab === 'telemetry') {
      const el = document.getElementById('mobile-interactive-demo');
      el?.scrollIntoView({ behavior: 'smooth' });
    } else if (tab === 'docs') {
      const el = document.getElementById('mobile-quickstart-snippet');
      el?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="w-full min-h-screen bg-surface-base text-on-surface antialiased">
      {/* ========================================================================= */}
      {/* DESKTOP VIEW (Visible on lg screens: 1024px and above)                   */}
      {/* ========================================================================= */}
      <div className="hidden lg:block w-full">
        {/* DESKTOP HEADER */}
        <header className="fixed top-0 w-full z-50 bg-surface-base/85 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
          <div className="h-16 max-w-7xl mx-auto px-6 lg:px-12 flex items-center justify-between">
            <div className="flex items-center gap-space-md">
              <a className="flex items-center gap-space-sm focus:outline-none" href="#">
                <img
                  alt="AgenticChaos Logo"
                  className="h-8 w-auto object-contain"
                  src={logoUrl}
                />
                <div className="flex flex-col">
                  <span className="font-headline-sm text-headline-sm tracking-tight text-text-primary leading-none">
                    AgenticChaos
                  </span>
                  <span className="font-label-caps text-label-caps text-text-muted leading-tight">
                    BY DEEPAGENTLABS
                  </span>
                </div>
              </a>
            </div>

            <nav className="flex items-center gap-space-lg">
              <a
                className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors py-space-xs px-space-sm rounded-lg"
                href="#hero"
              >
                Platform
              </a>
              <a
                className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors py-space-xs px-space-sm rounded-lg"
                href="#chaos-spectrum"
              >
                Chaos Modules
              </a>
              <a
                className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors py-space-xs px-space-sm rounded-lg"
                href="#architecture"
              >
                Architecture
              </a>
              <a
                className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors py-space-xs px-space-sm rounded-lg"
                href="#how-it-works"
              >
                How it works
              </a>
              <a
                className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors py-space-xs px-space-sm rounded-lg"
                href="#docs"
              >
                Docs
              </a>
            </nav>

            <div className="flex items-center gap-space-md">
              <a
                className="inline-flex items-center gap-space-xs font-code-md text-code-md bg-surface-card text-text-primary px-space-md py-space-xs rounded-lg hover:bg-surface-overlay hover:text-accent-cyan transition-colors"
                href="https://github.com/DeepAgentLabs/agentic-chaos"
                rel="noopener noreferrer"
                target="_blank"
              >
                <span className="text-accent-cyan font-headline-sm">$</span>
                <span>gh/agentic-chaos</span>
              </a>
              <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                <span className="material-symbols-outlined text-on-primary text-[18px]">person</span>
              </div>
            </div>
          </div>
        </header>

        {/* DESKTOP MAIN CONTENT */}
        <main className="w-full pt-16 bg-surface-base min-h-screen">
          <div className="flex flex-col w-full">
            {/* HERO SECTION */}
            <section id="hero" className="relative w-full max-w-7xl mx-auto px-6 lg:px-12 pt-8 pb-20 overflow-hidden">
              <div className="absolute -top-24 left-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl pointer-events-none -z-10" />
              <div className="absolute top-1/3 right-10 w-[500px] h-[500px] bg-accent-cyan/5 rounded-full blur-[100px] pointer-events-none -z-10" />
              <div className="grid grid-cols-12 gap-12 items-center">
                {/* Left Column */}
                <div className="col-span-6 flex flex-col items-start gap-space-lg">
                  <div className="inline-flex items-center gap-space-xs px-3 py-1 rounded-full bg-surface-card border border-border-subtle shadow-sm hover:border-border-strong transition-colors cursor-default">
                    <span className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse" />
                    <span className="font-code-md text-code-md text-text-secondary tracking-wide">
                      Open-source · Fault-injection · Framework-neutral
                    </span>
                  </div>

                  <h1 className="font-display text-display text-text-primary tracking-tight leading-[1.08]">
                    Break agentic AI before users do <br />
                    <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan via-primary to-secondary">
                      with chaos.
                    </span>
                  </h1>

                  <p className="font-body-lg text-body-lg text-text-secondary max-w-xl leading-relaxed">
                    AgenticChaos injects latency, state corruption, context drift, and tool failures to
                    stress-test autonomous LLM agents—without requiring mock rewrites or fragile test
                    harnesses.
                  </p>

                  <div className="flex items-center gap-space-md pt-2">
                    <a
                      className="inline-flex items-center justify-center gap-space-xs px-5 py-3 rounded-lg bg-primary hover:bg-primary-container text-surface-base font-headline-sm text-headline-sm transition-all shadow-[0_0_20px_rgba(56,189,248,0.25)] hover:shadow-[0_0_28px_rgba(56,189,248,0.45)]"
                      href="#interactive-tour"
                    >
                      <span>Explore the live demo</span>
                      <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                    </a>

                    <div
                      className="flex items-center justify-between gap-space-sm px-4 py-3 rounded-lg bg-surface-card border border-border-subtle hover:border-border-strong text-text-primary font-code-md text-code-md transition-all cursor-pointer group"
                      onClick={handleDesktopCopyPip}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-accent-cyan select-none">$</span>
                        <span className="text-text-primary group-hover:text-accent-cyan transition-colors">
                          {desktopPipCopied ? 'Copied!' : 'pip install agentic-chaos'}
                        </span>
                      </div>
                      <span className="material-symbols-outlined text-[16px] text-text-muted group-hover:text-text-primary transition-colors">
                        {desktopPipCopied ? 'check' : 'content_copy'}
                      </span>
                    </div>

                    <a
                      className="font-body-md text-body-md text-text-secondary hover:text-text-primary px-3 py-2 transition-colors flex items-center gap-1"
                      href="#docs"
                    >
                      <span>View Docs</span>
                      <span className="material-symbols-outlined text-[16px]">north_east</span>
                    </a>
                  </div>

                  <div className="grid grid-cols-3 gap-6 pt-6 border-t border-border-subtle w-full max-w-lg mt-2">
                    <div>
                      <div className="font-headline-md text-headline-md text-text-primary font-semibold tracking-tight">
                        100%
                      </div>
                      <div className="font-label-caps text-label-caps text-text-muted mt-1 uppercase tracking-wider">
                        Deterministic Seeds
                      </div>
                    </div>
                    <div>
                      <div className="font-headline-md text-headline-md text-text-primary font-semibold tracking-tight">
                        0.2ms
                      </div>
                      <div className="font-label-caps text-label-caps text-text-muted mt-1 uppercase tracking-wider">
                        Interceptor Overhead
                      </div>
                    </div>
                    <div>
                      <div className="font-headline-md text-headline-md text-text-primary font-semibold tracking-tight">
                        0
                      </div>
                      <div className="font-label-caps text-label-caps text-text-muted mt-1 uppercase tracking-wider">
                        External Dependencies
                      </div>
                    </div>
                  </div>
                </div>

                {/* Right Column: Live Terminal Trace */}
                <div className="col-span-6 w-full">
                  <div className="relative rounded-xl border border-border-subtle bg-surface-card/90 shadow-2xl backdrop-blur-sm overflow-hidden group hover:border-border-strong transition-all">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle bg-surface-raised/80">
                      <div className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-full bg-error-rose/60" />
                        <div className="w-2.5 h-2.5 rounded-full bg-warning-amber/60" />
                        <div className="w-2.5 h-2.5 rounded-full bg-accent-emerald/60" />
                        <span className="ml-2 font-code-md text-code-md text-text-secondary">
                          agentic-chaos-interceptor.json
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-ping" />
                        <span className="font-label-caps text-label-caps text-accent-cyan tracking-widest uppercase">
                          LIVE TRACE
                        </span>
                      </div>
                    </div>

                    <div className="p-5 flex flex-col gap-3 font-code-md text-code-md">
                      <div className="flex items-center justify-between p-3 rounded-lg bg-surface-base/60 border border-border-subtle/40 hover:border-border-subtle transition-colors">
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="w-6 h-6 rounded flex items-center justify-center bg-surface-overlay text-text-muted text-[11px] font-medium border border-border-subtle">
                            01
                          </span>
                          <span className="text-text-primary font-semibold">PLANNER</span>
                          <span className="text-text-secondary truncate">Delegate (market_analyst)</span>
                        </div>
                        <span className="text-text-muted shrink-0 text-right">1.2 ms</span>
                      </div>

                      <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-warning-amber/5 border border-warning-amber/30 transition-colors relative overflow-hidden">
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-warning-amber" />
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3 min-w-0">
                            <span className="w-6 h-6 rounded flex items-center justify-center bg-warning-amber/20 text-warning-amber text-[11px] font-semibold border border-warning-amber/40">
                              02
                            </span>
                            <span className="text-warning-amber font-semibold">SEARCH_TOOL</span>
                            <span className="text-text-secondary truncate">HTTP 504 Gateway Timeout</span>
                          </div>
                          <span className="text-warning-amber font-semibold shrink-0 text-right">
                            2,400 ms
                          </span>
                        </div>
                        <div className="flex items-center justify-between pl-9 text-xs">
                          <span className="text-text-muted">
                            Synthetic latency + connection reset injected
                          </span>
                          <span className="px-2 py-0.5 rounded text-[10px] uppercase font-semibold tracking-wider bg-warning-amber/20 text-warning-amber border border-warning-amber/30">
                            FAULT_INJECTED
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center justify-between p-3 rounded-lg bg-surface-base/60 border border-border-subtle/40 hover:border-border-subtle transition-colors">
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="w-6 h-6 rounded flex items-center justify-center bg-surface-overlay text-text-muted text-[11px] font-medium border border-border-subtle">
                            03
                          </span>
                          <span className="text-text-primary font-semibold">FALLBACK</span>
                          <span className="text-text-secondary truncate">Cache / Alternate Model invoked</span>
                        </div>
                        <span className="text-text-muted shrink-0 text-right">85 ms</span>
                      </div>

                      <div className="flex items-center justify-between p-3 rounded-lg bg-accent-emerald/5 border border-accent-emerald/20 transition-colors">
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="w-6 h-6 rounded flex items-center justify-center bg-accent-emerald/20 text-accent-emerald text-[11px] font-semibold border border-accent-emerald/30">
                            04
                          </span>
                          <span className="text-accent-emerald font-semibold">RECOVERY</span>
                          <span className="text-text-secondary truncate">Resilient deterministic output</span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/30 uppercase flex items-center gap-1">
                            <span className="material-symbols-outlined text-[12px]">check</span>
                            RECOVERED
                          </span>
                          <span className="text-text-muted text-right">1.4 ms</span>
                        </div>
                      </div>
                    </div>

                    <div className="px-5 py-3 border-t border-border-subtle bg-surface-raised/90 flex items-center justify-between gap-4 font-code-md text-code-md">
                      <div className="flex items-center gap-2">
                        <span className="text-text-muted uppercase text-[11px]">STATUS</span>
                        <div className="flex items-center gap-1.5 text-accent-emerald font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald" />
                          <span>Succeeded (Fault Handled)</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-5 text-text-secondary">
                        <div>
                          <span className="text-text-muted text-[11px] mr-1.5 uppercase">SPANS</span>
                          <span className="text-text-primary font-medium">8</span>
                        </div>
                        <div>
                          <span className="text-text-muted text-[11px] mr-1.5 uppercase">FAULTS</span>
                          <span className="text-warning-amber font-medium">1</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-text-muted text-[11px] uppercase">RESILIENCE</span>
                          <span className="px-2 py-0.5 rounded text-accent-emerald font-bold bg-accent-emerald/10 border border-accent-emerald/30">
                            94/100
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* ECOSYSTEM LOGO COMPATIBILITY STRIP */}
            <section className="w-full border-y border-border-subtle bg-surface-raised/40 py-6">
              <div className="max-w-7xl mx-auto px-6 lg:px-12 flex items-center justify-between gap-6">
                <span className="font-label-caps text-label-caps text-text-muted tracking-widest uppercase shrink-0">
                  BUILT FOR THE MODERN AGENT STACK
                </span>
                <div className="flex items-center justify-end gap-8 lg:gap-12 text-text-muted font-code-md text-code-md">
                  <div className="flex items-center gap-2 hover:text-text-primary transition-colors cursor-default">
                    <span className="material-symbols-outlined text-[18px] text-accent-cyan">account_tree</span>
                    <span>LangGraph</span>
                  </div>
                  <div className="flex items-center gap-2 hover:text-text-primary transition-colors cursor-default">
                    <span className="material-symbols-outlined text-[18px] text-primary">link</span>
                    <span>LangChain</span>
                  </div>
                  <div className="flex items-center gap-2 hover:text-text-primary transition-colors cursor-default">
                    <span className="material-symbols-outlined text-[18px] text-secondary">database</span>
                    <span>LlamaIndex</span>
                  </div>
                  <div className="flex items-center gap-2 hover:text-text-primary transition-colors cursor-default">
                    <span className="material-symbols-outlined text-[18px] text-tertiary">groups</span>
                    <span>CrewAI</span>
                  </div>
                  <div className="flex items-center gap-2 hover:text-text-primary transition-colors cursor-default">
                    <span className="material-symbols-outlined text-[18px] text-accent-cyan">hub</span>
                    <span>AutoGen</span>
                  </div>
                  <div className="flex items-center gap-2 hover:text-text-primary transition-colors cursor-default">
                    <span className="material-symbols-outlined text-[18px] text-text-primary">smart_toy</span>
                    <span>OpenAI Assistants</span>
                  </div>
                  <div className="flex items-center gap-2 hover:text-text-primary transition-colors cursor-default">
                    <span className="material-symbols-outlined text-[18px] text-warning-amber">terminal</span>
                    <span>Raw Python Agents</span>
                  </div>
                </div>
              </div>
            </section>

            {/* THE CHAOS SPECTRUM */}
            <section id="chaos-spectrum" className="w-full max-w-7xl mx-auto px-6 lg:px-12 py-24">
              <div className="flex items-end justify-between mb-16 gap-6">
                <div className="flex flex-col gap-2 max-w-2xl">
                  <span className="font-label-caps text-label-caps text-accent-cyan tracking-widest uppercase">
                    THE CHAOS SPECTRUM
                  </span>
                  <h2 className="font-headline-lg text-headline-lg text-text-primary tracking-tight leading-tight">
                    From stochastic failures to deterministic resilience.
                  </h2>
                </div>
                <p className="font-body-md text-body-md text-text-secondary max-w-md">
                  Autonomous agents fail differently than web servers. Single hallucinated parameters or
                  flaky APIs trigger runaway token billing and cascading agent deadlocks.
                </p>
              </div>

              <div className="grid grid-cols-4 gap-6">
                {/* Card 01 */}
                <div className="group relative flex flex-col justify-between p-6 rounded-xl bg-surface-card border border-border-subtle hover:border-border-strong hover:bg-surface-overlay/40 transition-all">
                  <div>
                    <div className="flex items-center justify-between pb-6">
                      <div className="w-10 h-10 rounded-lg bg-surface-raised flex items-center justify-center border border-border-subtle text-accent-cyan group-hover:border-accent-cyan/40 transition-colors">
                        <span className="material-symbols-outlined text-[20px]">cloud_off</span>
                      </div>
                      <span className="font-code-md text-code-md text-text-muted">01</span>
                    </div>
                    <h3 className="font-headline-sm text-headline-sm text-text-primary mb-2">Flaky External Tools</h3>
                    <p className="font-body-sm text-body-sm text-text-secondary leading-relaxed">
                      Inject synthetic HTTP 429 rate limits, 502/504 timeouts, dropped packets, and mutated JSON
                      schemas into live tools to verify recovery strategies.
                    </p>
                  </div>
                  <div className="pt-6 mt-6 border-t border-border-subtle/50 flex items-center justify-between">
                    <span className="font-code-md text-code-md text-text-muted group-hover:text-accent-cyan transition-colors">
                      Module: tool_chaos
                    </span>
                    <span className="material-symbols-outlined text-[16px] text-text-muted group-hover:translate-x-1 transition-transform">
                      arrow_forward
                    </span>
                  </div>
                </div>

                {/* Card 02 */}
                <div className="group relative flex flex-col justify-between p-6 rounded-xl bg-surface-card border border-border-subtle hover:border-border-strong hover:bg-surface-overlay/40 transition-all">
                  <div>
                    <div className="flex items-center justify-between pb-6">
                      <div className="w-10 h-10 rounded-lg bg-surface-raised flex items-center justify-center border border-border-subtle text-primary group-hover:border-primary/40 transition-colors">
                        <span className="material-symbols-outlined text-[20px]">psychology_alt</span>
                      </div>
                      <span className="font-code-md text-code-md text-text-muted">02</span>
                    </div>
                    <h3 className="font-headline-sm text-headline-sm text-text-primary mb-2">Context Memory Drift</h3>
                    <p className="font-body-sm text-body-sm text-text-secondary leading-relaxed">
                      Corrupt scratchpad state, truncate vector store recall chunks, or inject conflicting memory
                      observations across multi-turn delegation chains.
                    </p>
                  </div>
                  <div className="pt-6 mt-6 border-t border-border-subtle/50 flex items-center justify-between">
                    <span className="font-code-md text-code-md text-text-muted group-hover:text-primary transition-colors">
                      Module: state_drift
                    </span>
                    <span className="material-symbols-outlined text-[16px] text-text-muted group-hover:translate-x-1 transition-transform">
                      arrow_forward
                    </span>
                  </div>
                </div>

                {/* Card 03 */}
                <div className="group relative flex flex-col justify-between p-6 rounded-xl bg-surface-card border border-border-subtle hover:border-border-strong hover:bg-surface-overlay/40 transition-all">
                  <div>
                    <div className="flex items-center justify-between pb-6">
                      <div className="w-10 h-10 rounded-lg bg-surface-raised flex items-center justify-center border border-border-subtle text-warning-amber group-hover:border-warning-amber/40 transition-colors">
                        <span className="material-symbols-outlined text-[20px]">sync_problem</span>
                      </div>
                      <span className="font-code-md text-code-md text-text-muted">03</span>
                    </div>
                    <h3 className="font-headline-sm text-headline-sm text-text-primary mb-2">Loop Cascades</h3>
                    <p className="font-body-sm text-body-sm text-text-secondary leading-relaxed">
                      Expose infinite tool-call ping-pongs between sub-agents and calculate peak runaway token expense
                      before shipping autonomous agents to production.
                    </p>
                  </div>
                  <div className="pt-6 mt-6 border-t border-border-subtle/50 flex items-center justify-between">
                    <span className="font-code-md text-code-md text-text-muted group-hover:text-warning-amber transition-colors">
                      Module: runaway_guard
                    </span>
                    <span className="material-symbols-outlined text-[16px] text-text-muted group-hover:translate-x-1 transition-transform">
                      arrow_forward
                    </span>
                  </div>
                </div>

                {/* Card 04 */}
                <div className="group relative flex flex-col justify-between p-6 rounded-xl bg-surface-card border border-border-subtle hover:border-border-strong hover:bg-surface-overlay/40 transition-all">
                  <div>
                    <div className="flex items-center justify-between pb-6">
                      <div className="w-10 h-10 rounded-lg bg-surface-raised flex items-center justify-center border border-border-subtle text-accent-emerald group-hover:border-accent-emerald/40 transition-colors">
                        <span className="material-symbols-outlined text-[20px]">shield_lock</span>
                      </div>
                      <span className="font-code-md text-code-md text-text-muted">04</span>
                    </div>
                    <h3 className="font-headline-sm text-headline-sm text-text-primary mb-2">Brittle Fallbacks</h3>
                    <p className="font-body-sm text-body-sm text-text-secondary leading-relaxed">
                      Verify whether backup models, retry backoffs, human-in-the-loop triggers, and circuit breakers
                      actually engage cleanly under extreme operational load.
                    </p>
                  </div>
                  <div className="pt-6 mt-6 border-t border-border-subtle/50 flex items-center justify-between">
                    <span className="font-code-md text-code-md text-text-muted group-hover:text-accent-emerald transition-colors">
                      Module: breaker_verify
                    </span>
                    <span className="material-symbols-outlined text-[16px] text-text-muted group-hover:translate-x-1 transition-transform">
                      arrow_forward
                    </span>
                  </div>
                </div>
              </div>
            </section>

            {/* INTERACTIVE FAULT INJECTION TOUR */}
            <section className="w-full max-w-7xl mx-auto px-6 lg:px-12 py-16" id="interactive-tour">
              <div className="flex items-end justify-between mb-8 gap-4">
                <div>
                  <span className="font-label-caps text-label-caps text-accent-cyan tracking-widest uppercase">
                    INTERACTIVE FAULT INJECTION TOUR
                  </span>
                  <h2 className="font-headline-lg text-headline-lg text-text-primary tracking-tight mt-1">
                    Inject. Corrupt. Gate.
                  </h2>
                </div>
                <p className="font-body-sm text-body-sm text-text-secondary max-w-md">
                  Explore how AgenticChaos wraps the agent execution lifecycle to discover silent failure modes before
                  deployments.
                </p>
              </div>

              <div className="rounded-xl border border-border-subtle bg-surface-card overflow-hidden shadow-2xl">
                {/* Tabs Rail */}
                <div className="grid grid-cols-3 border-b border-border-subtle bg-surface-raised text-center font-code-md text-code-md select-none">
                  <button
                    onClick={() => setDesktopTourTab(1)}
                    className={`py-3.5 px-4 font-medium border-b-2 transition-all flex items-center justify-center gap-2 cursor-pointer ${
                      desktopTourTab === 1
                        ? 'border-primary text-text-primary bg-surface-card'
                        : 'border-transparent text-text-muted hover:text-text-primary'
                    }`}
                  >
                    <span className="text-accent-cyan">01</span>
                    <span>INJECT FAULTS</span>
                  </button>
                  <button
                    onClick={() => setDesktopTourTab(2)}
                    className={`py-3.5 px-4 font-medium border-b-2 transition-all flex items-center justify-center gap-2 cursor-pointer ${
                      desktopTourTab === 2
                        ? 'border-primary text-text-primary bg-surface-card'
                        : 'border-transparent text-text-muted hover:text-text-primary'
                    }`}
                  >
                    <span className="text-text-muted">02</span>
                    <span>CORRUPT MEMORY</span>
                  </button>
                  <button
                    onClick={() => setDesktopTourTab(3)}
                    className={`py-3.5 px-4 font-medium border-b-2 transition-all flex items-center justify-center gap-2 cursor-pointer ${
                      desktopTourTab === 3
                        ? 'border-primary text-text-primary bg-surface-card'
                        : 'border-transparent text-text-muted hover:text-text-primary'
                    }`}
                  >
                    <span className="text-text-muted">03</span>
                    <span>RESILIENCE GATE</span>
                  </button>
                </div>

                {/* Tab Content Panels */}
                <div className="p-8 lg:p-12">
                  {desktopTourTab === 1 && (
                    <div className="grid grid-cols-12 gap-10 items-center">
                      <div className="col-span-5 flex flex-col gap-6">
                        <span className="font-label-caps text-label-caps text-accent-cyan uppercase">
                          SYNTHETIC NETWORK &amp; API JITTER
                        </span>
                        <h3 className="font-headline-md text-headline-md text-text-primary">
                          Target tool nodes without refactoring agent code.
                        </h3>
                        <p className="font-body-md text-body-md text-text-secondary leading-relaxed">
                          Wrap any tool invocation or model gateway. Define fault rules in YAML or Python to simulate
                          slow connections, rate exhaustion, and schema drift.
                        </p>
                        <div className="flex flex-col gap-3 font-body-sm text-body-sm text-text-secondary">
                          <div className="flex items-center gap-2.5">
                            <span className="material-symbols-outlined text-accent-emerald text-[18px]">
                              check_circle
                            </span>
                            <span>Configurable fault probability (0.0 to 1.0)</span>
                          </div>
                          <div className="flex items-center gap-2.5">
                            <span className="material-symbols-outlined text-accent-emerald text-[18px]">
                              check_circle
                            </span>
                            <span>Custom jitter distribution (Gaussian / Pareto spikes)</span>
                          </div>
                          <div className="flex items-center gap-2.5">
                            <span className="material-symbols-outlined text-accent-emerald text-[18px]">
                              check_circle
                            </span>
                            <span>Exact seed reproducibility for CI/CD regressions</span>
                          </div>
                        </div>
                      </div>

                      <div className="col-span-7 bg-surface-raised rounded-lg border border-border-subtle p-5 font-code-md text-code-md">
                        <div className="flex items-center justify-between pb-3 mb-4 border-b border-border-subtle text-xs text-text-muted">
                          <span>chaos_config.py</span>
                          <span className="text-accent-cyan">ACTIVE INTERCEPTOR</span>
                        </div>
                        <pre className="text-text-primary leading-relaxed overflow-x-auto">
                          <code>
                            <span className="text-secondary">from</span> agentic_chaos.chaos{' '}
                            <span className="text-secondary">import</span> TokenTimeoutFault, RateLimitStormFault
                            {'\n'}
                            <span className="text-secondary">from</span> agentic_chaos.agents{' '}
                            <span className="text-secondary">import</span> ToolCallFailureFault
                            {'\n\n'}
                            <span className="text-text-muted"># Configure active multi-layer fault suite</span>
                            {'\n'}
                            faults = [{'\n'}    ToolCallFailureFault(tool_name=
                            <span className="text-secondary">"fetch_quotes"</span>, timeout_seconds=
                            <span className="text-warning-amber">3.2</span>),{'\n'}    RateLimitStormFault(burst_count=
                            <span className="text-warning-amber">3</span>, retry_after=
                            <span className="text-warning-amber">5.0</span>),{'\n'}    TokenTimeoutFault(hang_seconds=
                            <span className="text-warning-amber">2.0</span>, mode=
                            <span className="text-secondary">"delay"</span>){'\n'}]
                          </code>
                        </pre>
                      </div>
                    </div>
                  )}

                  {desktopTourTab === 2 && (
                    <div className="grid grid-cols-12 gap-10 items-center">
                      <div className="col-span-5 flex flex-col gap-6">
                        <span className="font-label-caps text-label-caps text-secondary uppercase">
                          STATE DRIFT &amp; MEMORY TOXICITY
                        </span>
                        <h3 className="font-headline-md text-headline-md text-text-primary">
                          Corrupt context windows to detect delusion loops.
                        </h3>
                        <p className="font-body-md text-body-md text-text-secondary leading-relaxed">
                          Autonomous agents accumulate drift across long runs. AgenticChaos deliberately drops keys,
                          mutates variable bindings, and truncates chat history to observe state repair.
                        </p>
                        <div className="flex flex-col gap-3 font-body-sm text-body-sm text-text-secondary">
                          <div className="flex items-center gap-2.5">
                            <span className="material-symbols-outlined text-accent-emerald text-[18px]">
                              check_circle
                            </span>
                            <span>Semantic needle-in-haystack eviction</span>
                          </div>
                          <div className="flex items-center gap-2.5">
                            <span className="material-symbols-outlined text-accent-emerald text-[18px]">
                              check_circle
                            </span>
                            <span>Contradictory state injection in working memory</span>
                          </div>
                          <div className="flex items-center gap-2.5">
                            <span className="material-symbols-outlined text-accent-emerald text-[18px]">
                              check_circle
                            </span>
                            <span>Tracks hallucination recovery score in real-time</span>
                          </div>
                        </div>
                      </div>

                      <div className="col-span-7 bg-surface-raised rounded-lg border border-border-subtle p-5 font-code-md text-code-md">
                        <div className="flex items-center justify-between pb-3 mb-4 border-b border-border-subtle text-xs text-text-muted">
                          <span>memory_and_drift.py</span>
                          <span className="text-secondary">STATE MUTATOR &amp; DRIFT</span>
                        </div>
                        <pre className="text-text-primary leading-relaxed overflow-x-auto">
                          <code>
                            <span className="text-secondary">from</span> agentic_chaos.agents{' '}
                            <span className="text-secondary">import</span> MemoryCorruptionFault
                            {'\n'}
                            <span className="text-secondary">from</span> agentic_chaos.drift{' '}
                            <span className="text-secondary">import</span> DriftSnapshot, compare_snapshots
                            {'\n\n'}
                            <span className="text-text-muted"># 1. State decay across conversation steps</span>
                            {'\n'}
                            memory_fault = MemoryCorruptionFault({'\n'}    variable_name=
                            <span className="text-accent-cyan">"agent_scratchpad"</span>, mode=
                            <span className="text-secondary">"decay"</span>, rate=
                            <span className="text-warning-amber">0.25</span>
                            {'\n'}){'\n\n'}
                            <span className="text-text-muted"># 2. Prompt &amp; Model Drift Detection (v0.4.0)</span>
                            {'\n'}
                            baseline = DriftSnapshot(name=
                            <span className="text-accent-cyan">"analyst"</span>, prompt=
                            <span className="text-secondary">"reconcile"</span>, model=
                            <span className="text-secondary">"gpt-5-mini"</span>){'\n'}
                            report = compare_snapshots(baseline, current_snapshot)
                          </code>
                        </pre>
                      </div>
                    </div>
                  )}

                  {desktopTourTab === 3 && (
                    <div className="grid grid-cols-12 gap-10 items-center">
                      <div className="col-span-5 flex flex-col gap-6">
                        <span className="font-label-caps text-label-caps text-accent-emerald uppercase">
                          AUTOMATED CI/CD RELEASE POLICIES
                        </span>
                        <h3 className="font-headline-md text-headline-md text-text-primary">
                          Hard gates for pull requests and agent commits.
                        </h3>
                        <p className="font-body-md text-body-md text-text-secondary leading-relaxed">
                          Do not deploy agents that crash on 500ms jitter or exceed token limits during failover
                          retries. Enforce automated pass/fail thresholds in GitHub Actions.
                        </p>
                        <div className="flex flex-col gap-3 font-body-sm text-body-sm text-text-secondary">
                          <div className="flex items-center gap-2.5">
                            <span className="material-symbols-outlined text-accent-emerald text-[18px]">
                              check_circle
                            </span>
                            <span>Pass/Fail gate based on resilience quotient</span>
                          </div>
                          <div className="flex items-center gap-2.5">
                            <span className="material-symbols-outlined text-accent-emerald text-[18px]">
                              check_circle
                            </span>
                            <span>Maximum runaway cost &amp; loop count enforcement</span>
                          </div>
                          <div className="flex items-center gap-2.5">
                            <span className="material-symbols-outlined text-accent-emerald text-[18px]">
                              check_circle
                            </span>
                            <span>JUnit XML &amp; Markdown summaries for CI workflows</span>
                          </div>
                        </div>
                      </div>

                      <div className="col-span-7 bg-surface-raised rounded-lg border border-border-subtle p-5 font-code-md text-code-md">
                        <div className="flex items-center justify-between pb-3 mb-4 border-b border-border-subtle text-xs text-text-muted">
                          <span>ci-drift-gate.log</span>
                          <span className="text-accent-emerald font-semibold">GATE COMPLETE</span>
                        </div>
                        <pre className="text-text-primary leading-relaxed overflow-x-auto">
                          <code>
                            <span className="text-text-muted">
                              $ agentic-chaos drift compare baseline.json --output-file current.txt
                            </span>
                            {'\n\n'}
                            [DRIFT-CHECK] Comparing live run against v0.4.0 baseline...{'\n'}  - Prompt Drift:{' '}
                            <span className="text-accent-emerald">MATCHED (Hash 0x8f2a)</span>
                            {'\n'}  - Model Provider Fingerprint:{' '}
                            <span className="text-accent-emerald">fp-001 (Consistent)</span>
                            {'\n'}  - Output Distance Score:{' '}
                            <span className="text-accent-emerald">0.04 (Below threshold 0.15)</span>
                            {'\n\n'}
                            <span className="text-text-primary font-bold">RELEASE DECISION: PERMITTED</span>
                            {'\n'}
                            Exit Code: <span className="text-accent-emerald font-bold">0 (No Silent Drift)</span>{'\n'}
                            Events Recorded: <span className="text-text-primary">12 assertions passed in pytest</span>
                          </code>
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </section>

            {/* ARCHITECTURE & INTERCEPTOR SCHEMATIC */}
            <section className="w-full max-w-7xl mx-auto px-6 lg:px-12 py-20" id="architecture">
              <div className="text-center max-w-2xl mx-auto mb-16">
                <span className="font-label-caps text-label-caps text-accent-cyan tracking-widest uppercase">
                  ZERO-CODE INTEGRATION
                </span>
                <h2 className="font-headline-lg text-headline-lg text-text-primary tracking-tight mt-2">
                  The Non-Invasive Interceptor Architecture
                </h2>
                <p className="font-body-md text-body-md text-text-secondary mt-3">
                  AgenticChaos acts as an invisible proxy between your agent execution graph and the outside world.
                  No rewrites required.
                </p>
              </div>

              <div className="grid grid-cols-3 gap-6 relative">
                {/* Node 1 */}
                <div className="p-6 rounded-xl bg-surface-card border border-border-subtle flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <span className="w-8 h-8 rounded-lg bg-surface-raised flex items-center justify-center text-text-secondary border border-border-subtle font-code-md text-xs">
                        01
                      </span>
                      <span className="font-label-caps text-label-caps text-text-muted">HOST ENVIRONMENT</span>
                    </div>
                    <h4 className="font-headline-sm text-headline-sm text-text-primary mb-2">
                      Agent Execution Core
                    </h4>
                    <p className="font-body-sm text-body-sm text-text-secondary">
                      Your LangGraph, CrewAI, or bespoke Python runtime runs normally. AgenticChaos binds via
                      decorator or lightweight proxy wrapper.
                    </p>
                  </div>
                  <div className="mt-6 pt-4 border-t border-border-subtle/50 flex items-center gap-2 text-text-muted font-code-md text-xs">
                    <span className="w-2 h-2 rounded-full bg-accent-cyan" />
                    <span>Zero monkeypatching</span>
                  </div>
                </div>

                {/* Node 2 */}
                <div className="p-6 rounded-xl bg-surface-raised border border-accent-cyan/40 flex flex-col justify-between relative shadow-[0_0_30px_rgba(56,189,248,0.08)]">
                  <div className="absolute -top-3 right-4 px-2.5 py-0.5 rounded-full bg-accent-cyan text-surface-base font-label-caps text-[10px] font-bold tracking-wider uppercase">
                    CORE INTERCEPTOR
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <span className="w-8 h-8 rounded-lg bg-accent-cyan/10 flex items-center justify-center text-accent-cyan border border-accent-cyan/30 font-code-md text-xs">
                        02
                      </span>
                      <span className="font-label-caps text-label-caps text-accent-cyan">AGENTICCHAOS ENGINE</span>
                    </div>
                    <h4 className="font-headline-sm text-headline-sm text-text-primary mb-2">
                      Fault &amp; Drift Injector
                    </h4>
                    <p className="font-body-sm text-body-sm text-text-secondary">
                      Intercepts tool RPCs, vector queries, and LLM completions in real-time. Injects synthetic
                      latency, status codes, corrupted JSON, and state drift.
                    </p>
                  </div>
                  <div className="mt-6 pt-4 border-t border-border-subtle/50 flex items-center justify-between text-xs font-code-md">
                    <span className="text-accent-cyan">&lt; 0.2ms overhead</span>
                    <span className="text-text-muted">Deterministic PRNG</span>
                  </div>
                </div>

                {/* Node 3 */}
                <div className="p-6 rounded-xl bg-surface-card border border-border-subtle flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <span className="w-8 h-8 rounded-lg bg-surface-raised flex items-center justify-center text-text-secondary border border-border-subtle font-code-md text-xs">
                        03
                      </span>
                      <span className="font-label-caps text-label-caps text-text-muted">EXTERNAL INTERFACES</span>
                    </div>
                    <h4 className="font-headline-sm text-headline-sm text-text-primary mb-2">
                      Tools, APIs &amp; Models
                    </h4>
                    <p className="font-body-sm text-body-sm text-text-secondary">
                      OpenAI, Anthropic, local vLLM, custom SQL DBs, web browsing tools, and vector indexes receive
                      modulated traffic.
                    </p>
                  </div>
                  <div className="mt-6 pt-4 border-t border-border-subtle/50 flex items-center gap-2 text-text-muted font-code-md text-xs">
                    <span className="w-2 h-2 rounded-full bg-accent-emerald" />
                    <span>Verified resilience telemetry</span>
                  </div>
                </div>
              </div>
            </section>

            {/* QUICK-START CODE SECTION */}
            <section className="w-full max-w-7xl mx-auto px-6 lg:px-12 py-20 border-t border-border-subtle" id="docs">
              <div className="grid grid-cols-12 gap-12 items-center">
                <div className="col-span-5 flex flex-col gap-6">
                  <span className="font-label-caps text-label-caps text-accent-cyan tracking-widest uppercase">
                    EASY ADOPTION
                  </span>
                  <h2 className="font-headline-lg text-headline-lg text-text-primary tracking-tight">
                    Instrument in 3 lines.<br />Stress-test everywhere.
                  </h2>
                  <p className="font-body-md text-body-md text-text-secondary leading-relaxed">
                    AgenticChaos does not require external SaaS daemons or heavy proxies. Drop it into your existing
                    pytest or standalone test runner and instantly evaluate resilience.
                  </p>
                  <div className="flex flex-wrap gap-2 pt-2">
                    <span className="px-3 py-1 rounded bg-surface-card border border-border-subtle font-code-md text-code-md text-text-secondary hover:border-accent-cyan transition-colors cursor-default">
                      Pytest Ready
                    </span>
                    <span className="px-3 py-1 rounded bg-surface-card border border-border-subtle font-code-md text-code-md text-text-secondary hover:border-accent-cyan transition-colors cursor-default">
                      JSON Schema Mutator
                    </span>
                    <span className="px-3 py-1 rounded bg-surface-card border border-border-subtle font-code-md text-code-md text-text-secondary hover:border-accent-cyan transition-colors cursor-default">
                      Latency Spiker
                    </span>
                    <span className="px-3 py-1 rounded bg-surface-card border border-border-subtle font-code-md text-code-md text-text-secondary hover:border-accent-cyan transition-colors cursor-default">
                      CI/CD Gate
                    </span>
                  </div>
                </div>

                <div className="col-span-7">
                  <div className="rounded-xl border border-border-subtle bg-surface-card shadow-2xl overflow-hidden">
                    <div className="flex items-center justify-between px-5 py-3 border-b border-border-subtle bg-surface-raised">
                      <div className="flex items-center gap-4 font-code-md text-code-md">
                        <span
                          onClick={() => setDesktopCodeTab('py')}
                          className={`cursor-pointer ${
                            desktopCodeTab === 'py'
                              ? 'text-text-primary border-b border-accent-cyan pb-1'
                              : 'text-text-muted hover:text-text-secondary'
                          }`}
                        >
                          quickstart.py
                        </span>
                        <span
                          onClick={() => setDesktopCodeTab('yaml')}
                          className={`cursor-pointer ${
                            desktopCodeTab === 'yaml'
                              ? 'text-text-primary border-b border-accent-cyan pb-1'
                              : 'text-text-muted hover:text-text-secondary'
                          }`}
                        >
                          chaos.yaml
                        </span>
                      </div>
                      <div className="flex items-center gap-2 font-code-md text-xs text-text-muted">
                        <span className="w-2 h-2 rounded-full bg-accent-emerald" />
                        <span>Python 3.10+</span>
                      </div>
                    </div>

                    <div className="p-6 font-code-md text-code-md overflow-x-auto">
                      {desktopCodeTab === 'py' ? (
                        <pre className="text-text-primary leading-relaxed">
                          <code>
                            <span className="text-secondary">from</span> agentic_chaos.chaos{' '}
                            <span className="text-secondary">import</span> chaos_call, chaos_session, TokenTimeoutFault
                            {'\n'}
                            <span className="text-secondary">from</span> agentic_chaos.agents{' '}
                            <span className="text-secondary">import</span> ToolCallFailureFault, wrap_tool
                            {'\n\n'}
                            <span className="text-text-muted">
                              # 1. Wrap external tool with non-invasive interceptor
                            </span>
                            {'\n'}
                            search = wrap_tool(retriever.search, tool_name=
                            <span className="text-accent-cyan">"web_search"</span>)
                            {'\n\n'}
                            <span className="text-text-muted"># 2. Inject real-world flaky tool behavior and timeouts</span>
                            {'\n'}
                            with chaos_session([{'\n'}    ToolCallFailureFault(tool_name=
                            <span className="text-secondary">"web_search"</span>, timeout_seconds=
                            <span className="text-warning-amber">3.0</span>),{'\n'}    TokenTimeoutFault(hang_seconds=
                            <span className="text-warning-amber">2.0</span>)
                            {'\n'}]) as session:{'\n'}    try:{'\n'}        chunks = search(
                            <span className="text-secondary">"AAPL quarterly filing"</span>)
                            {'\n'}    except Exception:{'\n'}        chunks = []  # Fallback handles failure gracefully
                            {'\n\n'}
                            <span className="text-text-muted">
                              # 3. Inspect structured chaos telemetry and outcome
                            </span>
                            {'\n'}
                            print(
                            <span className="text-secondary">
                              f"Recorded Events: &#123;len(session.events)&#125;"
                            </span>
                            ){'\n'}
                            print(
                            <span className="text-secondary">
                              f"First Outcome:   &#123;session.events[0].outcome&#125;"
                            </span>
                            ){'\n'}
                            assert len(session.events) &gt; 0,{' '}
                            <span className="text-secondary">"Chaos events recorded"</span>
                          </code>
                        </pre>
                      ) : (
                        <pre className="text-text-primary leading-relaxed">
                          <code>
                            <span className="text-text-muted"># Run application under active chaos from CLI</span>
                            {'\n'}
                            <span className="text-accent-cyan">agentic-chaos</span> chaos run my_agent.py \{'\n'}
                            {'  '}<span className="text-secondary">--inject</span> token_timeout,rate_limit_storm,tool_failure \{'\n'}
                            {'  '}<span className="text-secondary">--save</span> chaos_report.json
                            {'\n\n'}
                            <span className="text-text-muted"># Snapshot and compare prompt &amp; model drift (v0.4.0)</span>
                            {'\n'}
                            <span className="text-accent-cyan">agentic-chaos</span> drift compare baseline.json \{'\n'}
                            {'  '}<span className="text-secondary">--prompt-file</span> prompt.txt \{'\n'}
                            {'  '}<span className="text-secondary">--output-file</span> current.txt \{'\n'}
                            {'  '}<span className="text-secondary">--save</span> drift_report.json
                          </code>
                        </pre>
                      )}
                    </div>

                    <div className="px-5 py-3 border-t border-border-subtle bg-surface-raised/80 flex items-center justify-between text-xs font-code-md text-text-muted">
                      <span className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan" />
                        Local runtime · Zero egress · Pure Python
                      </span>
                      <button
                        className="text-accent-cyan hover:text-text-primary transition-colors flex items-center gap-1 cursor-pointer"
                        onClick={handleDesktopCopySnippet}
                      >
                        <span className="material-symbols-outlined text-[14px]">
                          {desktopSnippetCopied ? 'check' : 'content_copy'}
                        </span>
                        <span>{desktopSnippetCopied ? 'Copied!' : 'Copy snippet'}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* AUDIENCE / PERSONA SECTION */}
            <section className="w-full max-w-7xl mx-auto px-6 lg:px-12 py-16" id="how-it-works">
              <div className="text-center max-w-xl mx-auto mb-12">
                <span className="font-label-caps text-label-caps text-accent-cyan tracking-widest uppercase">
                  WHO IT'S FOR
                </span>
                <h2 className="font-headline-md text-headline-md text-text-primary mt-2">
                  Engineered for builders of high-stakes AI
                </h2>
              </div>
              <div className="grid grid-cols-3 gap-6">
                <div className="p-6 rounded-xl bg-surface-card border border-border-subtle hover:border-border-strong transition-all flex flex-col justify-between">
                  <div>
                    <span className="material-symbols-outlined text-accent-cyan text-3xl mb-4">smart_toy</span>
                    <h3 className="font-headline-sm text-headline-sm text-text-primary mb-2">
                      Agent System Developers
                    </h3>
                    <p className="font-body-sm text-body-sm text-text-secondary leading-relaxed">
                      Stop guessing how multi-agent supervisor trees behave when an upstream sub-agent fails. Fix
                      brittle graph transitions during local iteration.
                    </p>
                  </div>
                  <div className="mt-6 pt-4 border-t border-border-subtle/50 text-xs font-code-md text-text-muted">
                    Used by core LLM engineers
                  </div>
                </div>

                <div className="p-6 rounded-xl bg-surface-card border border-border-subtle hover:border-border-strong transition-all flex flex-col justify-between">
                  <div>
                    <span className="material-symbols-outlined text-primary text-3xl mb-4">verified_user</span>
                    <h3 className="font-headline-sm text-headline-sm text-text-primary mb-2">
                      QA &amp; Reliability Engineers
                    </h3>
                    <p className="font-body-sm text-body-sm text-text-secondary leading-relaxed">
                      Replace brittle end-to-end prompt assertions with deterministic fault schedules. Quantify token
                      burn ratios during error retries.
                    </p>
                  </div>
                  <div className="mt-6 pt-4 border-t border-border-subtle/50 text-xs font-code-md text-text-muted">
                    CI/CD gate integration
                  </div>
                </div>

                <div className="p-6 rounded-xl bg-surface-card border border-border-subtle hover:border-border-strong transition-all flex flex-col justify-between">
                  <div>
                    <span className="material-symbols-outlined text-warning-amber text-3xl mb-4">security</span>
                    <h3 className="font-headline-sm text-headline-sm text-text-primary mb-2">
                      Security &amp; Red Teams
                    </h3>
                    <p className="font-body-sm text-body-sm text-text-secondary leading-relaxed">
                      Simulate malicious tool injection, memory poisoning, and prompt leakage under stressed state
                      conditions before deploying to untrusted users.
                    </p>
                  </div>
                  <div className="mt-6 pt-4 border-t border-border-subtle/50 text-xs font-code-md text-text-muted">
                    Safety &amp; adversarial verification
                  </div>
                </div>
              </div>
            </section>

            {/* BOTTOM CTA BANNER */}
            <section className="w-full max-w-7xl mx-auto px-6 lg:px-12 py-16">
              <div className="relative rounded-2xl border border-border-subtle bg-surface-card overflow-hidden p-8 lg:p-14 shadow-2xl">
                <div className="absolute -right-20 -bottom-20 w-96 h-96 bg-accent-cyan/10 rounded-full blur-3xl pointer-events-none" />
                <div className="grid grid-cols-12 gap-10 items-center relative z-10">
                  <div className="col-span-7 flex flex-col items-start gap-4">
                    <div className="flex items-center gap-2 font-code-md text-xs text-text-muted uppercase tracking-wider">
                      <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan" />
                      <span>OPEN SOURCE · MIT LICENSE</span>
                    </div>
                    <h2 className="font-headline-lg text-headline-lg text-text-primary tracking-tight">
                      Your agent data stays yours.
                    </h2>
                    <p className="font-body-md text-body-md text-text-secondary max-w-lg leading-relaxed">
                      No mandatory cloud account. No hosted backend. No telemetry egress required just to inspect or
                      stress-test your run. Start locally in 60 seconds.
                    </p>
                    <div className="flex flex-wrap items-center gap-4 pt-4">
                      <a
                        className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-text-primary hover:bg-white text-surface-base font-headline-sm text-headline-sm transition-all shadow-md"
                        href="https://github.com/DeepAgentLabs/agentic-chaos"
                        rel="noopener noreferrer"
                        target="_blank"
                      >
                        <span>View on GitHub</span>
                        <span className="material-symbols-outlined text-[16px]">north_east</span>
                      </a>
                      <a
                        className="inline-flex items-center gap-2 px-5 py-3 rounded-lg bg-surface-raised border border-border-subtle hover:border-border-strong text-text-primary font-headline-sm text-headline-sm transition-all"
                        href="#docs"
                      >
                        <span>Read the docs</span>
                      </a>
                    </div>
                  </div>

                  <div className="col-span-5 w-full">
                    <div className="rounded-xl border border-border-subtle bg-surface-raised p-5 font-code-md text-code-md shadow-xl">
                      <div className="flex items-center justify-between pb-3 mb-3 border-b border-border-subtle/60 text-xs text-text-muted">
                        <div className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-error-rose/50" />
                          <span className="w-2 h-2 rounded-full bg-warning-amber/50" />
                          <span className="w-2 h-2 rounded-full bg-accent-emerald/50" />
                        </div>
                        <span>terminal</span>
                      </div>
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center gap-2 text-text-secondary">
                          <span className="text-accent-cyan">$</span>
                          <span>pip install agentic-chaos</span>
                        </div>
                        <div className="flex items-center gap-2 text-text-secondary">
                          <span className="text-accent-cyan">$</span>
                          <span>agentic-chaos inspect trace.json</span>
                        </div>
                        <div className="pt-3 pb-2 text-xs font-mono text-text-muted border-t border-border-subtle/40 mt-1 flex flex-col gap-1">
                          <div className="flex justify-between">
                            <span>Run Summary</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Status</span>
                            <span className="text-accent-emerald font-semibold">succeeded</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Spans</span>
                            <span className="text-text-primary">8</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Tokens</span>
                            <span className="text-text-primary">94</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Latency</span>
                            <span className="text-text-primary">4.8 ms</span>
                          </div>
                        </div>
                        <div className="pt-2 text-xs border-t border-border-subtle/40 flex flex-col gap-1">
                          <div className="text-text-secondary">
                            <span className="text-accent-cyan">$</span> agentic-chaos gate release.json
                          </div>
                          <div className="text-accent-emerald flex items-center gap-1 font-semibold">
                            <span className="material-symbols-outlined text-[14px]">check</span>
                            <span>Release gate passed. Ready for prod.</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </main>

        {/* DESKTOP FOOTER */}
        <footer className="w-full bg-surface-raised mt-space-3xl">
          <div className="max-w-7xl mx-auto px-6 lg:px-12 py-space-2xl">
            <div className="flex justify-between items-center gap-space-xl pb-space-xl">
              <div className="flex flex-col gap-space-xs">
                <div className="flex items-center gap-space-sm">
                  <img alt="AgenticChaos Logo" className="h-6 w-auto object-contain" src={logoUrl} />
                  <span className="font-headline-sm text-headline-sm text-text-primary">AgenticChaos</span>
                </div>
                <p className="font-body-sm text-body-sm text-text-muted max-w-sm">
                  Deterministic multi-agent failure injection, safety verification, and adaptive resilience testing
                  by DeepAgentLabs.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-space-lg font-code-md text-code-md">
                <a
                  className="text-on-surface-variant hover:text-accent-cyan transition-colors"
                  href="https://github.com/DeepAgentLabs/agentic-chaos"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  GitHub
                </a>
                <a
                  className="text-on-surface-variant hover:text-accent-cyan transition-colors"
                  href="https://pypi.org/project/agentic-chaos/"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  PyPI
                </a>
                <a className="text-on-surface-variant hover:text-accent-cyan transition-colors" href="#docs">
                  Docs
                </a>
                <a
                  className="text-on-surface-variant hover:text-accent-cyan transition-colors"
                  href="https://opensource.org/licenses/MIT"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  License MIT
                </a>
                <a
                  className="text-accent-cyan hover:text-primary transition-colors flex items-center gap-space-xxs"
                  href="#"
                >
                  <span>Back to top</span>
                  <span className="material-symbols-outlined text-[14px]">arrow_upward</span>
                </a>
              </div>
            </div>
            <div className="flex justify-between items-center gap-space-md pt-space-lg font-code-md text-code-md text-text-muted">
              <p>© 2025 DeepAgentLabs. Engineered for AI Systems &amp; Runtime Engineers.</p>
              <div className="flex items-center gap-space-sm">
                <span className="inline-block w-2 h-2 rounded-full bg-accent-emerald" />
                <span className="font-label-caps text-label-caps text-text-secondary">CORE ENGINE: OPERATIONAL</span>
              </div>
            </div>
          </div>
        </footer>
      </div>

      {/* ========================================================================= */}
      {/* MOBILE VIEW (Visible on mobile/tablet viewports below 1024px: lg:hidden)   */}
      {/* ========================================================================= */}
      <div className="block lg:hidden w-full font-body-md text-on-surface flex flex-col min-h-screen">
        {/* MOBILE HEADER */}
        <header className="fixed top-0 inset-x-0 z-50 bg-surface-base/80 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.4)] pt-safe">
          <div className="h-16 px-gutter-mobile flex items-center justify-between gap-space-sm">
            <div className="flex items-center gap-space-sm min-w-0">
              <img
                alt="AgenticChaos Logo"
                className="h-8 w-auto object-contain shrink-0"
                src={logoUrl}
              />
              <div className="flex flex-col min-w-0">
                <div className="flex items-center gap-space-xs">
                  <span className="font-headline-sm text-headline-sm text-text-primary tracking-tight font-semibold truncate">
                    AgenticChaos
                  </span>
                  <span className="font-label-caps text-label-caps uppercase bg-surface-overlay text-accent-cyan px-1.5 py-0.5 rounded-DEFAULT shrink-0">
                    v0.9
                  </span>
                </div>
                <span className="font-code-md text-code-md text-text-muted truncate">Overview</span>
              </div>
            </div>

            <div className="flex items-center gap-space-xs shrink-0">
              <a
                aria-label="GitHub Repository"
                className="w-11 h-11 flex items-center justify-center text-text-secondary hover:text-text-primary transition-colors rounded-DEFAULT"
                href="https://github.com/DeepAgentLabs/AgenticChaos"
                rel="noreferrer"
                target="_blank"
              >
                <svg aria-hidden="true" className="w-5 h-5 fill-current" viewBox="0 0 24 24">
                  <path
                    clipRule="evenodd"
                    d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                    fillRule="evenodd"
                  />
                </svg>
              </a>
              <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center shrink-0">
                <span className="material-symbols-outlined text-on-primary text-[18px]">person</span>
              </div>
            </div>
          </div>
        </header>

        {/* MOBILE MAIN CONTENT */}
        <main className="flex flex-col relative w-full pt-16 bg-surface">
          <div className="flex flex-col w-full">
            {/* Visual Ambience */}
            <div className="relative w-full overflow-hidden px-gutter-mobile pt-space-md pb-space-2xl">
              <div className="absolute -top-12 left-1/2 -translate-x-1/2 w-72 h-72 bg-secondary-container/10 rounded-full blur-3xl pointer-events-none" />
              <div className="absolute top-48 right-0 w-48 h-48 bg-primary-container/10 rounded-full blur-2xl pointer-events-none" />

              {/* 1. Mobile Hero Content */}
              <div className="relative flex flex-col items-start gap-space-md">
                <div className="inline-flex items-center gap-space-xs px-2.5 py-1 rounded-full bg-surface-overlay text-text-secondary">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald animate-pulse" />
                  <span className="font-label-caps text-label-caps tracking-wider text-accent-cyan uppercase">
                    Open-source · Fault-injection
                  </span>
                </div>

                <h1 className="font-headline-lg-mobile text-headline-lg-mobile text-text-primary tracking-tight">
                  Break agentic AI <br />
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan via-primary to-secondary">
                    before users do.
                  </span>
                </h1>

                <p className="font-body-md text-body-md text-text-secondary">
                  Resilience evaluation &amp; deterministic chaos testing for multi-agent LLM systems, pipelines,
                  and autonomous graphs.
                </p>

                {/* Terminal Quick-Install Command */}
                <div
                  className="w-full flex items-center justify-between px-space-md py-space-xs rounded-lg bg-surface-card text-text-primary shadow-sm"
                  onClick={handleMobileCopyPip}
                >
                  <div className="flex items-center gap-space-xs min-w-0">
                    <span className="font-code-md text-code-md text-accent-cyan shrink-0">$</span>
                    <code className="font-code-md text-code-md text-text-primary truncate">
                      {mobilePipCopied ? 'Copied to clipboard!' : 'pip install agentic-chaos'}
                    </code>
                  </div>
                  <button
                    aria-label="Copy Command"
                    className="flex items-center justify-center p-1 rounded hover:bg-surface-overlay transition-colors text-text-secondary active:scale-95"
                  >
                    <span
                      className={`material-symbols-outlined text-[16px] ${
                        mobilePipCopied ? 'text-accent-emerald' : ''
                      }`}
                    >
                      {mobilePipCopied ? 'done' : 'content_copy'}
                    </span>
                  </button>
                </div>

                {/* CTA Buttons */}
                <div className="w-full flex flex-col gap-space-xs pt-space-xs">
                  <a
                    className="w-full flex items-center justify-center gap-space-xs py-space-sm px-space-md rounded-lg bg-primary-container text-surface-base font-headline-sm text-headline-sm hover:brightness-110 active:scale-[0.99] transition-all shadow-md"
                    href="#mobile-interactive-demo"
                  >
                    <span>Explore Live Chaos Run</span>
                    <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                  </a>
                  <a
                    className="w-full flex items-center justify-center gap-space-xs py-space-sm px-space-md rounded-lg bg-surface-card text-text-primary font-headline-sm text-headline-sm hover:bg-surface-overlay transition-all"
                    href="#mobile-quickstart-snippet"
                  >
                    <span className="material-symbols-outlined text-[18px] text-text-secondary">menu_book</span>
                    <span>View Documentation</span>
                  </a>
                </div>

                {/* Quick Metrics Strip */}
                <div className="w-full grid grid-cols-3 gap-space-xs pt-space-xs">
                  <div className="flex flex-col p-2.5 rounded-lg bg-surface-card">
                    <span className="font-headline-sm text-headline-sm text-text-primary font-semibold">100%</span>
                    <span className="font-label-caps text-label-caps text-text-muted uppercase">Deterministic</span>
                  </div>
                  <div className="flex flex-col p-2.5 rounded-lg bg-surface-card">
                    <span className="font-headline-sm text-headline-sm text-accent-cyan font-semibold">94/100</span>
                    <span className="font-label-caps text-label-caps text-text-muted uppercase">Health Index</span>
                  </div>
                  <div className="flex flex-col p-2.5 rounded-lg bg-surface-card">
                    <span className="font-headline-sm text-headline-sm text-tertiary font-semibold">0</span>
                    <span className="font-label-caps text-label-caps text-text-muted uppercase">Cloud Deps</span>
                  </div>
                </div>

                {/* Live Trace Inspector Card */}
                <div
                  className="w-full rounded-xl bg-surface-card overflow-hidden shadow-xl mt-space-xs"
                  id="mobile-interactive-demo"
                >
                  <div className="flex items-center justify-between px-space-md py-2.5 bg-surface-raised">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-error-rose/70" />
                      <span className="w-2.5 h-2.5 rounded-full bg-warning-amber/70" />
                      <span className="w-2.5 h-2.5 rounded-full bg-accent-emerald/70" />
                      <span className="font-code-md text-code-md text-text-muted ml-2 truncate">
                        chaos-run_09f.json
                      </span>
                    </div>
                    <span className="inline-flex items-center gap-1 font-label-caps text-label-caps uppercase text-accent-cyan px-2 py-0.5 rounded bg-surface-overlay">
                      <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-pulse" />
                      LIVE AUDIT
                    </span>
                  </div>

                  <div className="flex flex-col p-space-sm gap-2">
                    {/* Step 1 */}
                    <div className="flex items-center justify-between p-2 rounded-lg bg-surface-raised/70">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="flex items-center justify-center w-6 h-6 rounded bg-surface-overlay font-code-md text-code-md text-text-secondary shrink-0">
                          01
                        </span>
                        <div className="flex flex-col min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-code-md text-code-md text-text-primary font-medium">
                              SUPERVISOR
                            </span>
                            <span className="font-code-md text-code-md text-text-muted truncate">
                              Plan &amp; Delegate
                            </span>
                          </div>
                          <span className="font-label-caps text-label-caps text-accent-emerald">State validated</span>
                        </div>
                      </div>
                      <span className="font-code-md text-code-md text-text-muted shrink-0">1.2ms</span>
                    </div>

                    {/* Step 2 */}
                    <div className="flex items-center justify-between p-2 rounded-lg bg-surface-overlay">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="flex items-center justify-center w-6 h-6 rounded bg-error-container text-on-error-container font-code-md text-code-md font-medium shrink-0">
                          02
                        </span>
                        <div className="flex flex-col min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-code-md text-code-md text-error font-medium">EXTERNAL_API</span>
                            <span className="font-label-caps text-label-caps px-1 rounded bg-error-container text-on-error-container">
                              FAULT: 504 TIMEOUT
                            </span>
                          </div>
                          <span className="font-label-caps text-label-caps text-warning-amber truncate">
                            Injected 3500ms jitter
                          </span>
                        </div>
                      </div>
                      <span className="font-code-md text-code-md text-error shrink-0">3.5s</span>
                    </div>

                    {/* Step 3 */}
                    <div className="flex items-center justify-between p-2 rounded-lg bg-surface-raised/70">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="flex items-center justify-center w-6 h-6 rounded bg-surface-overlay font-code-md text-code-md text-text-secondary shrink-0">
                          03
                        </span>
                        <div className="flex flex-col min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-code-md text-code-md text-text-primary font-medium">
                              FALLBACK_AGENT
                            </span>
                            <span className="font-code-md text-code-md text-tertiary truncate">
                              Cached Vector Store
                            </span>
                          </div>
                          <span className="font-label-caps text-label-caps text-accent-emerald">
                            Self-healing invoked
                          </span>
                        </div>
                      </div>
                      <span className="font-code-md text-code-md text-text-muted shrink-0">4.1ms</span>
                    </div>

                    {/* Step 4 */}
                    <div className="flex items-center justify-between p-2 rounded-lg bg-surface-raised/70">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="flex items-center justify-center w-6 h-6 rounded bg-surface-overlay font-code-md text-code-md text-text-secondary shrink-0">
                          04
                        </span>
                        <div className="flex flex-col min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-code-md text-code-md text-text-primary font-medium">
                              VERIFIER
                            </span>
                            <span className="font-code-md text-code-md text-text-muted truncate">
                              Deterministic Match
                            </span>
                          </div>
                          <span className="font-label-caps text-label-caps text-accent-emerald">
                            No hallucination detected
                          </span>
                        </div>
                      </div>
                      <span className="font-code-md text-code-md text-text-muted shrink-0">0.9ms</span>
                    </div>
                  </div>

                  {/* Ribbon */}
                  <div className="flex items-center justify-between px-space-md py-space-sm bg-surface-raised">
                    <div className="flex flex-col">
                      <span className="font-label-caps text-label-caps text-text-muted uppercase">
                        RESILIENCE SCORE
                      </span>
                      <span className="font-headline-sm text-headline-sm font-semibold text-accent-emerald">
                        94.2% Passed
                      </span>
                    </div>
                    <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-accent-emerald/15 text-accent-emerald">
                      <span className="material-symbols-outlined text-[16px]">check_circle</span>
                      <span className="font-label-caps text-label-caps uppercase font-semibold">GATE: READY</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 2. Framework Ecosystem (Horizontal Capsule Rail) */}
            <div className="w-full flex flex-col gap-space-xs py-space-md bg-surface-raised">
              <div className="px-gutter-mobile flex items-center justify-between">
                <span className="font-label-caps text-label-caps uppercase tracking-wider text-text-muted">
                  NATIVE INTEGRATION SUPPORT
                </span>
                <span className="font-code-md text-code-md text-accent-cyan">5 CONNECTORS</span>
              </div>
              <div className="flex overflow-x-auto gap-space-xs px-gutter-mobile no-scrollbar py-1">
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-card text-text-primary shrink-0">
                  <span className="w-2 h-2 rounded-full bg-accent-cyan" />
                  <span className="font-code-md text-code-md font-medium">LangGraph</span>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-card text-text-primary shrink-0">
                  <span className="w-2 h-2 rounded-full bg-secondary" />
                  <span className="font-code-md text-code-md font-medium">AutoGen</span>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-card text-text-primary shrink-0">
                  <span className="w-2 h-2 rounded-full bg-tertiary" />
                  <span className="font-code-md text-code-md font-medium">LlamaIndex</span>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-card text-text-primary shrink-0">
                  <span className="w-2 h-2 rounded-full bg-primary" />
                  <span className="font-code-md text-code-md font-medium">CrewAI</span>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-card text-text-primary shrink-0">
                  <span className="w-2 h-2 rounded-full bg-warning-amber" />
                  <span className="font-code-md text-code-md font-medium">Model Context Protocol</span>
                </div>
              </div>
            </div>

            {/* 3. Failure Matrix Section */}
            <div className="flex flex-col px-gutter-mobile py-space-xl gap-space-lg" id="mobile-failure-matrix">
              <div className="flex flex-col gap-space-xs">
                <div className="flex items-center gap-space-xs">
                  <span className="font-label-caps text-label-caps text-accent-cyan uppercase">FAILURE MATRIX</span>
                </div>
                <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-text-primary tracking-tight">
                  Production multi-agent runs fail in silent ways.
                </h2>
                <p className="font-body-md text-body-md text-text-secondary">
                  Standard unit tests miss cyclic deadlocks and context drift. Inject chaos directly into your graph
                  edges to uncover brittle architectures.
                </p>
              </div>

              <div className="flex flex-col gap-space-sm">
                {/* Mode 01 */}
                <div className="p-space-md rounded-xl bg-surface-card flex flex-col gap-space-xs">
                  <div className="flex items-center justify-between">
                    <div className="w-8 h-8 rounded-lg bg-surface-overlay flex items-center justify-center text-accent-cyan">
                      <span className="material-symbols-outlined text-[20px]">bolt</span>
                    </div>
                    <span className="font-code-md text-code-md text-text-muted">MODE 01</span>
                  </div>
                  <h3 className="font-headline-sm text-headline-sm text-text-primary font-medium">
                    Flaky External Tool Invocations
                  </h3>
                  <p className="font-body-sm text-body-sm text-text-secondary">
                    Simulate intermittent 429 rate limits, malformed JSON schemas, and arbitrary 2s to 12s latency
                    spikes across upstream REST tools.
                  </p>
                  <div className="flex items-center gap-1.5 pt-space-xs text-accent-cyan">
                    <span className="font-label-caps text-label-caps uppercase">INSPECTION TRACE</span>
                    <span className="material-symbols-outlined text-[14px]">chevron_right</span>
                  </div>
                </div>

                {/* Mode 02 */}
                <div className="p-space-md rounded-xl bg-surface-card flex flex-col gap-space-xs">
                  <div className="flex items-center justify-between">
                    <div className="w-8 h-8 rounded-lg bg-surface-overlay flex items-center justify-center text-warning-amber">
                      <span className="material-symbols-outlined text-[20px]">memory</span>
                    </div>
                    <span className="font-code-md text-code-md text-text-muted">MODE 02</span>
                  </div>
                  <h3 className="font-headline-sm text-headline-sm text-text-primary font-medium">
                    Context Window Poisoning &amp; Drift
                  </h3>
                  <p className="font-body-sm text-body-sm text-text-secondary">
                    Inject adversarial prompt noise or token-truncation artifacts into sub-agent memory buffers to
                    verify context degradation boundaries.
                  </p>
                  <div className="flex items-center gap-1.5 pt-space-xs text-warning-amber">
                    <span className="font-label-caps text-label-caps uppercase">INSPECTION TRACE</span>
                    <span className="material-symbols-outlined text-[14px]">chevron_right</span>
                  </div>
                </div>

                {/* Mode 03 */}
                <div className="p-space-md rounded-xl bg-surface-card flex flex-col gap-space-xs">
                  <div className="flex items-center justify-between">
                    <div className="w-8 h-8 rounded-lg bg-surface-overlay flex items-center justify-center text-error">
                      <span className="material-symbols-outlined text-[20px]">call_split</span>
                    </div>
                    <span className="font-code-md text-code-md text-text-muted">MODE 03</span>
                  </div>
                  <h3 className="font-headline-sm text-headline-sm text-text-primary font-medium">
                    Cascading Delegation Loops
                  </h3>
                  <p className="font-body-sm text-body-sm text-text-secondary">
                    Force circular handoffs between research, math, and planner sub-agents to stress-test your
                    system's global recursion and token caps.
                  </p>
                  <div className="flex items-center gap-1.5 pt-space-xs text-error">
                    <span className="font-label-caps text-label-caps uppercase">INSPECTION TRACE</span>
                    <span className="material-symbols-outlined text-[14px]">chevron_right</span>
                  </div>
                </div>

                {/* Mode 04 */}
                <div className="p-space-md rounded-xl bg-surface-card flex flex-col gap-space-xs">
                  <div className="flex items-center justify-between">
                    <div className="w-8 h-8 rounded-lg bg-surface-overlay flex items-center justify-center text-tertiary">
                      <span className="material-symbols-outlined text-[20px]">verified_user</span>
                    </div>
                    <span className="font-code-md text-code-md text-text-muted">MODE 04</span>
                  </div>
                  <h3 className="font-headline-sm text-headline-sm text-text-primary font-medium">
                    Brittle Fallback Regressions
                  </h3>
                  <p className="font-body-sm text-body-sm text-text-secondary">
                    Automatically evaluate whether fallback mechanisms degrade gracefully or introduce security
                    regressions and ungrounded statements.
                  </p>
                  <div className="flex items-center gap-1.5 pt-space-xs text-tertiary">
                    <span className="font-label-caps text-label-caps uppercase">INSPECTION TRACE</span>
                    <span className="material-symbols-outlined text-[14px]">chevron_right</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 4. Interactive Product Tour */}
            <div className="flex flex-col px-gutter-mobile py-space-xl bg-surface-raised gap-space-lg" id="mobile-tour">
              <div className="flex flex-col gap-space-xs">
                <span className="font-label-caps text-label-caps text-accent-cyan uppercase">
                  INTERACTIVE RESILIENCE TOUR
                </span>
                <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-text-primary tracking-tight">
                  Inject. Corrupt. Score.
                </h2>
                <p className="font-body-md text-body-md text-text-secondary">
                  Step through the deterministic pipeline used by high-assurance AI agents before hitting staging
                  environments.
                </p>
              </div>

              <div className="flex flex-col gap-space-sm">
                <div className="flex rounded-lg bg-surface-base p-1">
                  <button
                    onClick={() => setMobileTourTab('inject')}
                    className={`flex-1 py-2 px-1 text-center font-label-caps text-label-caps uppercase rounded transition-all cursor-pointer ${
                      mobileTourTab === 'inject'
                        ? 'text-accent-cyan bg-surface-overlay'
                        : 'text-text-muted hover:text-text-primary'
                    }`}
                  >
                    01 INJECT
                  </button>
                  <button
                    onClick={() => setMobileTourTab('corrupt')}
                    className={`flex-1 py-2 px-1 text-center font-label-caps text-label-caps uppercase rounded transition-all cursor-pointer ${
                      mobileTourTab === 'corrupt'
                        ? 'text-accent-cyan bg-surface-overlay'
                        : 'text-text-muted hover:text-text-primary'
                    }`}
                  >
                    02 CORRUPT
                  </button>
                  <button
                    onClick={() => setMobileTourTab('score')}
                    className={`flex-1 py-2 px-1 text-center font-label-caps text-label-caps uppercase rounded transition-all cursor-pointer ${
                      mobileTourTab === 'score'
                        ? 'text-accent-cyan bg-surface-overlay'
                        : 'text-text-muted hover:text-text-primary'
                    }`}
                  >
                    03 SCORE
                  </button>
                </div>

                {mobileTourTab === 'inject' && (
                  <div className="flex flex-col p-space-md rounded-xl bg-surface-card gap-space-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-label-caps text-label-caps text-accent-cyan uppercase">
                        ATTACK VECTOR DISCOVERY
                      </span>
                      <span className="font-code-md text-code-md text-text-muted">Target: langgraph_router</span>
                    </div>
                    <p className="font-body-sm text-body-sm text-text-secondary">
                      Declare failure policies declaratively in YAML or Python fixtures. Chaos hooks automatically
                      attach to model invocations without rewriting pipeline logic.
                    </p>
                    <div className="rounded-lg bg-surface-base p-3 flex flex-col gap-1 font-code-md text-code-md text-text-secondary">
                      <div className="text-text-muted"># chaos_spec.yaml</div>
                      <div>
                        <span className="text-secondary">strategy</span>: <span className="text-text-primary">stochastic_latency</span>
                      </div>
                      <div>
                        <span className="text-secondary">probability</span>: <span className="text-accent-cyan">0.45</span>
                      </div>
                      <div>
                        <span className="text-secondary">target_nodes</span>: [<span className="text-text-primary">"retrieval_agent"</span>]
                      </div>
                    </div>
                  </div>
                )}

                {mobileTourTab === 'corrupt' && (
                  <div className="flex flex-col p-space-md rounded-xl bg-surface-card gap-space-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-label-caps text-label-caps text-warning-amber uppercase">
                        PAYLOAD TAMPERING
                      </span>
                      <span className="font-code-md text-code-md text-text-muted">Target: vector_memory</span>
                    </div>
                    <p className="font-body-sm text-body-sm text-text-secondary">
                      Simulate prompt injections, corrupted chunk context, and out-of-order agent messaging at runtime
                      to test fallback guards.
                    </p>
                    <div className="rounded-lg bg-surface-base p-3 flex flex-col gap-1 font-code-md text-code-md text-text-secondary">
                      <div className="text-text-muted"># injection_hook.py</div>
                      <div>
                        <span className="text-secondary">corrupter</span> = <span className="text-text-primary">FuzzEngine()</span>
                      </div>
                      <div>
                        corrupter.<span className="text-accent-cyan">inject_drift</span>(layer=<span className="text-text-primary">"handoff"</span>)
                      </div>
                      <div className="text-error">! Corrupted semantic embedding injected</div>
                    </div>
                  </div>
                )}

                {mobileTourTab === 'score' && (
                  <div className="flex flex-col p-space-md rounded-xl bg-surface-card gap-space-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-label-caps text-label-caps text-tertiary uppercase">
                        DETERMINISTIC EVALUATION
                      </span>
                      <span className="font-code-md text-code-md text-text-muted">Gate Verdict</span>
                    </div>
                    <p className="font-body-sm text-body-sm text-text-secondary">
                      Grade the system against deterministic rubrics, hallucination tolerance, and recovery time
                      objectives (RTO). Block deployments via GitHub Action exit codes.
                    </p>
                    <div className="rounded-lg bg-surface-base p-3 flex flex-col gap-1.5">
                      <div className="flex justify-between items-center text-body-sm">
                        <span className="text-text-primary">Fallback Pass Rate</span>
                        <span className="text-accent-emerald font-code-md">98.4%</span>
                      </div>
                      <div className="w-full bg-surface-overlay h-1.5 rounded-full overflow-hidden">
                        <div className="bg-accent-emerald h-full w-[98%]" />
                      </div>
                      <div className="flex justify-between items-center text-body-sm pt-1">
                        <span className="text-text-primary">Recovery Latency P99</span>
                        <span className="text-accent-cyan font-code-md">240ms</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* 5. 60-Second Quick Start Snippet */}
            <div className="flex flex-col px-gutter-mobile py-space-xl gap-space-md" id="mobile-quickstart-snippet">
              <div className="flex flex-col gap-space-xs">
                <span className="font-label-caps text-label-caps text-accent-cyan uppercase">
                  DEVELOPER ERGONOMICS
                </span>
                <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-text-primary tracking-tight">
                  Instrument once. Run locally.
                </h2>
                <p className="font-body-md text-body-md text-text-secondary">
                  Zero SaaS accounts or telemetry uploads required. Your agent graphs and prompts stay entirely on
                  your local machine.
                </p>
              </div>

              <div className="w-full rounded-xl bg-surface-card overflow-hidden shadow-md">
                <div className="flex items-center justify-between px-space-md py-2 bg-surface-raised">
                  <span className="font-code-md text-code-md text-text-muted">test_resilience.py</span>
                  <button
                    onClick={handleMobileCopySnippet}
                    className="font-label-caps text-label-caps uppercase text-accent-cyan hover:underline flex items-center gap-1 cursor-pointer"
                  >
                    <span>{mobileCodeCopied ? 'COPIED!' : 'COPY'}</span>
                  </button>
                </div>
                <div className="p-space-md bg-surface-base overflow-x-auto">
                  <pre className="font-code-md text-code-md leading-relaxed text-text-secondary">
                    <code>
                      <span className="text-secondary">from</span> agentic_chaos{' '}
                      <span className="text-secondary">import</span> ChaosSession, faults
                      {'\n\n'}
                      <span className="text-text-muted"># 1. Wrap your LangGraph or AutoGen agent</span>
                      {'\n'}
                      session = ChaosSession(target=supervisor_agent)
                      {'\n\n'}
                      <span className="text-text-muted"># 2. Inject arbitrary network delay and tool failures</span>
                      {'\n'}
                      session.apply({'\n'}    faults.ToolTimeout(target=
                      <span className="text-text-primary">"web_search"</span>, delay_ms=
                      <span className="text-accent-cyan">4000</span>),{'\n'}    faults.DriftContext(drop_ratio=
                      <span className="text-accent-cyan">0.2</span>){'\n'}){'\n\n'}
                      <span className="text-text-muted"># 3. Assert self-healing and recovery</span>
                      {'\n'}
                      verdict = session.run(prompt=
                      <span className="text-text-primary">"Reconcile invoice #889"</span>)
                      {'\n'}
                      <span className="text-secondary">assert</span> verdict.recovered =={' '}
                      <span className="text-tertiary">True</span>
                      {'\n'}
                      <span className="text-secondary">assert</span> verdict.score &gt;={' '}
                      <span className="text-accent-cyan">0.90</span>
                    </code>
                  </pre>
                </div>
                <div className="px-space-md py-2.5 bg-surface-raised flex items-center justify-between">
                  <span className="font-code-md text-code-md text-text-muted">Ready for CI / GitHub Actions</span>
                  <span className="material-symbols-outlined text-[16px] text-accent-emerald">terminal</span>
                </div>
              </div>
            </div>

            {/* 6. Bottom Showcase & Open-Source Guarantee Card */}
            <div className="px-gutter-mobile pb-space-lg">
              <div className="flex flex-col p-space-lg rounded-xl bg-surface-card gap-space-md relative overflow-hidden shadow-xl">
                <div className="absolute -right-10 -bottom-10 w-44 h-44 bg-accent-cyan/10 rounded-full blur-2xl pointer-events-none" />
                <div className="flex flex-col gap-space-xs">
                  <span className="font-label-caps text-label-caps text-accent-cyan uppercase tracking-wider">
                    OPEN SOURCE · MIT LICENSE
                  </span>
                  <h3 className="font-headline-lg-mobile text-headline-lg-mobile text-text-primary tracking-tight">
                    Your agent data stays in your VPC.
                  </h3>
                  <p className="font-body-md text-body-md text-text-secondary">
                    No mandatory accounts. No hosted platform lock-in. No egress tokens sent over the wire. Run locally
                    during development and enforce in pull requests.
                  </p>
                </div>

                <div className="flex flex-col gap-space-xs pt-space-xs">
                  <a
                    className="w-full flex items-center justify-center gap-space-xs py-space-sm px-space-md rounded-lg bg-primary-container text-surface-base font-headline-sm text-headline-sm hover:brightness-110 active:scale-[0.99] transition-all"
                    href="https://github.com/DeepAgentLabs/AgenticChaos"
                    rel="noreferrer"
                    target="_blank"
                  >
                    <svg aria-hidden="true" className="w-5 h-5 fill-current" viewBox="0 0 24 24">
                      <path
                        clipRule="evenodd"
                        d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                        fillRule="evenodd"
                      />
                    </svg>
                    <span>Star on GitHub</span>
                  </a>
                  <a
                    className="w-full flex items-center justify-center gap-space-xs py-space-sm px-space-md rounded-lg bg-surface-raised text-text-primary font-headline-sm text-headline-sm hover:bg-surface-overlay transition-all"
                    href="#mobile-failure-matrix"
                  >
                    <span>Explore Scenarios Library</span>
                  </a>
                </div>

                <div className="w-full p-space-sm rounded-lg bg-surface-base font-code-md text-code-md text-text-secondary flex flex-col gap-1">
                  <div className="text-text-muted">$ agentic-chaos test --strict</div>
                  <div className="text-accent-emerald flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px]">check</span>
                    <span>Passed 18 of 18 fault vectors. Gate clear.</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* MOBILE FOOTER */}
          <footer className="w-full bg-surface-raised px-gutter-mobile py-space-xl pb-28 mt-space-2xl text-left">
            <div className="flex flex-col gap-space-md">
              <div className="flex items-center gap-space-xs">
                <span className="font-code-md text-code-md text-text-muted">RUNNING UNDER</span>
                <span className="font-label-caps text-label-caps text-accent-cyan uppercase tracking-wider">
                  DeepAgentLabs
                </span>
              </div>
              <p className="font-body-sm text-body-sm text-text-secondary leading-relaxed">
                AgenticChaos is a resilience testing and determinism evaluation framework for multi-agent LLM systems.
              </p>
              <div className="flex flex-wrap items-center gap-space-md font-code-md text-code-md">
                <a className="text-primary hover:text-text-primary transition-colors" href="#mobile-quickstart-snippet">
                  DOCS
                </a>
                <span className="text-text-muted">/</span>
                <a
                  className="text-text-secondary hover:text-text-primary transition-colors"
                  href="https://github.com/DeepAgentLabs/agentic-chaos"
                  rel="noreferrer"
                  target="_blank"
                >
                  GITHUB
                </a>
                <span className="text-text-muted">/</span>
                <a
                  className="text-text-secondary hover:text-text-primary transition-colors"
                  href="https://github.com/DeepAgentLabs/agentic-chaos/blob/main/LICENSE"
                  rel="noreferrer"
                  target="_blank"
                >
                  MIT LICENSE
                </a>
              </div>
              <div className="font-code-md text-code-md text-text-muted pt-space-xs">
                © 2026 DeepAgentLabs. Engineered for runtime precision.
              </div>
            </div>
          </footer>
        </main>

        {/* MOBILE FIXED BOTTOM TAB NAVIGATION */}
        <nav className="fixed bottom-0 inset-x-0 z-50 pb-safe bg-surface-base/90 backdrop-blur-xl shadow-[0_-2px_12px_rgba(0,0,0,0.5)]">
          <div className="flex justify-around items-center h-16 px-space-xs">
            <button
              onClick={() => handleMobileNavClick('overview')}
              className={`flex flex-col items-center justify-center gap-space-xxs min-w-[44px] min-h-[44px] px-2 transition-colors cursor-pointer ${
                mobileActiveNav === 'overview' ? 'text-accent-cyan font-medium' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              <span className="material-symbols-outlined text-[20px]">grid_view</span>
              <span className="font-label-caps text-label-caps">OVERVIEW</span>
            </button>

            <button
              onClick={() => handleMobileNavClick('scenarios')}
              className={`flex flex-col items-center justify-center gap-space-xxs min-w-[44px] min-h-[44px] px-2 transition-colors cursor-pointer ${
                mobileActiveNav === 'scenarios' ? 'text-accent-cyan font-medium' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              <span className="material-symbols-outlined text-[20px]">bolt</span>
              <span className="font-label-caps text-label-caps">SCENARIOS</span>
            </button>

            <button
              onClick={() => handleMobileNavClick('telemetry')}
              className={`flex flex-col items-center justify-center gap-space-xxs min-w-[44px] min-h-[44px] px-2 transition-colors cursor-pointer ${
                mobileActiveNav === 'telemetry' ? 'text-accent-cyan font-medium' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              <span className="material-symbols-outlined text-[20px]">terminal</span>
              <span className="font-label-caps text-label-caps">TELEMETRY</span>
            </button>

            <button
              onClick={() => handleMobileNavClick('docs')}
              className={`flex flex-col items-center justify-center gap-space-xxs min-w-[44px] min-h-[44px] px-2 transition-colors cursor-pointer ${
                mobileActiveNav === 'docs' ? 'text-accent-cyan font-medium' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              <span className="material-symbols-outlined text-[20px]">menu_book</span>
              <span className="font-label-caps text-label-caps">DOCS</span>
            </button>
          </div>
        </nav>
      </div>
    </div>
  );
}
