# Getting Started

This page takes you from zero to a recorded chaos event in a few minutes.

## Requirements

- Python **3.10 or newer** (tested classifiers: 3.10, 3.11, 3.12, 3.13)
- No other runtime dependency. The AgenticLens integration and the eval-framework
  judges are optional.

## Installation

=== "pip"

    ```bash
    pip install agentic-chaos
    ```

=== "uv (from source)"

    ```bash
    git clone https://github.com/DeepAgentLabs/agentic-chaos.git
    cd agentic-chaos
    uv sync --extra dev --frozen
    ```

### Optional extras

| Extra | Install | Purpose |
| --- | --- | --- |
| `agenticlens` | `pip install agentic-chaos[agenticlens]` | Merge chaos events into an AgenticLens `Workflow` |
| `dev` | `uv sync --extra dev --frozen` | Test, lint and type-check tooling for contributors |

!!! warning "Why `--frozen`?"
    `pyproject.toml` points the `agenticlens` extra at a sibling checkout through
    `[tool.uv.sources]`. Plain `uv sync` tries to validate the *entire* lock, including
    extras you did not ask for, and fails if that sibling directory does not exist.
    `--frozen` installs straight from the committed `uv.lock`. Drop it only if you are
    working on the AgenticLens integration itself. See
    [Troubleshooting](troubleshooting.md#uv-sync-fails-because-of-the-agenticlens-extra).

### Verify the install

```bash
agentic-chaos chaos list-faults
```

You should see every available fault type. If the command is not found, make sure the
environment that holds the package is active, or prefix with `uv run`.

## Your first experiment

### 1. Write a script with a fragile call

Wrap the call you want to stress with `chaos_call()`. Save this as `my_app.py`:

```python
from agentic_chaos.chaos import chaos_call, TokenTimeoutError


def search(question: str) -> list[str]:
    # Stand-in for a real retriever or LLM call.
    return [f"document about {question}"]


def main() -> None:
    try:
        chunks = chaos_call(
            search,
            "refund policy",
            faults=["token_timeout"],
            step_name="Retriever",
        )
    except TokenTimeoutError:
        chunks = []  # no fallback handled it -- this is exactly what we want to find
    print("chunks:", chunks)


main()
```

Run it normally and nothing changes: outside a chaos session, `chaos_call()` simply
calls `search("refund policy")`.

### 2. Run it under chaos from the CLI

```bash
agentic-chaos chaos run my_app.py --inject token_timeout --save chaos_run.json
```

Illustrative output:

```text
                                  Chaos Events
  Step        Fault           Outcome    Message
 ────────────────────────────────────────────────────────────────────────────
  Retriever   token_timeout   errored    call hung for 2.0s then timed out

1 chaos event(s) recorded.

Saved chaos report to chaos_run.json
```

The call hung for the default 2.0 seconds, then raised `TokenTimeoutError`. Your
`except` block swallowed it and returned an empty list. That is the finding: **no
fallback produced a useful answer.**

`chaos_run.json` is the package's own standalone report. No other library is needed to
produce or read it. See [Output Formats](output-formats.md).

### 3. Do the same thing from Python

```python
from agentic_chaos.chaos import chaos_session, TokenTimeoutFault

with chaos_session([TokenTimeoutFault(hang_seconds=0.5)]) as session:
    main()

for event in session.events:
    print(event.fault_type, event.outcome)
```

Use this form inside tests, where you want to assert on `session.events`. See
[Examples](examples.md#recipe-1-find-an-unhandled-timeout).

## Next steps

- Learn the three fault families in [Features](features.md).
- Tune fault behavior in [Configuration](configuration.md).
- Try the runnable scripts listed in [Examples](examples.md).
- Add drift checks to CI with the [Drift Detector](features.md#drift-detector).
