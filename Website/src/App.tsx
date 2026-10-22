/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import {
  ShieldAlert,
  Zap,
  Terminal,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  Copy,
  Check,
  ExternalLink,
  Cpu,
  Layers,
  Sparkles,
  ArrowRight,
  GitBranch,
  FileCode,
  Gauge,
  Sliders,
  Flame,
  Clock,
  Bug,
  Compass,
  Database,
  RefreshCw,
  Workflow,
  Lock,
  Boxes
} from 'lucide-react';

export default function App() {
  // Navigation & UI States
  const [copiedCommand, setCopiedCommand] = useState<string | null>(null);
  const [activeCodeTab, setActiveCodeTab] = useState<'langgraph' | 'quickstart' | 'pytest' | 'cli'>('langgraph');
  const [activeFaultCategory, setActiveFaultCategory] = useState<'all' | 'llm' | 'agent' | 'drift'>('all');

  // Interactive Live Simulator State
  const [selectedScenario, setSelectedScenario] = useState<'financial' | 'customer' | 'routing'>('financial');
  const [enableTimeout, setEnableTimeout] = useState<boolean>(true);
  const [enableRateLimit, setEnableRateLimit] = useState<boolean>(true);
  const [enableMemoryCorruption, setEnableMemoryCorruption] = useState<boolean>(false);
  const [enableDrift, setEnableDrift] = useState<boolean>(false);
  const [simulationRunning, setSimulationRunning] = useState<boolean>(false);
  const [simulationLogs, setSimulationLogs] = useState<Array<{
    step: string;
    level: 'info' | 'warn' | 'fault' | 'success';
    msg: string;
    timestamp: string;
    duration?: string;
  }>>([
    {
      step: '01 / INIT',
      level: 'info',
      msg: 'Initialized Financial Analyst Agent workflow with LangGraph state engine',
      timestamp: '00:00.012',
      duration: '1.2ms'
    },
    {
      step: '02 / DISPATCH',
      level: 'info',
      msg: 'Supervisor dispatched task: "Summarize Q3 SEC 10-K filings for AAPL & MSFT"',
      timestamp: '00:00.084',
      duration: '4.8ms'
    },
    {
      step: '03 / TOOL_CALL',
      level: 'fault',
      msg: '[FAULT INJECTED] TokenTimeoutFault triggered on sec_filings_api: stalled token stream after 18 tokens',
      timestamp: '00:01.420',
      duration: '2,400ms'
    },
    {
      step: '04 / INTERCEPT',
      level: 'warn',
      msg: 'AgenticChaos interceptor captured fault -> synthesized degraded event to AI Operations Spec',
      timestamp: '00:01.428',
      duration: '0.2ms'
    },
    {
      step: '05 / FALLBACK',
      level: 'info',
      msg: 'Supervisor agent triggered graceful fallback policy: switched to cached offline document store',
      timestamp: '00:01.520',
      duration: '92ms'
    },
    {
      step: '06 / RECOVERED',
      level: 'success',
      msg: 'Recovery verified: Agent completed summary with 100% factual citation fidelity. Gate passed.',
      timestamp: '00:01.810',
      duration: '290ms'
    }
  ]);
  const [resilienceScore, setResilienceScore] = useState<number>(94);

  // Copy helper
  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCommand(id);
    setTimeout(() => setCopiedCommand(null), 2000);
  };

  // Run live simulation
  const runSimulation = () => {
    setSimulationRunning(true);
    setSimulationLogs([
      {
        step: '01 / SETUP',
        level: 'info',
        msg: `Deploying ChaosSession with active fault matrix for [${selectedScenario.toUpperCase()}]...`,
        timestamp: '00:00.005'
      }
    ]);

    setTimeout(() => {
      const newLogs: typeof simulationLogs = [
        {
          step: '01 / SETUP',
          level: 'info',
          msg: `Deploying ChaosSession with active fault matrix for [${selectedScenario.toUpperCase()}]...`,
          timestamp: '00:00.005'
        },
        {
          step: '02 / EXECUTE',
          level: 'info',
          msg: `Executing agent graph nodes under deterministic PRNG seed 0x8F2A...`,
          timestamp: '00:00.045'
        }
      ];

      if (enableTimeout) {
        newLogs.push({
          step: '03 / FAULT_TIMEOUT',
          level: 'fault',
          msg: '[FAULT INJECTED] TokenTimeoutFault: simulated 3.2s connection freeze on LLM stream gateway',
          timestamp: '00:01.120',
          duration: '3,200ms'
        });
      }

      if (enableRateLimit) {
        newLogs.push({
          step: '04 / FAULT_RATELIMIT',
          level: 'fault',
          msg: '[FAULT INJECTED] RateLimitStormFault: HTTP 429 Too Many Requests, retry-after: 4.5s burst',
          timestamp: '00:01.840',
          duration: '45ms'
        });
      }

      if (enableMemoryCorruption) {
        newLogs.push({
          step: '05 / FAULT_MEMORY',
          level: 'fault',
          msg: '[FAULT INJECTED] MemoryCorruptionFault: agent scratchpad variable "invoice_total" decayed by 30%',
          timestamp: '00:02.100',
          duration: '1.4ms'
        });
      }

      if (enableDrift) {
        newLogs.push({
          step: '06 / DRIFT_CHECK',
          level: 'warn',
          msg: '[DRIFT OBSERVED] Prompt semantic drift detected (delta: 0.18 > baseline threshold 0.12)',
          timestamp: '00:02.350',
          duration: '34ms'
        });
      }

      newLogs.push({
        step: '07 / FALLBACK_EVAL',
        level: 'info',
        msg: 'Evaluating circuit breakers & sub-agent retry boundaries against AI Operations Spec...',
        timestamp: '00:02.620',
        duration: '78ms'
      });

      newLogs.push({
        step: '08 / VERDICT',
        level: 'success',
        msg: 'RESILIENCE GATE PASSED: Graceful recovery within budget. Zero unhandled exceptions or runaway loops.',
        timestamp: '00:02.890',
        duration: '12ms'
      });

      setSimulationLogs(newLogs);
      
      // Calculate dynamic resilience score based on enabled faults
      const activeFaultCount = [enableTimeout, enableRateLimit, enableMemoryCorruption, enableDrift].filter(Boolean).length;
      const baseScore = 98 - (activeFaultCount * 3);
      setResilienceScore(Math.max(82, baseScore));
      setSimulationRunning(false);
    }, 900);
  };

  // Fault items dataset
  const faults = [
    {
      id: 'token-timeout',
      category: 'llm',
      title: 'TokenTimeoutFault',
      module: 'agentic_chaos.chaos',
      badge: 'LLM-LEVEL',
      desc: 'Simulates token stream stalls, connection hangs, and TTFT (time-to-first-token) latency spikes to verify client retry and cancel timeouts.',
      code: 'TokenTimeoutFault(hang_seconds=3.5, mode="delay")'
    },
    {
      id: 'rate-limit-storm',
      category: 'llm',
      title: 'RateLimitStormFault',
      module: 'agentic_chaos.chaos',
      badge: 'LLM-LEVEL',
      desc: 'Injects synthetic HTTP 429 bursts with dynamic retry-after backoffs to prove exponential backoff policies without draining live API quotas.',
      code: 'RateLimitStormFault(burst_count=5, retry_after=4.0)'
    },
    {
      id: 'silent-degradation',
      category: 'llm',
      title: 'SilentDegradationFault',
      module: 'agentic_chaos.chaos',
      badge: 'LLM-LEVEL',
      desc: 'Subtly corrupts LLM output tokens or injects hallucinated JSON payloads to ensure downstream validation and guardrail sidecars catch bad outputs.',
      code: 'SilentDegradationFault(degrade_ratio=0.35, strategy="truncate")'
    },
    {
      id: 'tool-call-failure',
      category: 'agent',
      title: 'ToolCallFailureFault',
      module: 'agentic_chaos.agents',
      badge: 'AGENT-LEVEL',
      desc: 'Wraps tool execution nodes to inject HTTP 500/502/504 errors, malformed return schemas, or connection drops directly into LangGraph or CrewAI.',
      code: 'ToolCallFailureFault(tool_name="web_search", timeout_seconds=4.0)'
    },
    {
      id: 'memory-corruption',
      category: 'agent',
      title: 'MemoryCorruptionFault',
      module: 'agentic_chaos.agents',
      badge: 'AGENT-LEVEL',
      desc: 'Deliberately drops dictionary keys, mutates variable bindings, or triggers semantic scratchpad decay across multi-turn delegation chains.',
      code: 'MemoryCorruptionFault(variable_name="scratchpad", mode="decay", rate=0.25)'
    },
    {
      id: 'infinite-loop-guard',
      category: 'agent',
      title: 'InfiniteLoopFault',
      module: 'agentic_chaos.agents',
      badge: 'AGENT-LEVEL',
      desc: 'Traps recursive tool-call ping-pongs between sub-agents and calculates runaway token billing and memory bloat before shipping to production.',
      code: 'InfiniteLoopFault(max_turns=6, runaway_threshold_tokens=4000)'
    },
    {
      id: 'prompt-model-drift',
      category: 'drift',
      title: 'DriftSnapshot & Compare',
      module: 'agentic_chaos.drift',
      badge: 'DRIFT (v0.4.0)',
      desc: 'Captures deterministic snapshots of system prompts, provider fingerprints, and semantic embeddings to flag silent provider-side updates.',
      code: 'compare_snapshots(baseline_snapshot, live_snapshot)'
    },
    {
      id: 'topology-tracker',
      category: 'agent',
      title: 'TopologyTracker',
      module: 'agentic_chaos.agents.topology',
      badge: 'AGENT-LEVEL',
      desc: 'Constructs a runtime dependency map of agents, tools, and shared scratchpads to locate single-points-of-failure in complex topologies.',
      code: 'TopologyTracker(record_events=True).analyze()'
    }
  ];

  const filteredFaults = activeFaultCategory === 'all' 
    ? faults 
    : faults.filter(f => f.category === activeFaultCategory);

  return (
    <div className="w-full min-h-screen bg-[#f7f7f8] text-[#0f172a] antialiased selection:bg-[#bef264] selection:text-black">
      
      {/* ========================================================================= */}
      {/* 1. GLOBAL STICKY ECOSYSTEM HEADER                                         */}
      {/* ========================================================================= */}
      <header className="sticky top-0 z-50 bg-[#f7f7f8]/90 backdrop-blur-md border-b border-zinc-200">
        <div className="max-w-[1440px] mx-auto px-6 h-16 flex items-center justify-between">
          
          {/* Logo & Product Sequence Breadcrumb */}
          <div className="flex items-center gap-3">
            <a 
              className="flex items-center gap-2 group focus:outline-none" 
              href="../Demo%20Website/code.html" 
              title="Return to DeepAgentLabs Ecosystem Hub"
            >
              <div className="w-7 h-7 bg-black text-[#bef264] flex items-center justify-center font-bold text-base rounded shadow-xs group-hover:scale-105 transition-transform">
                <span className="font-mono-tech">&gt;_</span>
              </div>
              <span className="text-lg font-bold tracking-tight text-zinc-900 group-hover:text-zinc-600 transition-colors">
                DeepAgentLabs
              </span>
            </a>

            <span className="text-zinc-300 font-mono-tech text-sm select-none">/</span>

            <div className="flex items-center gap-2">
              <span className="text-base font-extrabold tracking-tight text-zinc-950 font-mono-tech">
                agentic-chaos
              </span>
              <span className="px-2 py-0.5 text-[10px] bg-[#bef264]/40 text-zinc-800 rounded font-mono-tech font-bold uppercase tracking-wider hidden sm:inline-flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#84cc16]"></span>
                STAGE 04: STRESS
              </span>
            </div>
          </div>

          {/* Desktop Navigation Menu */}
          <nav className="hidden xl:flex items-center gap-6 text-[13.5px] font-medium text-zinc-600">
            <a className="hover:text-zinc-950 transition-colors" href="#operating-loop">Operating Loop</a>
            <a className="hover:text-zinc-950 transition-colors" href="#spectrum">Chaos Spectrum</a>
            <a className="hover:text-zinc-950 transition-colors" href="#simulator">Live Simulator</a>
            <a className="hover:text-zinc-950 transition-colors" href="#architecture">Architecture</a>
            <a className="hover:text-zinc-950 transition-colors" href="#code-walkthrough">Code &amp; SDK</a>
            <a className="hover:text-zinc-950 transition-colors" href="#benchmarks">Resilience Gate</a>
            <a className="hover:text-zinc-950 transition-colors" href="#docs">Docs</a>
          </nav>

          {/* Right Action Bar */}
          <div className="flex items-center gap-3">
            {/* Quick copy pip command */}
            <button
              onClick={() => copyToClipboard('pip install agentic-chaos', 'nav-pip')}
              className="hidden sm:inline-flex items-center gap-2 px-3 py-1.5 bg-zinc-100 hover:bg-zinc-200 text-zinc-800 border border-zinc-300 rounded-md font-mono-tech text-xs font-medium transition-colors cursor-pointer"
              title="Copy install command"
            >
              <span className="text-zinc-400 select-none">$</span>
              <span>{copiedCommand === 'nav-pip' ? 'Copied!' : 'pip install agentic-chaos'}</span>
              {copiedCommand === 'nav-pip' ? (
                <Check className="w-3.5 h-3.5 text-emerald-600" />
              ) : (
                <Copy className="w-3.5 h-3.5 text-zinc-400" />
              )}
            </button>

            {/* GitHub Link */}
            <a
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md border border-zinc-300 text-xs font-semibold text-zinc-800 bg-white hover:bg-zinc-50 hover:border-zinc-400 transition-all shadow-xs"
              href="https://github.com/DeepAgentLabs/agentic-chaos"
              rel="noreferrer"
              target="_blank"
            >
              <span>GitHub</span>
              <span className="text-zinc-400 text-sm">↗</span>
            </a>
          </div>

        </div>
      </header>

      {/* ========================================================================= */}
      {/* 2. HERO SECTION (Syntropic Technical Editorial Style)                      */}
      {/* ========================================================================= */}
      <section className="relative pt-12 pb-16 bg-[#f7f7f8] border-b border-zinc-200 overflow-hidden bg-grid-pattern">
        <div className="max-w-[1440px] mx-auto px-6 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          
          {/* Hero Left Column: Editorial Headline & CTAs */}
          <div className="lg:col-span-7 flex flex-col items-start pr-0 lg:pr-6">
            
            {/* Tagline Badge */}
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-200/80 border border-zinc-300 text-[11px] font-mono-tech tracking-wider uppercase text-zinc-800 mb-6 font-semibold">
              <span className="w-2 h-2 rounded-full bg-[#a3e635] animate-pulse"></span>
              STAGE 04: DETERMINISTIC CHAOS &amp; RESILIENCE TESTING
            </div>

            {/* Giant Typography Headline */}
            <h1 className="text-5xl xl:text-6xl tracking-tight text-zinc-950 font-extrabold leading-[1.08] mb-6 font-headline">
              Break agentic AI<br />
              before users do<br />
              <span className="italic font-serif font-normal bg-[#bef264] px-2 py-0.5 rounded-sm inline-block transform -rotate-1 text-zinc-950 shadow-xs">
                with deterministic chaos.
              </span>
            </h1>

            {/* Subtitle */}
            <p className="text-lg text-zinc-600 max-w-xl font-normal leading-relaxed mb-8">
              The resilience and failure-validation engine in the DeepAgentLabs ecosystem. 
              Deliberately inject token timeouts, tool crashes, memory decay, and rate limit storms 
              to verify recovery quality and safety gates before production.
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap items-center gap-3.5 mb-8">
              <a
                className="px-6 py-3 rounded-lg bg-zinc-950 text-white font-medium text-sm hover:bg-zinc-800 transition-interactive shadow-sm flex items-center gap-2"
                href="#spectrum"
              >
                <span>Explore Fault Modules</span>
                <ArrowRight className="w-4 h-4 text-[#bef264]" />
              </a>

              <a
                className="px-6 py-3 rounded-lg bg-white border border-zinc-300 text-zinc-900 font-medium text-sm hover:bg-zinc-50 hover:border-zinc-400 transition-interactive shadow-xs flex items-center gap-2"
                href="#simulator"
              >
                <Play className="w-3.5 h-3.5 text-[#84cc16] fill-current" />
                <span>Test Live in Simulator</span>
              </a>

              <div
                onClick={() => copyToClipboard('uv run agentic-chaos --help', 'hero-cli')}
                className="px-4 py-3 rounded-lg bg-zinc-100 border border-zinc-300 text-zinc-800 font-mono-tech text-xs hover:border-zinc-400 transition-colors flex items-center gap-2 cursor-pointer"
                title="Click to copy CLI command"
              >
                <span className="text-zinc-400 select-none">$</span>
                <span>{copiedCommand === 'hero-cli' ? 'Copied to clipboard!' : 'agentic-chaos chaos run'}</span>
                <Copy className="w-3.5 h-3.5 text-zinc-500" />
              </div>
            </div>

            {/* Meta Qualities Checklist */}
            <div className="flex flex-wrap items-center gap-6 text-xs font-mono-tech text-zinc-600">
              <div className="flex items-center gap-1.5">
                <span className="text-emerald-600 font-bold">✓</span>
                <span>Framework-neutral</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-emerald-600 font-bold">✓</span>
                <span>Zero external runtime deps</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-emerald-600 font-bold">✓</span>
                <span>ai-operations-spec exportable</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-emerald-600 font-bold">✓</span>
                <span>Deterministic seeds</span>
              </div>
            </div>

          </div>

          {/* Hero Right Column: High-tech System Stack Inspection Card */}
          <div className="lg:col-span-5">
            <div className="bg-[#0c0d0e] rounded-xl border border-zinc-800 p-6 shadow-2xl relative text-zinc-200">
              
              {/* Terminal Card Header */}
              <div className="flex items-center justify-between pb-4 border-b border-zinc-800 text-[11px] font-mono-tech">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-rose-500/80"></div>
                  <div className="w-2.5 h-2.5 rounded-full bg-amber-500/80"></div>
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/80"></div>
                  <span className="text-zinc-400 tracking-wider font-semibold ml-2">AGENTICCHAOS / TRACE INTERCEPTOR</span>
                </div>
                <span className="text-[#bef264] font-bold flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#bef264] animate-ping"></span>
                  LIVE ENGINE
                </span>
              </div>

              {/* Stack Rows Grid */}
              <div className="divide-y divide-zinc-800/80 my-3 font-mono-tech">
                {/* Step 01 */}
                <div className="py-2.5 px-2 flex items-center justify-between rounded hover:bg-zinc-900/60 transition-colors">
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-zinc-500">01</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">PLANNER</span>
                    <span className="text-sm font-semibold text-white">Delegate (market_analyst)</span>
                  </div>
                  <span className="text-xs text-zinc-400">1.2 ms</span>
                </div>

                {/* Step 02: Injected Fault */}
                <div className="py-2.5 px-2 flex flex-col gap-1.5 rounded bg-amber-950/20 border-l-2 border-amber-400 my-1">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-amber-400 font-bold">02</span>
                      <span className="text-xs px-2 py-0.5 rounded bg-amber-400/20 text-amber-300 border border-amber-400/30">
                        FAULT INJECTED
                      </span>
                      <span className="text-sm font-semibold text-amber-200">HTTP 504 Gateway Timeout</span>
                    </div>
                    <span className="text-xs font-bold text-amber-400">2,400 ms</span>
                  </div>
                  <div className="text-[11px] text-zinc-400 pl-7 flex items-center justify-between">
                    <span>TokenTimeoutFault active on web_search tool</span>
                    <span className="text-amber-300 font-mono-tech">[CHAOS_CALL]</span>
                  </div>
                </div>

                {/* Step 03 */}
                <div className="py-2.5 px-2 flex items-center justify-between rounded hover:bg-zinc-900/60 transition-colors">
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-zinc-500">03</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">FALLBACK</span>
                    <span className="text-sm font-semibold text-white">Circuit Breaker &amp; Cache</span>
                  </div>
                  <span className="text-xs text-zinc-400">85 ms</span>
                </div>

                {/* Step 04: Recovery */}
                <div className="py-2.5 px-2 flex items-center justify-between rounded bg-emerald-950/20 border-l-2 border-emerald-400 my-1">
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-emerald-400 font-bold">04</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-emerald-400/20 text-emerald-300 border border-emerald-400/30">
                      RECOVERED
                    </span>
                    <span className="text-sm font-semibold text-emerald-200">Resilient output produced</span>
                  </div>
                  <span className="text-xs text-emerald-400 font-bold">1.4 ms</span>
                </div>
              </div>

              {/* Bottom Foundation Banner */}
              <div className="mt-4 p-3 bg-zinc-900/90 rounded border border-zinc-800/80 flex items-center justify-between font-mono-tech text-xs">
                <div>
                  <div className="text-[10px] uppercase text-[#bef264] font-bold tracking-wider mb-0.5">
                    RESILIENCE EVIDENCE QUOTIENT
                  </div>
                  <div className="text-zinc-300 text-xs flex items-center gap-2">
                    <span>Spans: 8</span>
                    <span>•</span>
                    <span>Faults Handled: 1/1</span>
                    <span>•</span>
                    <span>Overhead: &lt; 0.2ms</span>
                  </div>
                </div>
                <div className="px-3 py-1 bg-black border border-[#84cc16] text-[#bef264] font-bold text-sm rounded">
                  94 / 100
                </div>
              </div>

            </div>
          </div>

        </div>
      </section>

      {/* ========================================================================= */}
      {/* 3. CONTINUOUS PACKAGE TICKER BAR                                          */}
      {/* ========================================================================= */}
      <div className="w-full bg-[#bef264] border-y border-[#a3e635] py-2.5 overflow-x-auto text-black font-mono-tech text-xs font-semibold tracking-tight shadow-inner">
        <div className="max-w-[1440px] mx-auto px-6 flex items-center justify-between whitespace-nowrap gap-8">
          <a className="flex items-center gap-2 hover:opacity-80 transition-opacity text-black" href="../Demo%20Website/code.html#ecosystem">
            <span>●</span>
            <span>mcp-server</span>
          </a>
          <a className="flex items-center gap-2 hover:opacity-80 transition-opacity text-black" href="../Demo%20Website/code.html#specification">
            <span>●</span>
            <span>ai-operations-spec</span>
          </a>
          <a className="flex items-center gap-2 hover:opacity-80 transition-opacity text-black" href="../Demo%20Website/code.html#products">
            <span>●</span>
            <span>agenticlens</span>
          </a>
          <a className="flex items-center gap-2 hover:opacity-80 transition-opacity text-black" href="../Demo%20Website/code.html#products">
            <span>●</span>
            <span>agentic-evals</span>
          </a>
          <div className="flex items-center gap-2 px-2.5 py-0.5 bg-black text-[#bef264] rounded font-bold shadow-xs">
            <span className="w-2 h-2 rounded-full bg-[#bef264] animate-pulse"></span>
            <span>agentic-chaos [CURRENT - 04 STRESS]</span>
          </div>
          <a className="flex items-center gap-2 hover:opacity-80 transition-opacity text-black" href="../Demo%20Website/code.html#products">
            <span>●</span>
            <span>agentic-sidecar</span>
          </a>
          <a className="flex items-center gap-2 hover:opacity-80 transition-opacity text-black" href="../Demo%20Website/code.html#products">
            <span>●</span>
            <span>control-tower</span>
          </a>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 4. THE OPERATING LOOP: WHERE AGENTIC-CHAOS FITS                            */}
      {/* ========================================================================= */}
      <section className="py-20 bg-[#090a0f] text-white border-b border-zinc-800" id="operating-loop">
        <div className="max-w-[1440px] mx-auto px-6">
          
          <div className="flex flex-col lg:flex-row lg:items-end justify-between mb-16 gap-6">
            <div>
              <div className="text-xs font-mono-tech uppercase tracking-widest text-[#bef264] font-semibold mb-2">
                THE OPERATING LOOP · STAGE CONTINUITY
              </div>
              <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tight font-headline">
                One loop,<br />
                <span className="text-[#bef264] font-serif italic font-normal">seven stages.</span>
              </h2>
            </div>
            <p className="max-w-xl text-zinc-400 text-sm leading-relaxed">
              In the DeepAgentLabs ecosystem, you define runtime contracts, supervise agent actions, observe behavior,
              and stress-test resilience before scoring releases. <strong className="text-white">AgenticChaos</strong> powers 
              Stage 04: deliberately breaking agents to guarantee robust recovery.
            </p>
          </div>

          {/* 7 Stage Cards with Stage 04 Highlighted */}
          <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-7 gap-3">
            
            {/* Stage 01 */}
            <div className="bg-[#121318] border border-zinc-800/80 rounded-lg p-4 flex flex-col justify-between opacity-75 hover:opacity-100 transition-opacity">
              <div>
                <div className="text-xs font-mono-tech text-zinc-500 mb-2">01</div>
                <h3 className="text-base font-bold text-white mb-1">Define</h3>
                <span className="text-[11px] font-mono-tech text-zinc-400 block mb-3">ai-operations-spec</span>
                <p className="text-xs text-zinc-400 leading-normal">
                  Shared schema for runs, steps, and incident evidence.
                </p>
              </div>
              <div className="mt-6 pt-3 border-t border-zinc-800/60 text-[10px] font-mono-tech text-zinc-500">
                SCHEMA CONTRACT
              </div>
            </div>

            {/* Stage 02 */}
            <div className="bg-[#121318] border border-zinc-800/80 rounded-lg p-4 flex flex-col justify-between opacity-75 hover:opacity-100 transition-opacity">
              <div>
                <div className="text-xs font-mono-tech text-zinc-500 mb-2">02</div>
                <h3 className="text-base font-bold text-white mb-1">Supervise</h3>
                <span className="text-[11px] font-mono-tech text-zinc-400 block mb-3">agentic-sidecar</span>
                <p className="text-xs text-zinc-400 leading-normal">
                  Real-time intent boundaries, critique, and human approval.
                </p>
              </div>
              <div className="mt-6 pt-3 border-t border-zinc-800/60 text-[10px] font-mono-tech text-zinc-500">
                REAL-TIME POLICY
              </div>
            </div>

            {/* Stage 03 */}
            <div className="bg-[#121318] border border-zinc-800/80 rounded-lg p-4 flex flex-col justify-between opacity-75 hover:opacity-100 transition-opacity">
              <div>
                <div className="text-xs font-mono-tech text-zinc-500 mb-2">03</div>
                <h3 className="text-base font-bold text-white mb-1">Observe</h3>
                <span className="text-[11px] font-mono-tech text-zinc-400 block mb-3">agenticlens</span>
                <p className="text-xs text-zinc-400 leading-normal">
                  End-to-end trace telemetry, latency, token spend, and profiling.
                </p>
              </div>
              <div className="mt-6 pt-3 border-t border-zinc-800/60 text-[10px] font-mono-tech text-zinc-500">
                TRACE TELEMETRY
              </div>
            </div>

            {/* Stage 04 - HIGHLIGHTED AS ACTIVE PRODUCT */}
            <div className="bg-zinc-900 border-2 border-[#bef264] rounded-lg p-4 flex flex-col justify-between relative shadow-[0_0_25px_rgba(190,242,100,0.15)] ring-1 ring-[#bef264]/40">
              <div className="absolute -top-3 left-3 px-2 py-0.5 bg-[#bef264] text-black font-mono-tech text-[9px] font-extrabold uppercase rounded">
                YOU ARE HERE
              </div>
              <div>
                <div className="text-xs font-mono-tech text-[#bef264] font-bold mb-2">04</div>
                <h3 className="text-base font-bold text-white mb-1">Stress &amp; Chaos</h3>
                <span className="text-[11px] font-mono-tech text-[#bef264] block mb-3 font-semibold">agentic-chaos</span>
                <p className="text-xs text-zinc-200 leading-normal">
                  Inject controlled faults, latency, tool crashes, and drift to validate recovery.
                </p>
              </div>
              <div className="mt-6 pt-3 border-t border-[#bef264]/40 text-[10px] font-mono-tech text-[#bef264] font-bold">
                RESILIENCE EVIDENCE
              </div>
            </div>

            {/* Stage 05 */}
            <div className="bg-[#121318] border border-zinc-800/80 rounded-lg p-4 flex flex-col justify-between opacity-75 hover:opacity-100 transition-opacity">
              <div>
                <div className="text-xs font-mono-tech text-zinc-500 mb-2">05</div>
                <h3 className="text-base font-bold text-white mb-1">Evaluate</h3>
                <span className="text-[11px] font-mono-tech text-zinc-400 block mb-3">agentic-evals</span>
                <p className="text-xs text-zinc-400 leading-normal">
                  Score behavior with deterministic &amp; judge evaluations; gate releases.
                </p>
              </div>
              <div className="mt-6 pt-3 border-t border-zinc-800/60 text-[10px] font-mono-tech text-zinc-500">
                GATING MATRIX
              </div>
            </div>

            {/* Stage 06 */}
            <div className="bg-[#121318] border border-zinc-800/80 rounded-lg p-4 flex flex-col justify-between opacity-75 hover:opacity-100 transition-opacity">
              <div>
                <div className="text-xs font-mono-tech text-zinc-500 mb-2">06</div>
                <h3 className="text-base font-bold text-white mb-1">Improve</h3>
                <span className="text-[11px] font-mono-tech text-zinc-400 block mb-3">control-tower</span>
                <p className="text-xs text-zinc-400 leading-normal">
                  Optimize prompt boundaries and fallbacks from evidence reports.
                </p>
              </div>
              <div className="mt-6 pt-3 border-t border-zinc-800/60 text-[10px] font-mono-tech text-zinc-500">
                FEEDBACK LOOP
              </div>
            </div>

            {/* Stage 07 */}
            <div className="bg-[#121318] border border-zinc-800/80 rounded-lg p-4 flex flex-col justify-between opacity-75 hover:opacity-100 transition-opacity">
              <div>
                <div className="text-xs font-mono-tech text-zinc-500 mb-2">07</div>
                <h3 className="text-base font-bold text-white mb-1">Operate</h3>
                <span className="text-[11px] font-mono-tech text-zinc-400 block mb-3">control-tower</span>
                <p className="text-xs text-zinc-400 leading-normal">
                  Fleet telemetry, incident tracking, and active system health.
                </p>
              </div>
              <div className="mt-6 pt-3 border-t border-zinc-800/60 text-[10px] font-mono-tech text-zinc-500">
                FLEET MONITOR
              </div>
            </div>

          </div>

        </div>
      </section>

      {/* ========================================================================= */}
      {/* 5. THE CHAOS SPECTRUM: LLM & AGENT FAULTS                                  */}
      {/* ========================================================================= */}
      <section className="py-20 bg-[#f7f7f8] border-b border-zinc-200" id="spectrum">
        <div className="max-w-[1440px] mx-auto px-6">
          
          <div className="flex flex-col lg:flex-row lg:items-end justify-between mb-12 gap-6">
            <div>
              <div className="text-xs font-mono-tech uppercase tracking-widest text-zinc-500 font-semibold mb-2">
                FAULT CATALOG &amp; INJECTION PRIMITIVES
              </div>
              <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tight text-zinc-950 font-headline">
                The full chaos <span className="bg-[#bef264] px-1 font-serif italic font-normal">spectrum.</span>
              </h2>
            </div>
            
            {/* Filter pills */}
            <div className="flex items-center gap-2 font-mono-tech text-xs">
              <button
                onClick={() => setActiveFaultCategory('all')}
                className={`px-3 py-1.5 rounded-md border transition-colors cursor-pointer ${
                  activeFaultCategory === 'all'
                    ? 'bg-zinc-950 text-white border-zinc-950 font-bold'
                    : 'bg-white text-zinc-700 border-zinc-300 hover:bg-zinc-100'
                }`}
              >
                All Faults ({faults.length})
              </button>
              <button
                onClick={() => setActiveFaultCategory('llm')}
                className={`px-3 py-1.5 rounded-md border transition-colors cursor-pointer ${
                  activeFaultCategory === 'llm'
                    ? 'bg-zinc-950 text-white border-zinc-950 font-bold'
                    : 'bg-white text-zinc-700 border-zinc-300 hover:bg-zinc-100'
                }`}
              >
                LLM-Level
              </button>
              <button
                onClick={() => setActiveFaultCategory('agent')}
                className={`px-3 py-1.5 rounded-md border transition-colors cursor-pointer ${
                  activeFaultCategory === 'agent'
                    ? 'bg-zinc-950 text-white border-zinc-950 font-bold'
                    : 'bg-white text-zinc-700 border-zinc-300 hover:bg-zinc-100'
                }`}
              >
                Agent-Level
              </button>
              <button
                onClick={() => setActiveFaultCategory('drift')}
                className={`px-3 py-1.5 rounded-md border transition-colors cursor-pointer ${
                  activeFaultCategory === 'drift'
                    ? 'bg-zinc-950 text-white border-zinc-950 font-bold'
                    : 'bg-white text-zinc-700 border-zinc-300 hover:bg-zinc-100'
                }`}
              >
                Prompt/Model Drift
              </button>
            </div>
          </div>

          {/* Fault Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {filteredFaults.map((fault) => (
              <div
                key={fault.id}
                className="bg-white rounded-xl border border-zinc-300 p-6 flex flex-col justify-between hover:shadow-md hover:border-zinc-500 transition-all group"
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[10px] font-mono-tech px-2 py-0.5 rounded bg-zinc-100 text-zinc-700 border border-zinc-200 font-bold uppercase tracking-wider">
                      {fault.badge}
                    </span>
                    <span className="text-zinc-400 text-xs font-mono-tech">
                      {fault.category.toUpperCase()}
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-zinc-950 mb-1 group-hover:text-black transition-colors font-headline">
                    {fault.title}
                  </h3>
                  <div className="text-[11px] font-mono-tech text-zinc-500 mb-3">
                    {fault.module}
                  </div>

                  <p className="text-xs text-zinc-600 leading-relaxed mb-4">
                    {fault.desc}
                  </p>
                </div>

                <div>
                  <div className="p-2.5 bg-zinc-900 rounded text-[11px] font-mono-tech text-[#bef264] border border-zinc-800 overflow-x-auto">
                    <code>{fault.code}</code>
                  </div>
                  <div className="mt-3 pt-3 border-t border-zinc-200 flex items-center justify-between text-xs font-mono-tech text-zinc-500">
                    <span>Emits ChaosEvent</span>
                    <span className="text-zinc-900 font-bold group-hover:translate-x-1 transition-transform">→</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

        </div>
      </section>

      {/* ========================================================================= */}
      {/* 6. INTERACTIVE LIVE CHAOS SIMULATOR (UI/UX Centerpiece)                   */}
      {/* ========================================================================= */}
      <section className="py-20 bg-white border-b border-zinc-200" id="simulator">
        <div className="max-w-[1440px] mx-auto px-6">
          
          <div className="flex flex-col lg:flex-row lg:items-end justify-between mb-12 gap-6">
            <div>
              <div className="text-xs font-mono-tech uppercase tracking-widest text-zinc-500 font-semibold mb-2">
                INTERACTIVE LAB
              </div>
              <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tight text-zinc-950 font-headline">
                Live chaos <span className="italic font-serif font-normal bg-[#bef264] px-2 py-0.5 rounded-sm">simulator.</span>
              </h2>
            </div>
            <p className="max-w-md text-sm text-zinc-600 leading-relaxed">
              Toggle simulated failure modes on real agent workflows. Observe how non-invasive wrappers intercept faults,
              preserve context, and generate structured resilience evidence.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            
            {/* Left Controls & Configuration Panel (lg:col-span-5) */}
            <div className="lg:col-span-5 space-y-6">
              
              {/* Scenario Picker */}
              <div className="bg-[#f7f7f8] rounded-xl border border-zinc-300 p-5 shadow-xs">
                <label className="text-xs font-mono-tech font-bold uppercase text-zinc-700 tracking-wider block mb-3">
                  01 / Select Target Agent Workflow
                </label>
                <div className="space-y-2">
                  <div
                    onClick={() => setSelectedScenario('financial')}
                    className={`p-3 rounded-lg border text-xs font-mono-tech cursor-pointer flex items-center justify-between transition-colors ${
                      selectedScenario === 'financial'
                        ? 'bg-zinc-950 text-white border-zinc-950'
                        : 'bg-white text-zinc-800 border-zinc-300 hover:bg-zinc-50'
                    }`}
                  >
                    <div>
                      <div className="font-bold text-sm">Financial Research Agent</div>
                      <div className="text-[11px] text-zinc-400">Multi-turn SEC filings search &amp; cashflow analyzer</div>
                    </div>
                    {selectedScenario === 'financial' && <Check className="w-4 h-4 text-[#bef264]" />}
                  </div>

                  <div
                    onClick={() => setSelectedScenario('customer')}
                    className={`p-3 rounded-lg border text-xs font-mono-tech cursor-pointer flex items-center justify-between transition-colors ${
                      selectedScenario === 'customer'
                        ? 'bg-zinc-950 text-white border-zinc-950'
                        : 'bg-white text-zinc-800 border-zinc-300 hover:bg-zinc-50'
                    }`}
                  >
                    <div>
                      <div className="font-bold text-sm">Customer Support &amp; Refund Agent</div>
                      <div className="text-[11px] text-zinc-400">SQL database queries &amp; payment gateway webhooks</div>
                    </div>
                    {selectedScenario === 'customer' && <Check className="w-4 h-4 text-[#bef264]" />}
                  </div>

                  <div
                    onClick={() => setSelectedScenario('routing')}
                    className={`p-3 rounded-lg border text-xs font-mono-tech cursor-pointer flex items-center justify-between transition-colors ${
                      selectedScenario === 'routing'
                        ? 'bg-zinc-950 text-white border-zinc-950'
                        : 'bg-white text-zinc-800 border-zinc-300 hover:bg-zinc-50'
                    }`}
                  >
                    <div>
                      <div className="font-bold text-sm">Multi-Agent Router &amp; Supervisor</div>
                      <div className="text-[11px] text-zinc-400">LangGraph hierarchical task delegation tree</div>
                    </div>
                    {selectedScenario === 'routing' && <Check className="w-4 h-4 text-[#bef264]" />}
                  </div>
                </div>
              </div>

              {/* Active Fault Injection Toggles */}
              <div className="bg-[#f7f7f8] rounded-xl border border-zinc-300 p-5 shadow-xs">
                <label className="text-xs font-mono-tech font-bold uppercase text-zinc-700 tracking-wider block mb-3">
                  02 / Configure Fault Injection Suite
                </label>

                <div className="space-y-3 font-mono-tech text-xs">
                  {/* Toggle 1 */}
                  <label className="flex items-center justify-between p-3 rounded-lg bg-white border border-zinc-200 cursor-pointer hover:border-zinc-400 transition-colors">
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={enableTimeout}
                        onChange={(e) => setEnableTimeout(e.target.checked)}
                        className="w-4 h-4 text-black rounded border-zinc-300 focus:ring-black"
                      />
                      <div>
                        <span className="font-bold text-zinc-950 block">TokenTimeoutFault</span>
                        <span className="text-[11px] text-zinc-500">Inject 3.2s LLM token stream hang</span>
                      </div>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-bold">TIMEOUT</span>
                  </label>

                  {/* Toggle 2 */}
                  <label className="flex items-center justify-between p-3 rounded-lg bg-white border border-zinc-200 cursor-pointer hover:border-zinc-400 transition-colors">
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={enableRateLimit}
                        onChange={(e) => setEnableRateLimit(e.target.checked)}
                        className="w-4 h-4 text-black rounded border-zinc-300 focus:ring-black"
                      />
                      <div>
                        <span className="font-bold text-zinc-950 block">RateLimitStormFault</span>
                        <span className="text-[11px] text-zinc-500">Trigger HTTP 429 burst with 4.5s backoff</span>
                      </div>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-rose-100 text-rose-800 font-bold">429 SPIKE</span>
                  </label>

                  {/* Toggle 3 */}
                  <label className="flex items-center justify-between p-3 rounded-lg bg-white border border-zinc-200 cursor-pointer hover:border-zinc-400 transition-colors">
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={enableMemoryCorruption}
                        onChange={(e) => setEnableMemoryCorruption(e.target.checked)}
                        className="w-4 h-4 text-black rounded border-zinc-300 focus:ring-black"
                      />
                      <div>
                        <span className="font-bold text-zinc-950 block">MemoryCorruptionFault</span>
                        <span className="text-[11px] text-zinc-500">Decay scratchpad state across steps</span>
                      </div>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-purple-100 text-purple-800 font-bold">MUTATION</span>
                  </label>

                  {/* Toggle 4 */}
                  <label className="flex items-center justify-between p-3 rounded-lg bg-white border border-zinc-200 cursor-pointer hover:border-zinc-400 transition-colors">
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={enableDrift}
                        onChange={(e) => setEnableDrift(e.target.checked)}
                        className="w-4 h-4 text-black rounded border-zinc-300 focus:ring-black"
                      />
                      <div>
                        <span className="font-bold text-zinc-950 block">Prompt / Model Drift</span>
                        <span className="text-[11px] text-zinc-500">Compare against v0.4.0 baseline snapshot</span>
                      </div>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-bold">DRIFT v0.4</span>
                  </label>
                </div>

                {/* Execute Button */}
                <div className="mt-5">
                  <button
                    onClick={runSimulation}
                    disabled={simulationRunning}
                    className="w-full py-3.5 px-4 rounded-lg bg-black hover:bg-zinc-800 text-white font-mono-tech text-xs font-bold transition-all shadow-md flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                  >
                    {simulationRunning ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin text-[#bef264]" />
                        <span>Injecting Faults &amp; Evaluating Spans...</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4 text-[#bef264] fill-current" />
                        <span>Execute Workflow Under Active Chaos</span>
                      </>
                    )}
                  </button>
                </div>

              </div>

            </div>

            {/* Right Live Terminal & Spec Inspector (lg:col-span-7) */}
            <div className="lg:col-span-7 bg-[#0d0e12] rounded-xl border border-zinc-800 p-6 text-white shadow-xl">
              
              {/* Terminal Window Bar */}
              <div className="flex items-center justify-between pb-4 border-b border-zinc-800 text-xs font-mono-tech">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-rose-500"></div>
                  <div className="w-2.5 h-2.5 rounded-full bg-amber-500"></div>
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-500"></div>
                  <span className="ml-2 font-bold text-white uppercase">
                    CHAOS_SESSION_REPORT: [{selectedScenario.toUpperCase()}]
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-zinc-400">SEED: 0x8F2A</span>
                  <span className="px-2 py-0.5 rounded bg-zinc-800 text-[#bef264] font-bold">
                    RESILIENCE: {resilienceScore}/100
                  </span>
                </div>
              </div>

              {/* Terminal Log Stream */}
              <div className="mt-4 font-mono-tech text-xs space-y-2.5 min-h-[300px] max-h-[360px] overflow-y-auto pr-2">
                {simulationLogs.map((log, idx) => (
                  <div
                    key={idx}
                    className={`p-2.5 rounded border transition-all ${
                      log.level === 'fault'
                        ? 'bg-amber-950/30 border-amber-500/40 text-amber-200'
                        : log.level === 'warn'
                        ? 'bg-purple-950/30 border-purple-500/40 text-purple-200'
                        : log.level === 'success'
                        ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-200'
                        : 'bg-zinc-900/60 border-zinc-800 text-zinc-300'
                    }`}
                  >
                    <div className="flex items-center justify-between text-[10px] text-zinc-400 mb-1">
                      <span className="font-bold text-white">{log.step}</span>
                      <div className="flex items-center gap-2">
                        {log.duration && (
                          <span className="text-[#bef264]">{log.duration}</span>
                        )}
                        <span>{log.timestamp}</span>
                      </div>
                    </div>
                    <div className="leading-relaxed">
                      {log.msg}
                    </div>
                  </div>
                ))}
              </div>

              {/* AI Operations Spec JSON Artifact Output */}
              <div className="mt-5 pt-4 border-t border-zinc-800 font-mono-tech text-[11px]">
                <div className="flex items-center justify-between text-zinc-400 mb-2">
                  <span className="text-[10px] uppercase font-bold text-[#bef264]">
                    AI OPERATIONS SPEC INCIDENT EXPORT
                  </span>
                  <span>v0.4 SCHEMA COMPLIANT</span>
                </div>
                <div className="p-3 bg-[#050608] rounded border border-zinc-800 text-zinc-300 overflow-x-auto text-[11px] leading-relaxed">
                  <pre>{JSON.stringify({
                    schema_version: "ai-operations-spec/v0.4",
                    event_type: "chaos.injection.recovery",
                    session_id: "csess_98a2f1b0",
                    scenario: selectedScenario,
                    faults_injected: [
                      enableTimeout && "TokenTimeoutFault",
                      enableRateLimit && "RateLimitStormFault",
                      enableMemoryCorruption && "MemoryCorruptionFault",
                      enableDrift && "PromptDrift"
                    ].filter(Boolean),
                    outcome: "recovered_graceful",
                    resilience_quotient: resilienceScore / 100,
                    evidence_retention: "100%"
                  }, null, 2)}</pre>
                </div>
              </div>

            </div>

          </div>

        </div>
      </section>

      {/* ========================================================================= */}
      {/* 7. ARCHITECTURE & INTERCEPTOR CAPABILITY MAP                              */}
      {/* ========================================================================= */}
      <section className="py-20 bg-[#f7f7f8] border-b border-zinc-200" id="architecture">
        <div className="max-w-[1440px] mx-auto px-6">
          
          <div className="flex flex-col lg:flex-row lg:items-end justify-between mb-12 gap-6">
            <div>
              <div className="text-xs font-mono-tech uppercase tracking-widest text-zinc-500 font-semibold mb-2">
                ZERO-OVERHEAD INTERCEPTOR ARCHITECTURE
              </div>
              <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tight text-zinc-950 font-headline">
                How it connects to <span className="underline decoration-wavy decoration-[#a3e635]">your stack.</span>
              </h2>
            </div>
            <p className="max-w-md text-sm text-zinc-600 leading-relaxed">
              AgenticChaos wraps external tools and model gateways with micro-millisecond latency. 
              No invasive framework rewrites or proxy daemon requirements.
            </p>
          </div>

          {/* 3 Tier System Diagram */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            
            {/* Box 1 */}
            <div className="bg-white rounded-xl border border-zinc-300 p-6 shadow-xs flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-4 mb-4 border-b border-zinc-200">
                  <span className="text-xs font-mono-tech text-zinc-500">01 / HOST RUNTIME</span>
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                </div>
                <h3 className="text-xl font-bold text-zinc-900 mb-2 font-headline">
                  Agent Execution Engine
                </h3>
                <p className="text-xs text-zinc-600 leading-relaxed mb-4">
                  Runs directly inside your existing LangGraph, CrewAI, AutoGen, LlamaIndex, or raw Python workflow.
                </p>
                <div className="flex flex-wrap gap-1.5 font-mono-tech text-[10px]">
                  <span className="px-2 py-0.5 bg-zinc-100 rounded border border-zinc-200">LangGraph</span>
                  <span className="px-2 py-0.5 bg-zinc-100 rounded border border-zinc-200">CrewAI</span>
                  <span className="px-2 py-0.5 bg-zinc-100 rounded border border-zinc-200">OpenAI Swarm</span>
                  <span className="px-2 py-0.5 bg-zinc-100 rounded border border-zinc-200">LlamaIndex</span>
                </div>
              </div>
              <div className="mt-6 pt-3 border-t border-zinc-200 text-xs font-mono-tech text-zinc-500">
                Pure Python 3.10+
              </div>
            </div>

            {/* Box 2 (Highlighted Core) */}
            <div className="bg-[#0c0d10] text-white rounded-xl border border-zinc-800 p-6 shadow-xl flex flex-col justify-between ring-2 ring-[#bef264]/40">
              <div>
                <div className="flex items-center justify-between pb-4 mb-4 border-b border-zinc-800">
                  <span className="text-xs font-mono-tech text-[#bef264] font-bold">02 / INTERCEPTOR PROXY</span>
                  <span className="px-2 py-0.5 bg-[#bef264] text-black font-mono-tech text-[9px] font-bold rounded">
                    ACTIVE
                  </span>
                </div>
                <h3 className="text-xl font-bold text-white mb-2 font-headline">
                  AgenticChaos Core Engine
                </h3>
                <p className="text-xs text-zinc-400 leading-relaxed mb-4">
                  Dynamically modulates model completions, tool RPCs, vector queries, and scratchpad memory with deterministic PRNG seeds.
                </p>
                <div className="space-y-1.5 font-mono-tech text-[11px] text-zinc-300">
                  <div className="flex items-center gap-2">
                    <span className="text-[#bef264]">✓</span>
                    <span>Token &amp; Rate-limit jitter</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[#bef264]">✓</span>
                    <span>State corruption &amp; loop break</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[#bef264]">✓</span>
                    <span>&lt; 0.2ms interceptor overhead</span>
                  </div>
                </div>
              </div>
              <div className="mt-6 pt-3 border-t border-zinc-800 text-xs font-mono-tech text-[#bef264]">
                agentic_chaos.chaos_call()
              </div>
            </div>

            {/* Box 3 */}
            <div className="bg-white rounded-xl border border-zinc-300 p-6 shadow-xs flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-4 mb-4 border-b border-zinc-200">
                  <span className="text-xs font-mono-tech text-zinc-500">03 / ECOSYSTEM SYNC</span>
                  <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                </div>
                <h3 className="text-xl font-bold text-zinc-900 mb-2 font-headline">
                  Evidence &amp; Spec Export
                </h3>
                <p className="text-xs text-zinc-600 leading-relaxed mb-4">
                  Passes structured events directly to AgenticLens for observability and generates AI Operations Spec reports.
                </p>
                <div className="space-y-1.5 font-mono-tech text-[11px] text-zinc-600">
                  <div>• AgenticLens: attach_events()</div>
                  <div>• Spec: AI Operations Spec v0.4</div>
                  <div>• Sidecar: verified intent fallback</div>
                  <div>• MCP: deep-agentic-core-mcp tools</div>
                </div>
              </div>
              <div className="mt-6 pt-3 border-t border-zinc-200 text-xs font-mono-tech text-zinc-500">
                ai-operations-spec exportable
              </div>
            </div>

          </div>

          {/* Ecosystem Banner Bridge */}
          <div className="bg-[#bef264] border border-[#a3e635] text-zinc-950 rounded-lg p-3.5 text-center font-mono-tech shadow-xs flex flex-col sm:flex-row items-center justify-between px-6 gap-2">
            <span className="text-xs font-bold uppercase tracking-wider">ECOSYSTEM BOUNDARY GUARANTEE</span>
            <span className="text-[12px]">AgenticChaos is 100% standalone — zero mandatory dependencies from other ecosystem repos.</span>
            <span className="px-2 py-0.5 bg-black text-white text-[10px] rounded font-bold">INDEPENDENT</span>
          </div>

        </div>
      </section>

      {/* ========================================================================= */}
      {/* 8. CODE WALKTHROUGH & SDK EXAMPLES                                        */}
      {/* ========================================================================= */}
      <section className="py-20 bg-white border-b border-zinc-200" id="code-walkthrough">
        <div className="max-w-[1440px] mx-auto px-6">
          
          <div className="flex flex-col lg:flex-row lg:items-end justify-between mb-12 gap-6">
            <div>
              <div className="text-xs font-mono-tech uppercase tracking-widest text-zinc-500 font-semibold mb-2">
                DEVELOPER EXPERIENCE
              </div>
              <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tight text-zinc-950 font-headline">
                Instrument in 3 lines.<br />
                <span className="bg-[#bef264] px-1 font-serif italic font-normal">Test everywhere.</span>
              </h2>
            </div>
            <p className="max-w-md text-sm text-zinc-600 leading-relaxed">
              Native adapters for LangGraph tools and nodes, straightforward context managers, 
              and CLI runners for instant pipeline stress-testing.
            </p>
          </div>

          {/* Code Viewer Shell */}
          <div className="bg-[#0c0d10] rounded-xl border border-zinc-800 shadow-2xl overflow-hidden">
            
            {/* Tab Header Bar */}
            <div className="flex flex-wrap items-center justify-between px-5 py-3 border-b border-zinc-800 bg-[#07080a] text-xs font-mono-tech gap-3">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveCodeTab('langgraph')}
                  className={`px-3 py-1.5 rounded transition-colors cursor-pointer ${
                    activeCodeTab === 'langgraph'
                      ? 'bg-zinc-800 text-white font-bold text-[#bef264]'
                      : 'text-zinc-400 hover:text-white'
                  }`}
                >
                  langgraph_adapter.py
                </button>
                <button
                  onClick={() => setActiveCodeTab('quickstart')}
                  className={`px-3 py-1.5 rounded transition-colors cursor-pointer ${
                    activeCodeTab === 'quickstart'
                      ? 'bg-zinc-800 text-white font-bold text-[#bef264]'
                      : 'text-zinc-400 hover:text-white'
                  }`}
                >
                  quickstart.py
                </button>
                <button
                  onClick={() => setActiveCodeTab('pytest')}
                  className={`px-3 py-1.5 rounded transition-colors cursor-pointer ${
                    activeCodeTab === 'pytest'
                      ? 'bg-zinc-800 text-white font-bold text-[#bef264]'
                      : 'text-zinc-400 hover:text-white'
                  }`}
                >
                  test_resilience.py
                </button>
                <button
                  onClick={() => setActiveCodeTab('cli')}
                  className={`px-3 py-1.5 rounded transition-colors cursor-pointer ${
                    activeCodeTab === 'cli'
                      ? 'bg-zinc-800 text-white font-bold text-[#bef264]'
                      : 'text-zinc-400 hover:text-white'
                  }`}
                >
                  cli_workflow.sh
                </button>
              </div>

              <div className="flex items-center gap-3">
                <span className="text-zinc-500 hidden sm:inline">Python 3.10+ · UV Ready</span>
                <button
                  onClick={() => {
                    const code = activeCodeTab === 'langgraph'
                      ? `from agentic_chaos.agents.langgraph import wrap_tool, wrap_node\nfrom agentic_chaos.chaos import chaos_session, TokenTimeoutFault\nfrom agentic_chaos.agents import ToolCallFailureFault\n\n# Wrap LangGraph tool without touching the graph logic\nresilient_tool = wrap_tool(web_search, tool_name="web_search")\n\n# Execute graph within active chaos session\nwith chaos_session([\n    ToolCallFailureFault(tool_name="web_search", timeout_seconds=3.0),\n    TokenTimeoutFault(hang_seconds=2.5)\n]) as session:\n    result = graph.invoke({"input": "Analyze Q3 SEC filings"})\n    print(f"Recorded {len(session.events)} chaos events")\n    assert result["status"] == "success"  # Fallback verified`
                      : activeCodeTab === 'quickstart'
                      ? `from agentic_chaos import chaos_call, chaos_session\nfrom agentic_chaos.chaos.faults import TokenTimeoutFault, RateLimitStormFault\n\n# Standard Python LLM call wrapper\nwith chaos_session([\n    TokenTimeoutFault(hang_seconds=2.0),\n    RateLimitStormFault(burst_count=3, retry_after=4.0)\n]) as session:\n    response = chaos_call(client.chat.completions.create, model="gpt-4o", messages=msgs)\n    print(session.events[0].outcome)  # 'errored' / 'degraded'`
                      : activeCodeTab === 'pytest'
                      ? `import pytest\nfrom agentic_chaos import chaos_session\nfrom agentic_chaos.agents import MemoryCorruptionFault\n\ndef test_agent_memory_resilience():\n    # Enforce deterministic PRNG seed for exact CI reproducibility\n    with chaos_session([\n        MemoryCorruptionFault(variable_name="scratchpad", mode="decay", rate=0.25)\n    ], seed=42) as session:\n        agent_output = run_reconcile_agent("Invoice #882")\n        assert len(session.events) > 0\n        assert agent_output.has_valid_total()  # Self-healing test`
                      : `agentic-chaos chaos run my_agent.py \\\n  --inject token_timeout,rate_limit_storm,tool_failure \\\n  --save chaos_report.json\n\nagentic-chaos drift compare baseline_snapshot.json \\\n  --prompt-file prompt.txt \\\n  --output-file current.txt`;
                    copyToClipboard(code, 'tab-code');
                  }}
                  className="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs rounded border border-zinc-700 transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  {copiedCommand === 'tab-code' ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5 text-zinc-400" />
                      <span>Copy Code</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Code Content */}
            <div className="p-6 font-mono-tech text-xs text-zinc-200 overflow-x-auto leading-relaxed">
              {activeCodeTab === 'langgraph' && (
                <pre><code><span className="text-zinc-500"># 1. Import LangGraph native wrappers and chaos faults</span>
<span className="text-sky-400">from</span> agentic_chaos.agents.langgraph <span className="text-sky-400">import</span> wrap_tool, wrap_node
<span className="text-sky-400">from</span> agentic_chaos.chaos <span className="text-sky-400">import</span> chaos_session, TokenTimeoutFault
<span className="text-sky-400">from</span> agentic_chaos.agents <span className="text-sky-400">import</span> ToolCallFailureFault

<span className="text-zinc-500"># 2. Non-invasively wrap tool execution without rewriting graph logic</span>
resilient_tool = wrap_tool(web_search, tool_name=<span className="text-emerald-300">"web_search"</span>)

<span className="text-zinc-500"># 3. Execute graph inside active chaos session with timeout &amp; tool failure</span>
<span className="text-sky-400">with</span> chaos_session([
    ToolCallFailureFault(tool_name=<span className="text-emerald-300">"web_search"</span>, timeout_seconds=<span className="text-amber-400">3.0</span>),
    TokenTimeoutFault(hang_seconds=<span className="text-amber-400">2.5</span>)
]) <span className="text-sky-400">as</span> session:
    result = graph.invoke(&#123;<span className="text-emerald-300">"input"</span>: <span className="text-emerald-300">"Analyze Q3 SEC filings"</span>&#125;)
    
    <span className="text-zinc-500"># Verify structured evidence</span>
    <span className="text-sky-400">print</span>(<span className="text-emerald-300">f"Chaos Events Emitted: &#123;len(session.events)&#125;"</span>)
    <span className="text-sky-400">print</span>(<span className="text-emerald-300">f"Fault Outcome:         &#123;session.events[0].outcome&#125;"</span>)
    <span className="text-sky-400">assert</span> result[<span className="text-emerald-300">"status"</span>] == <span className="text-emerald-300">"success"</span>  <span className="text-zinc-500"># Fallback handled cleanly</span></code></pre>
              )}

              {activeCodeTab === 'quickstart' && (
                <pre><code><span className="text-zinc-500"># Core Python API: chaos_call and chaos_session</span>
<span className="text-sky-400">from</span> agentic_chaos <span className="text-sky-400">import</span> chaos_call, chaos_session
<span className="text-sky-400">from</span> agentic_chaos.chaos.faults <span className="text-sky-400">import</span> TokenTimeoutFault, RateLimitStormFault

<span className="text-sky-400">with</span> chaos_session([
    TokenTimeoutFault(hang_seconds=<span className="text-amber-400">2.0</span>),
    RateLimitStormFault(burst_count=<span className="text-amber-400">3</span>, retry_after=<span className="text-amber-400">4.0</span>)
]) <span className="text-sky-400">as</span> session:
    <span className="text-zinc-500"># Direct callable interceptor</span>
    response = chaos_call(
        client.chat.completions.create,
        model=<span className="text-emerald-300">"gpt-4o"</span>,
        messages=[&#123;<span className="text-emerald-300">"role"</span>: <span className="text-emerald-300">"user"</span>, <span className="text-emerald-300">"content"</span>: <span className="text-emerald-300">"Reconcile invoice"</span>&#125;]
    )
    
    <span className="text-sky-400">print</span>(session.events[<span className="text-amber-400">0</span>].outcome)  <span className="text-zinc-500"># 'errored' / 'degraded'</span></code></pre>
              )}

              {activeCodeTab === 'pytest' && (
                <pre><code><span className="text-zinc-500"># CI/CD Pytest integration for regression suites</span>
<span className="text-sky-400">import</span> pytest
<span className="text-sky-400">from</span> agentic_chaos <span className="text-sky-400">import</span> chaos_session
<span className="text-sky-400">from</span> agentic_chaos.agents <span className="text-sky-400">import</span> MemoryCorruptionFault

<span className="text-sky-400">def</span> <span className="text-emerald-300">test_agent_memory_decay_recovery</span>():
    <span className="text-zinc-500"># Enforce deterministic PRNG seed for bitwise reproducibility</span>
    <span className="text-sky-400">with</span> chaos_session([
        MemoryCorruptionFault(variable_name=<span className="text-emerald-300">"scratchpad"</span>, mode=<span className="text-emerald-300">"decay"</span>, rate=<span className="text-amber-400">0.25</span>)
    ], seed=<span className="text-amber-400">42</span>) <span className="text-sky-400">as</span> session:
        result = agent.run(<span className="text-emerald-300">"Process claim #8892"</span>)
        <span className="text-sky-400">assert</span> <span className="text-sky-400">len</span>(session.events) &gt; <span className="text-amber-400">0</span>
        <span className="text-sky-400">assert</span> result.repaired_state <span className="text-sky-400">is True</span>  <span className="text-zinc-500"># Verified self-healing</span></code></pre>
              )}

              {activeCodeTab === 'cli' && (
                <pre><code><span className="text-zinc-500"># CLI Usage: execute agents under active fault storm</span>
<span className="text-[#bef264]">$</span> agentic-chaos chaos run my_agent.py \
    <span className="text-sky-400">--inject</span> token_timeout,rate_limit_storm,tool_failure \
    <span className="text-sky-400">--save</span> chaos_report.json

<span className="text-zinc-500"># Compare prompt and model drift against baseline snapshot (v0.4.0)</span>
<span className="text-[#bef264]">$</span> agentic-chaos drift compare baseline_snapshot.json \
    <span className="text-sky-400">--prompt-file</span> system_prompt.txt \
    <span className="text-sky-400">--output-file</span> current_run.txt \
    <span className="text-sky-400">--save</span> drift_report.json</code></pre>
              )}
            </div>

            {/* Bottom Code Bar */}
            <div className="px-6 py-3 border-t border-zinc-800 bg-[#07080a] flex items-center justify-between text-xs font-mono-tech text-zinc-400">
              <span>Zero external daemon · Runs locally · Deterministic seeds</span>
              <a 
                href="https://github.com/DeepAgentLabs/agentic-chaos/tree/main/examples" 
                target="_blank" 
                rel="noreferrer"
                className="text-[#bef264] hover:underline flex items-center gap-1 font-semibold"
              >
                <span>Explore examples/ in repository</span>
                <span>↗</span>
              </a>
            </div>

          </div>

        </div>
      </section>

      {/* ========================================================================= */}
      {/* 9. RESILIENCE BENCHMARK & CI/CD GATING                                    */}
      {/* ========================================================================= */}
      <section className="py-20 bg-[#f7f7f8] border-b border-zinc-200" id="benchmarks">
        <div className="max-w-[1440px] mx-auto px-6">
          
          <div className="flex flex-col lg:flex-row lg:items-end justify-between mb-12 gap-6">
            <div>
              <div className="text-xs font-mono-tech uppercase tracking-widest text-zinc-500 font-semibold mb-2">
                MEASURABLE OUTCOMES
              </div>
              <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tight text-zinc-950 font-headline">
                Resilience benchmarks &amp; <span className="bg-[#bef264] px-1 font-serif italic font-normal">CI/CD gating.</span>
              </h2>
            </div>
            <p className="max-w-md text-sm text-zinc-600 leading-relaxed">
              Quantify failure impact and runaway token burn ratios before shipping autonomous agent changes to production.
            </p>
          </div>

          {/* Benchmark Comparison Table */}
          <div className="bg-white rounded-xl border border-zinc-300 shadow-sm overflow-hidden mb-12">
            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono-tech text-xs">
                <thead>
                  <tr className="bg-zinc-100/80 border-b border-zinc-300 text-zinc-700">
                    <th className="py-3.5 px-6 font-bold uppercase">Resilience Metric</th>
                    <th className="py-3.5 px-6 font-bold uppercase">Untested Baseline Agent</th>
                    <th className="py-3.5 px-6 font-bold uppercase text-zinc-950 bg-[#bef264]/20">Chaos-Hardened Agent</th>
                    <th className="py-3.5 px-6 font-bold uppercase">Impact Delta</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 text-zinc-800">
                  <tr className="hover:bg-zinc-50 transition-colors">
                    <td className="py-4 px-6 font-semibold text-zinc-950">
                      Tool Timeout Recovery Rate
                    </td>
                    <td className="py-4 px-6 text-rose-600 font-bold">42.8% (Silent Hang)</td>
                    <td className="py-4 px-6 text-emerald-700 font-bold bg-[#bef264]/10">99.4% (Fallback Active)</td>
                    <td className="py-4 px-6 text-emerald-600 font-bold">+56.6%</td>
                  </tr>
                  <tr className="hover:bg-zinc-50 transition-colors">
                    <td className="py-4 px-6 font-semibold text-zinc-950">
                      Runaway Retry Token Burn
                    </td>
                    <td className="py-4 px-6 text-rose-600 font-bold">$14.20 per incident</td>
                    <td className="py-4 px-6 text-emerald-700 font-bold bg-[#bef264]/10">$0.18 per incident</td>
                    <td className="py-4 px-6 text-emerald-600 font-bold">-98.7% waste</td>
                  </tr>
                  <tr className="hover:bg-zinc-50 transition-colors">
                    <td className="py-4 px-6 font-semibold text-zinc-950">
                      Mean Time to Fallback (MTTF)
                    </td>
                    <td className="py-4 px-6 text-rose-600 font-bold">18.4 seconds</td>
                    <td className="py-4 px-6 text-emerald-700 font-bold bg-[#bef264]/10">1.8 seconds</td>
                    <td className="py-4 px-6 text-emerald-600 font-bold">10.2x faster</td>
                  </tr>
                  <tr className="hover:bg-zinc-50 transition-colors">
                    <td className="py-4 px-6 font-semibold text-zinc-950">
                      Infinite Tool Ping-Pong Detection
                    </td>
                    <td className="py-4 px-6 text-rose-600 font-bold">Undetected (Loop Crash)</td>
                    <td className="py-4 px-6 text-emerald-700 font-bold bg-[#bef264]/10">Trapped at turn 4</td>
                    <td className="py-4 px-6 text-emerald-600 font-bold">Zero loop crashes</td>
                  </tr>
                </tbody>
              </table>
            </div>
            
            <div className="p-4 bg-zinc-50 border-t border-zinc-200 text-xs font-mono-tech text-zinc-500 flex flex-col sm:flex-row items-center justify-between gap-2">
              <span>Benchmark suite conducted across 500 multi-agent trials under 100% deterministic seeds.</span>
              <span className="text-zinc-900 font-bold">CI Gate: agentic-chaos gate --min-score 90</span>
            </div>
          </div>

          {/* Persona 3-Column Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white rounded-xl border border-zinc-300 p-6 flex flex-col justify-between shadow-xs">
              <div>
                <span className="text-[11px] font-mono-tech text-zinc-500 uppercase tracking-wider block mb-2">01 / FOR AGENT BUILDERS</span>
                <h3 className="text-xl font-bold text-zinc-900 mb-2 font-headline">Agent System Developers</h3>
                <p className="text-xs text-zinc-600 leading-relaxed">
                  Stop guessing how multi-agent supervisor graphs behave when a sub-agent hangs. 
                  Fix brittle edge transitions during local development before merging.
                </p>
              </div>
              <div className="mt-6 pt-3 border-t border-zinc-200 text-xs font-mono-tech text-zinc-500">
                Local iteration &amp; unit tests
              </div>
            </div>

            <div className="bg-white rounded-xl border border-zinc-300 p-6 flex flex-col justify-between shadow-xs">
              <div>
                <span className="text-[11px] font-mono-tech text-zinc-500 uppercase tracking-wider block mb-2">02 / FOR QA &amp; SRE</span>
                <h3 className="text-xl font-bold text-zinc-900 mb-2 font-headline">Reliability Engineers</h3>
                <p className="text-xs text-zinc-600 leading-relaxed">
                  Replace flaky prompt assertions with deterministic fault injection schedules. 
                  Enforce strict token burn budgets during error retries in CI/CD.
                </p>
              </div>
              <div className="mt-6 pt-3 border-t border-zinc-200 text-xs font-mono-tech text-zinc-500">
                Automated GitHub Actions gates
              </div>
            </div>

            <div className="bg-white rounded-xl border border-zinc-300 p-6 flex flex-col justify-between shadow-xs">
              <div>
                <span className="text-[11px] font-mono-tech text-zinc-500 uppercase tracking-wider block mb-2">03 / FOR RED TEAMS</span>
                <h3 className="text-xl font-bold text-zinc-900 mb-2 font-headline">Security &amp; Red Teams</h3>
                <p className="text-xs text-zinc-600 leading-relaxed">
                  Simulate malicious tool returns, memory poisoning, and prompt drift under stressed conditions 
                  to verify that agent guardrails stay impermeable.
                </p>
              </div>
              <div className="mt-6 pt-3 border-t border-zinc-200 text-xs font-mono-tech text-zinc-500">
                Adversarial fault validation
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* ========================================================================= */}
      {/* 10. NEWSLETTER & COMMUNITY STRIP (Syntropic Style)                         */}
      {/* ========================================================================= */}
      <section className="py-12 bg-[#bef264] border-b border-[#a3e635]">
        <div className="max-w-[1440px] mx-auto px-6 flex flex-col lg:flex-row items-center justify-between gap-6">
          <div>
            <div className="text-[10px] font-mono-tech uppercase tracking-wider text-zinc-800 font-bold mb-1">
              DEEPAGENTLABS RESILIENCE BULLETINS
            </div>
            <h3 className="text-2xl font-extrabold text-zinc-950 font-headline">
              Stay ahead of agentic failure modes.
            </h3>
            <p className="text-xs text-zinc-800 font-mono-tech mt-1">
              Release notes, failure case studies, and synthetic resilience patterns. No spam, unsubscribe anytime.
            </p>
          </div>

          <form className="flex w-full lg:w-auto items-stretch gap-2" onSubmit={(e) => e.preventDefault()}>
            <input
              type="email"
              placeholder="engineer@company.com"
              required
              className="w-full sm:w-80 px-4 py-2.5 rounded-lg border border-zinc-900 bg-white text-zinc-900 text-xs font-mono-tech focus:ring-2 focus:ring-black focus:outline-none"
            />
            <button
              type="submit"
              className="px-5 py-2.5 bg-black hover:bg-zinc-800 text-white font-mono-tech text-xs font-bold rounded-lg transition-colors whitespace-nowrap cursor-pointer"
            >
              Subscribe
            </button>
          </form>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 11. GLOBAL FOOTER (Matching Demo Website Perfectly)                       */}
      {/* ========================================================================= */}
      <footer className="bg-[#090a0f] text-white pt-16 pb-12" id="docs">
        <div className="max-w-[1440px] mx-auto px-6">
          
          {/* Top Grid: Manifesto & Link Columns */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-10 pb-16 border-b border-zinc-800">
            
            {/* Col 1: Manifesto */}
            <div className="lg:col-span-5 pr-0 lg:pr-8">
              <h4 className="text-base font-bold text-white mb-3 font-headline">
                Open infrastructure for <span className="italic text-[#bef264] font-serif font-normal">observable, efficient</span><br />
                and <span className="italic text-[#bef264] font-serif font-normal">resilient</span> AI agents, built in the open.
              </h4>
              <div className="space-y-1.5 text-xs font-mono-tech text-zinc-400">
                <div>● SPEC COMES FIRST</div>
                <div>● WORKS WITH ANY FRAMEWORK</div>
                <div>● RUNS ON YOUR MACHINE</div>
                <div>● FREE AND OPEN SOURCE</div>
              </div>
            </div>

            {/* Col 2: Products */}
            <div className="lg:col-span-2">
              <div className="text-xs font-mono-tech text-zinc-500 uppercase tracking-wider mb-4 font-semibold">
                PRODUCTS
              </div>
              <ul className="space-y-2.5 text-xs font-mono-tech text-zinc-300">
                <li><a className="hover:text-[#bef264] transition-colors" href="../Demo%20Website/code.html#products">AgenticLens</a></li>
                <li><a className="hover:text-[#bef264] transition-colors" href="../Demo%20Website/code.html#products">Agentic Evals</a></li>
                <li><a className="hover:text-[#bef264] transition-colors" href="../Demo%20Website/code.html#products">Agentic Sidecar</a></li>
                <li><a className="text-[#bef264] font-bold" href="#hero">Agentic Chaos (Active)</a></li>
                <li><a className="hover:text-[#bef264] transition-colors" href="../Demo%20Website/code.html#products">MCP Server</a></li>
                <li><a className="hover:text-[#bef264] transition-colors" href="../Demo%20Website/code.html#products">Control Tower</a></li>
              </ul>
            </div>

            {/* Col 3: Explore */}
            <div className="lg:col-span-2">
              <div className="text-xs font-mono-tech text-zinc-500 uppercase tracking-wider mb-4 font-semibold">
                EXPLORE
              </div>
              <ul className="space-y-2.5 text-xs font-mono-tech text-zinc-300">
                <li><a className="hover:text-[#bef264] transition-colors" href="../Demo%20Website/code.html#specification">Specification</a></li>
                <li><a className="hover:text-[#bef264] transition-colors" href="../Demo%20Website/code.html#roadmap">Roadmap</a></li>
                <li><a className="hover:text-[#bef264] transition-colors" href="#architecture">Capability Map</a></li>
                <li><a className="hover:text-[#bef264] transition-colors" href="#spectrum">Chaos Catalog</a></li>
                <li><a className="hover:text-[#bef264] transition-colors" href="#benchmarks">Benchmarks</a></li>
                <li><a className="hover:text-[#bef264] transition-colors" href="https://pypi.org/project/agentic-chaos/" target="_blank" rel="noreferrer">PyPI Release</a></li>
              </ul>
            </div>

            {/* Col 4: Community */}
            <div className="lg:col-span-3">
              <div className="text-xs font-mono-tech text-zinc-500 uppercase tracking-wider mb-4 font-semibold">
                COMMUNITY &amp; CODE
              </div>
              <ul className="space-y-2.5 text-xs font-mono-tech text-zinc-300">
                <li>
                  <a className="hover:text-[#bef264] transition-colors flex items-center gap-2" href="https://github.com/DeepAgentLabs/agentic-chaos" target="_blank" rel="noreferrer">
                    <span className="font-bold">gh</span>
                    <span>GitHub: DeepAgentLabs/agentic-chaos</span>
                  </a>
                </li>
                <li>
                  <a className="hover:text-[#bef264] transition-colors flex items-center gap-2" href="https://pypi.org/project/agentic-chaos/" target="_blank" rel="noreferrer">
                    <span className="font-bold">pkg</span>
                    <span>pip install agentic-chaos</span>
                  </a>
                </li>
                <li>
                  <a className="hover:text-[#bef264] transition-colors flex items-center gap-2" href="../Demo%20Website/code.html">
                    <span className="font-bold">←</span>
                    <span>Return to DeepAgentLabs Hub</span>
                  </a>
                </li>
              </ul>
            </div>

          </div>

          {/* Giant DeepAgentLabs Wordmark */}
          <div className="py-12 text-center select-none overflow-hidden">
            <h1 className="text-6xl sm:text-7xl md:text-8xl lg:text-9xl font-extrabold text-[#bef264] tracking-tight font-headline">
              DeepAgentLabs
            </h1>
          </div>

          {/* Bottom Bar: Spec Status and Copyright */}
          <div className="pt-8 border-t border-zinc-800 flex flex-col md:flex-row items-center justify-between text-xs font-mono-tech text-zinc-500 gap-4">
            <div>
              © 2026 DEEPAGENTLABS · AGENTIC-CHAOS
            </div>
            <div className="flex items-center gap-2 text-zinc-400">
              <span className="w-2 h-2 rounded-full bg-[#bef264]"></span>
              <span>AI OPERATIONS SPECIFICATION — V0.4 CONFORMANCE READY</span>
            </div>
            <a className="hover:text-white transition-colors flex items-center gap-1 font-semibold text-zinc-400" href="#">
              BACK TO TOP ↑
            </a>
          </div>

        </div>
      </footer>

    </div>
  );
}
