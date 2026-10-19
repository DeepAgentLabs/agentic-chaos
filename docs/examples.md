# Examples

!!! info
    The repository ships runnable scripts in `examples/`. Every recipe on this page is verified against v0.4.0.

The repository ships runnable scripts in [`examples/`](https://github.com/DeepAgentLabs/agentic-chaos/tree/main/examples). This page summarizes each one and adds short recipes you can copy.

## Bundled scripts

| Script | Needs | Shows |
| --- | --- | --- |
| `chaos_customer_support_demo.py` | `agentic_chaos` only | All three v0.1 faults in one flow: a rate-limit storm the app retries through, a token timeout it does not handle, and a silent degradation. |
| `chaos_advanced_faults_demo.py` | `agentic_chaos` only | `TokenTimeoutFault(mode="delay")` and a custom `SilentDegradationFault(degrade_fn=...)`. |
| `chaos_agent_failure_demo.py` | `agentic_chaos` only | The v0.2 agent faults (tool-call failure, memory corruption, infinite loop), plus `wrap_tool()` and `TopologyTracker`. |
| `chaos_handoff_and_judges_demo.py` | `agentic_chaos` only | Edge-scoped handoff corruption and a manual baseline capture so `fidelity_session()` can score the event. |
| `drift_detection_demo.py` | `agentic_chaos` only | Creates a drift baseline and a current snapshot, compares them, and writes a drift report JSON. |
| `chaos_with_agenticlens_demo.py` | `agentic-chaos[agenticlens]` | The optional AgenticLens integration: `attach_events()` and `step_kwargs()`. |

Run any of them directly:

```bash
uv run python examples/chaos_customer_support_demo.py
```

Or run the first two under the CLI:

```bash
uv run agentic-chaos chaos run examples/chaos_customer_support_demo.py \
    --inject rate_limit_storm,token_timeout,silent_degradation \
    --save /tmp/chaos_run.json
```

## Recipe 1: find an unhandled timeout

Wrap the call, run it under chaos, and see whether anything catches the failure.

```python
from agentic_chaos.chaos import chaos_call, TokenTimeoutError

try:
    chunks = chaos_call(retriever.search, user_question, faults=["token_timeout"])
except TokenTimeoutError:
    chunks = []  # no fallback handled it: this is what we want to find
```

```bash
agentic-chaos chaos run my_app.py --inject token_timeout --save chaos_run.json
```

Outside a chaos session, `chaos_call()` is a transparent pass-through, so this instrumented code is safe to ship.

## Recipe 2: tune fault parameters

```python
from agentic_chaos.chaos import chaos_session, TokenTimeoutFault, RateLimitStormFault

with chaos_session([TokenTimeoutFault(hang_seconds=5.0), RateLimitStormFault(burst_count=1)]):
    ...
```

With more than one fault in a session, each `chaos_call()` must say which applies:

```python
chaos_call(llm.complete, prompt, faults=["rate_limit_storm"])
```

## Recipe 3: test retry logic against a rate-limit storm

`RateLimitStormFault` raises `RateLimitStormError` (with a `retry_after` hint) for the first `burst_count` calls, then passes through. That makes it a good test for backoff code.

```python
import time
from agentic_chaos.chaos import chaos_call, chaos_session, RateLimitStormFault, RateLimitStormError

def call_with_retry(fn, *args, attempts=5, delay=0.1):
    for _ in range(attempts):
        try:
            return chaos_call(fn, *args, faults=["rate_limit_storm"])
        except RateLimitStormError:
            time.sleep(delay)
    raise RuntimeError("gave up")

with chaos_session([RateLimitStormFault(burst_count=3)]):
    result = call_with_retry(llm.complete, "hello")
```

!!! note
    `RateLimitStormError` carries a `retry_after: float` attribute (the value you configured on `RateLimitStormFault`). You can use it to drive backoff sleep duration.

## Recipe 4: a slow but successful call

```python
from agentic_chaos.chaos import chaos_session, chaos_call, TokenTimeoutFault

with chaos_session([TokenTimeoutFault(hang_seconds=3.0, mode="delay")]) as session:
    answer = chaos_call(llm.complete, "hello", faults=["token_timeout"])

print(session.events[0].outcome)  # "delayed"
```

## Recipe 5: custom silent corruption

Simulate a narrow, realistic bug instead of wholesale noise.

```python
from agentic_chaos.chaos import chaos_session, chaos_call, SilentDegradationFault

def drop_last_sentence(text):
    return text.rsplit(".", 2)[0] + "."

with chaos_session([SilentDegradationFault(degrade_fn=drop_last_sentence)]):
    answer = chaos_call(llm.complete, "Summarize the policy", faults=["silent_degradation"])
```

## Recipe 6: tool failure on one tool only

```python
from agentic_chaos import ToolCallFailureFault, TopologyTracker, chaos_session, wrap_tool

tracker = TopologyTracker()
tracker.register_node("SupportAgent", type="agent")

search = wrap_tool(search_fn, tool_name="search", tracker=tracker, caller_node="SupportAgent")
refund = wrap_tool(refund_fn, tool_name="refund", tracker=tracker, caller_node="SupportAgent")

with chaos_session([ToolCallFailureFault(tool_name="search")]):
    search("order #123")  # fault fires
    refund("123")         # passes through

print(tracker.topology.as_json())
```

## Recipe 7: score whether corruption hurt quality

```python
from agentic_chaos import HeuristicJudge, SilentDegradationFault, chaos_call, chaos_session, fidelity_session

with fidelity_session(HeuristicJudge()):
    with chaos_session([SilentDegradationFault()]) as session:
        answer = chaos_call(agent.answer, "What changed?", faults=["silent_degradation"])

print(session.events[0].fidelity_score)  # 0.0 - 1.0
```

## Recipe 8: agent-level faults from the CLI

```bash
agentic-chaos agent run my_agent.py --inject tool_failure,memory_corruption --save report.json
agentic-chaos agent run my_agent.py --inject handoff_corruption --save report.json
```

## Recipe 9: detect prompt and model drift

```bash
agentic-chaos drift snapshot \
  --name support-agent \
  --save baseline.json \
  --prompt-file prompt.txt \
  --output-file baseline_output.txt \
  --model gpt-5-mini \
  --model-fingerprint provider-fp-001

agentic-chaos drift compare baseline.json \
  --prompt-file prompt.txt \
  --output-file current_output.txt \
  --model gpt-5-mini \
  --model-fingerprint provider-fp-002 \
  --save drift_report.json
echo "exit code: $?"   # 2 when drift is detected
```

## Where to go next

- [Features](features.md) for what each fault does.
- [Output Formats](output-formats.md) for reading the saved reports.
- [Integrations](integrations.md) for the AgenticLens workflow.
