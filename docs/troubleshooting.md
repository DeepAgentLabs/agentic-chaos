# Troubleshooting

## Installation

### `uv sync` fails because of the agenticlens extra

**Symptom:** `uv sync` errors out about a missing sibling `agenticlens` directory.

**Cause:** `pyproject.toml` points the (currently unpublished) `agenticlens` extra at a sibling checkout through `[tool.uv.sources]`. Without `--frozen`, `uv sync` validates the entire lock, including extras you did not ask for.

**Fix:** install from the committed lock file:

```bash
uv sync --extra dev --frozen
uv run --frozen pytest
```

Drop `--frozen` only when you are working on the AgenticLens integration and have cloned it next to this repository:

```bash
git clone https://github.com/DeepAgentLabs/agenticlens.git ../agenticlens
uv sync --extra dev --extra agenticlens
```

### `ModuleNotFoundError: agenticlens`

You imported `agentic_chaos.integrations.agenticlens` without the extra. Install it:

```bash
pip install agentic-chaos[agenticlens]
```

In the source repository, tests for this module skip automatically when `agenticlens` is missing.

## Running faults

### Nothing happens when I run my code

`chaos_call()` is a pass-through outside a chaos session. Faults only fire when:

- the script is run with `agentic-chaos chaos run ... --inject <fault>`, or
- the call executes inside `with chaos_session([...]):`.

Also check that the fault you are injecting is applicable to the call site (for example, `tool_failure` with `tool_name="search"` only affects a tool named `search`).

### An error about multiple faults at a call site

When more than one fault is configured for a session, `chaos_call()` will not guess which one applies. Name it explicitly:

```python
chaos_call(fn, arg, faults=["token_timeout"])
```

### The rate-limit storm stops after a few calls

That is intended. `RateLimitStormFault` raises for the first `burst_count` calls (default 3) and then passes through, simulating a storm that eventually clears. Increase `burst_count` to extend it.

### `token_timeout` makes my tests slow

The fault hangs for `hang_seconds` (default 2.0) before raising. Lower it in tests:

```python
TokenTimeoutFault(hang_seconds=0.1)
```

### Silent degradation did not change my output

The built-in corruption works on text content: `.content`, `.text`, or a raw string. If your function returns another shape (for example a nested dict), supply your own corruption logic:

```python
SilentDegradationFault(degrade_fn=my_fn)  # my_fn(result) -> corrupted_result
```

### `fidelity_score` is missing

Scores are only computed inside a `fidelity_session(...)`, and the judge needs a baseline to compare against. For pure downstream functions, capture the baseline manually as shown in [`examples/chaos_handoff_and_judges_demo.py`](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/examples/chaos_handoff_and_judges_demo.py).

### My tool wrapper is not failing

Check that `tool_name` on `wrap_tool()` matches the `tool_name` on `ToolCallFailureFault`. A fault with `tool_name=None` targets all tools.

## CLI

### `agentic-chaos: command not found`

Activate the environment you installed into, or run through uv:

```bash
uv run agentic-chaos chaos list-faults
```

### Unknown fault name

Use `chaos list-faults` to see valid `--inject` names:

```bash
agentic-chaos chaos list-faults
```

### `drift compare` fails my CI job

`agentic-chaos drift compare` exits with code `2` when drift is detected. This is intended, so a CI job can fail on drift. If you only want the report, allow that exit code in your pipeline.

### No drift report was written

With `--emit-only-on-change` and `--cooldown-minutes`, repeated runs stay quiet until something changes, so a report may not be written when nothing is new. Check `--state-path` (the state file that tracks previous emissions) and remove it to reset the cooldown.

### Drift is not detected for an unchanged-looking prompt

Prompt drift is based on a hash and inline diff of the file you pass with `--prompt-file`. Make sure `snapshot` and `compare` read the same file path/content, and that you pass `--model-fingerprint` if you want provider-side model changes detected.

## Documentation build

### MkDocs strict build fails

Strict mode treats warnings as errors. Common causes:

- A page exists in `docs/` but is missing from `nav` in `mkdocs.yml`.
- A relative link points at a file that does not exist (for example `[x](missing.md)`). Link to repository files outside `docs/` with absolute GitHub URLs.
- Mermaid blocks need the `pymdownx.superfences` custom fence from `mkdocs.yml`.

## Still stuck?

Open an issue at [github.com/DeepAgentLabs/agentic-chaos/issues](https://github.com/DeepAgentLabs/agentic-chaos/issues) with the command you ran, the output, and your Python and package versions.
