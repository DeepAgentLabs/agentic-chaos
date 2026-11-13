# Quickstart

**Stress-test: How does the application behave when a dependency fails?**

**Input:** A wrapped callable or experiment target plus fault configuration.  
**Output:** Fault events, experiment reports, and resilience evidence.

## Install and inspect available faults

```
python -m pip install agentic-chaos
agentic-chaos chaos list-faults
```

## Create a local target

chaos_quickstart.py · complete file

```python
from agentic_chaos.chaos import chaos_call, TokenTimeoutError

def search(question):
    return [f"Document about {question}"]

try:
    result = chaos_call(search, "refund policy", faults=["token_timeout"], step_name="Search")
except TokenTimeoutError:
    result = []
print("Search result:", result)
```

[Download chaos_quickstart.py](examples/chaos_quickstart.py)

## Compare normal execution with injected failure

```
python chaos_quickstart.py
agentic-chaos chaos run chaos_quickstart.py --inject token_timeout --save chaos_run.json
```

**Expected:** the normal run returns a document. Under the timeout fault, the script catches the timeout and prints an empty result. A chaos report records the injected event.

An empty result is an observed recovery weakness, not a resilience pass. Decide what a useful fallback should return, implement it, and repeat the experiment.

## Connect real code

Wrap the callable whose failure you want to study. Establish the normal baseline, then inject a single fault before combining scenarios. Keep tests bounded and use a controlled test target.

[Configure experiments ↗](../configuration.md)[Read reports ↗](../output-formats.md)
