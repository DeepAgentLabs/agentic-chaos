# Features

This page documents every capability implemented in the current release (**v0.4.0**). Planned work is listed only in the [Roadmap](roadmap.md).

!!! info "Status labels"
    The package is classified **Alpha** on PyPI. Every capability below is therefore labeled **Experimental**. Maintainers can promote individual capabilities to **Stable** once their interfaces are frozen.

| Capability | Since | Status | Python API | CLI |
| --- | --- | --- | --- | --- |
| [Chaos sessions and `chaos_call()`](#chaos-sessions-and-chaos_call) | v0.1 | Experimental | Yes | Yes |
| [Token timeout](#token-timeout) | v0.1 | Experimental | Yes | Yes |
| [Rate-limit storm](#rate-limit-storm) | v0.1 | Experimental | Yes | Yes |
| [Silent degradation](#silent-degradation) | v0.1 | Experimental | Yes | Yes |
| [Tool-call failure](#tool-call-failure) | v0.2 | Experimental | Yes | Yes |
| [Memory corruption](#memory-corruption) | v0.2 | Experimental | Yes | Yes |
| [Infinite loop](#infinite-loop) | v0.2 | Experimental | Yes | Yes |
| [Tool and node wrapping, topology](#tool-and-node-wrapping-and-topology) | v0.2 | Experimental | Yes | n/a |
| [Handoff corruption](#handoff-corruption) | v0.3.0 | Experimental | Yes | Yes |
| [Fidelity judges](#fidelity-judges) | v0.3.0 | Experimental | Yes | n/a |
| [Drift detector](#drift-detector) | v0.4.0 | Experimental | Yes | Yes |
| [Fault listing](#fault-listing) | v0.1 | Experimental | n/a | Yes |
| [AgenticLens integration](#agenticlens-integration) | v0.1 | Experimental | Yes | n/a |

## Installation

```bash
pip install agentic-chaos
```

From source:

```bash
git clone https://github.com/DeepAgentLabs/agentic-chaos.git
cd agentic-chaos
uv sync --extra dev --frozen
```

Requires Python 3.10 or newer. No other package is required. See [Troubleshooting](troubleshooting.md#uv-sync-fails-because-of-the-agenticlens-extra) for why `--frozen` matters.

---

## Chaos sessions and `chaos_call()`

**What it does.** `chaos_call(fn, *args, faults=[...], **kwargs)` runs `fn` through the active fault. `chaos_session([...])` turns faults on for a block of code and records a `ChaosEvent` for every injection. Outside a session, `chaos_call()` is a transparent pass-through, so instrumented code is safe to ship.

**Status.** Experimental.

**Enable and configure.** Wrap the call, then activate chaos with `chaos_session()` or the CLI. With more than one fault in a session, pass `faults=[...]` at each call site.

**Inputs and outputs.** Input: a callable, its arguments, optional fault names, optional `step_id` / `step_name` for correlation. Output: the callable's result, or the fault's exception. Events are in `session.events`.

**Minimal example.**

```python
from agentic_chaos.chaos import chaos_call, chaos_session, TokenTimeoutError

with chaos_session(["token_timeout"]) as session:
    try:
        chunks = chaos_call(retriever.search, user_question, faults=["token_timeout"])
    except TokenTimeoutError:
        chunks = []

print(session.events)
```

**CLI.**

```bash
agentic-chaos chaos run my_app.py --inject token_timeout,rate_limit_storm --save chaos_run.json
```

**Limitations.** Only wrapped calls are affected. See [Limitations](limitations.md).

**Related.** [Output Formats](output-formats.md), [Examples](examples.md).

---

## Token timeout

**What it does.** Simulates a client-side timeout on a hung or slow completion. It hangs for `hang_seconds` (default `2.0`) and raises `TokenTimeoutError`. With `mode="delay"` the real call completes late instead of erroring (outcome `"delayed"`).

**Why it is useful.** Finds code paths with no timeout handling, and separately measures the UX cost of slow-but-successful calls.

**Status.** Experimental.

**Configure.** `TokenTimeoutFault(hang_seconds=..., mode=...)`. CLI name: `token_timeout`.

**Inputs and outputs.** Input: any callable. Output: `TokenTimeoutError`, or the real result after a delay; event outcome `errored` or `delayed`.

**Minimal example.**

```python
from agentic_chaos.chaos import chaos_session, chaos_call, TokenTimeoutFault

with chaos_session([TokenTimeoutFault(hang_seconds=0.2, mode="delay")]) as session:
    chaos_call(llm.complete, "hello", faults=["token_timeout"])
print(session.events[0].outcome)  # delayed
```

**Limitations.** Implemented as a real wait, so it slows the process by `hang_seconds`.

**Runnable demo.** `examples/chaos_advanced_faults_demo.py`.

---

## Rate-limit storm

**What it does.** Raises `RateLimitStormError` (with a `retry_after` hint) for the first `burst_count` calls (default `3`), then passes calls through. Simulates a provider 429 cascade that eventually clears.

**Why it is useful.** Verifies retry and backoff logic.

**Status.** Experimental.

**Configure.** `RateLimitStormFault(burst_count=...)`. CLI name: `rate_limit_storm`.

**Minimal example.**

```python
from agentic_chaos.chaos import chaos_session, RateLimitStormFault

with chaos_session([RateLimitStormFault(burst_count=1)]):
    ...
```

**Limitations.** A deterministic burst, not a random or time-windowed pattern.

---

## Silent degradation

**What it does.** Calls the real function, then corrupts its text (`.content`, `.text`, or a raw string) while preserving latency and token counts. Nothing in cost or latency telemetry looks wrong, which makes this the hardest failure to detect.

**Status.** Experimental.

**Configure.** `SilentDegradationFault(degrade_fn=my_fn)` replaces the built-in corruption, where `my_fn(result) -> corrupted_result`. CLI name: `silent_degradation`.

**Minimal example.**

```python
from agentic_chaos import SilentDegradationFault, chaos_call, chaos_session

with chaos_session([SilentDegradationFault()]):
    answer = chaos_call(agent.answer, "What changed?", faults=["silent_degradation"])
```

**Limitations.** Built-in corruption supports only the listed text shapes. Use `degrade_fn` for others.

**Related.** [Fidelity judges](#fidelity-judges) quantify whether the output got worse.

---

## Tool-call failure

**What it does.** Forces a tool call to fail by raising an error (`"error"`), timing out (`"timeout"`), or returning null (`"empty"`).

**Status.** Experimental.

**Configure.** `ToolCallFailureFault(tool_name="search")` targets one tool; `tool_name=None` targets all. CLI name: `tool_failure`.

**Inputs and outputs.** Input: a tool wrapped with `wrap_tool()`. Output: the failure mode's behavior; non-matching tools pass through.

**Minimal example.** See [Tool and node wrapping](#tool-and-node-wrapping-and-topology).

**CLI.**

```bash
agentic-chaos agent run my_agent.py --inject tool_failure --save report.json
```

**Limitations.** Matches by tool name; unwrapped tools are not affected.

---

## Memory corruption

**What it does.** Corrupts shared agent state with one of four modes: `"truncate"` (cut to half), `"inject"` (insert garbage), `"garble"` (replace text with random letters), `"decay"` (progressively worsen state across turns).

**Status.** Experimental.

**Configure.** `MemoryCorruptionFault(mode=..., seed=None, rate=0.25)`. CLI name: `memory_corruption`.

Modes: `"truncate"` (cut to half), `"inject"` (insert garbage), `"garble"` (replace text), `"decay"` (progressively worsen across turns — `rate` controls how fast).

**Minimal example.**

```python
from agentic_chaos import MemoryCorruptionFault, chaos_call, chaos_session

def read_memory(key: str) -> str:
    return f"Memory[{key}]: Customer is a premium member."

with chaos_session([MemoryCorruptionFault(mode="garble", seed=42)]) as session:
    result = chaos_call(read_memory, "customer_profile",
                        step_name="memory_read", faults=["memory_corruption"])
    print(result)  # garbled text

print(session.events[0].outcome)  # degraded
```

**CLI.**

```bash
agentic-chaos agent run my_agent.py --inject memory_corruption --save report.json
```

**Limitations.** Only affects state exposed to the fault. See [Limitations](limitations.md).

---

## Infinite loop

**What it does.** Replaces the agent's return value with a "continue" signal for `force_turns` calls, then passes through. Tests whether the agent has turn-limit safeguards.

**Status.** Experimental.

**Configure.** CLI name: `infinite_loop`; parameter `force_turns`.

**CLI.**

```bash
agentic-chaos agent run my_agent.py --inject infinite_loop --save report.json
```

**Limitations.** Your agent must interpret the continue signal for the test to be meaningful.

**Runnable demo.** `examples/chaos_agent_failure_demo.py` (covers tool failure, memory corruption and infinite loop).

---

## Tool and node wrapping and topology

**What it does.** `wrap_tool()` and `wrap_node()` wrap functions for transparent chaos injection. `TopologyTracker` records nodes and edges as wrapped functions are called.

**Status.** Experimental.

**Inputs and outputs.** Input: the function plus `tool_name`, `tracker`, `caller_node`. Output: a wrapped callable; `tracker.topology.as_json()` returns nodes and edges.

**Minimal example.**

```python
from agentic_chaos import ToolCallFailureFault, TopologyTracker, chaos_session, wrap_tool

tracker = TopologyTracker()
tracker.register_node("SupportAgent", type="agent")

search = wrap_tool(search_fn, tool_name="search", tracker=tracker, caller_node="SupportAgent")
refund = wrap_tool(refund_fn, tool_name="refund", tracker=tracker, caller_node="SupportAgent")

with chaos_session([ToolCallFailureFault(tool_name="search")]):
    search("order #123")   # fault fires
    refund("123")          # passes through

print(tracker.topology.as_json())
```

---

## Handoff corruption

**What it does.** Targets a topology **edge** (a handoff between agents) rather than a node. Modes: `"corrupt"` garbles the payload in transit, `"drop"` prevents delivery, `"delay"` delivers late.

**Status.** Experimental.

**Configure.** CLI name: `handoff_corruption`. Requires edges recorded by a `TopologyTracker`.

**CLI.**

```bash
agentic-chaos agent run my_agent.py --inject handoff_corruption --save report.json
```

**Limitations.** Edges that were never registered cannot be targeted.

**Runnable demo.** `examples/chaos_handoff_and_judges_demo.py`.

---

## Fidelity judges

**What it does.** Answers the question a raw fault event cannot: did the corrupted output actually get worse? A judge scores each event from `0.0` to `1.0` into `event.fidelity_score`.

**Judges.** `HeuristicJudge` (in-core, zero dependencies), `DeepEvalJudge` and `PydanticEvalsJudge` (adapters around evaluator objects you construct).

**Status.** Experimental.

**Minimal example.**

```python
from agentic_chaos import HeuristicJudge, SilentDegradationFault, chaos_call, chaos_session, fidelity_session

with fidelity_session(HeuristicJudge()):
    with chaos_session([SilentDegradationFault()]) as session:
        answer = chaos_call(agent.answer, "What changed?", faults=["silent_degradation"])

print(session.events[0].fidelity_score)  # 0.0 - 1.0
```

**Limitations.** A heuristic signal, not ground truth. For pure downstream functions, capture a baseline manually (see the handoff-and-judges demo).

**Related.** [Integrations](integrations.md#fidelity-judge-adapters).

---

## Drift detector

**What it does.** Captures a local baseline snapshot of a prompt, model metadata, output and retrieval results, then compares later runs against it to detect silent change.

**Status.** Experimental (new in v0.4.0).

**Signals.**

| Signal | Based on |
| --- | --- |
| Prompt drift | Hash and inline diff metadata. |
| Model drift | Model name, provider fingerprint, embedding-model metadata. |
| Output drift | Lightweight text-distance score vs. the baseline. |
| Retrieval drift | Set distance on fixed retrieval results. |

**Inputs.** Files and metadata you provide: `--prompt-file`, `--output-file`, `--retrieval-file`, `--model`, `--model-fingerprint`, and for snapshots `--name`, `--save`, `--embedding-model`.

**Outputs.** A baseline JSON (`snapshot --save`), a drift report JSON (`compare --save`), an optional state file, and an exit code: **`2` when drift is detected**.

**Minimal example.**

```bash
agentic-chaos drift snapshot --name support-agent --save baseline.json \
  --prompt-file prompt.txt --model gpt-5-mini --model-fingerprint fp-a

agentic-chaos drift compare baseline.json --prompt-file prompt.txt \
  --output-file answer.txt --model gpt-5-mini --model-fingerprint fp-b \
  --save drift_report.json
```

**Advanced: quiet scheduled runs.**

```bash
agentic-chaos drift compare baseline.json \
  --prompt-file prompt.txt --output-file current_output.txt \
  --save drift_report.json \
  --state-path .agentic-chaos/drift-state.json \
  --cooldown-minutes 1440 \
  --emit-only-on-change
```

**Limitations.** No scheduler built in; the drift module does not call a model itself. See [Limitations](limitations.md#drift-detector).

**Related.** Scheduled CI example in [Integrations](integrations.md#continuous-integration). Demo: `examples/drift_detection_demo.py`.

---

## Fault listing

```bash
agentic-chaos chaos list-faults
```

Lists the fault types available for `--inject`. Use it to confirm exact names for your installed version.

---

## AgenticLens integration

**What it does.** Merges chaos events onto an AgenticLens `Workflow` so `agenticlens analyze` reports cost, latency and chaos impact together.

**Status.** Experimental. Optional extra: `pip install agentic-chaos[agenticlens]`.

**Inputs and outputs.** Input: a chaos session and an AgenticLens workflow. Output: a workflow JSON with `chaos_events`.

**Minimal example and details.** See [Integrations](integrations.md#agenticlens).

**Limitations.** The extra resolves from a sibling checkout in the source repository until AgenticLens publishes a compatible release.
