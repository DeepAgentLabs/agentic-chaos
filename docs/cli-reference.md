# CLI Reference

The package installs one executable, `agentic-chaos`. Prefix with `uv run` when working
from a source checkout.

```text
agentic-chaos
├── chaos
│   ├── run <script> --inject <faults> [--save <file>] [--probe ...] [--min-score N]
│   ├── list-faults
│   └── workflow run|validate <file>
├── agent
│   ├── run <script> --inject <faults> [--save <file>] [--probe ...] [--min-score N]
│   └── fuzz <script>
├── contracts
│   ├── list
│   └── check <report>
├── experiment
│   ├── validate <files>
│   ├── run <file> [--min-score N] [--history <file>]
│   └── schedule <file>
├── score
│   ├── show <report> [--baseline ...] [--min-score N] [--json]
│   ├── history [--history <file>]
│   └── prune [--history <file>] --max-runs N | --max-age-days D
├── drift
│   ├── snapshot --name ... --save ...
│   └── compare <baseline> ...
└── estimate
```

Get help for any command with `--help`, for example
`agentic-chaos drift compare --help`.

## `agentic-chaos chaos run`

Run a Python script with LLM-level chaos active and print a chaos-events report.

```bash
agentic-chaos chaos run <script.py> --inject <fault[,fault...]> [--save <report.json>]
```

| Option | Description |
| --- | --- |
| `<script.py>` | The script to run under chaos |
| `--inject` | Comma-separated fault names: `token_timeout`, `rate_limit_storm`, `silent_degradation` |
| `--save` | Write the standalone chaos report to this path |

```bash
agentic-chaos chaos run my_app.py --inject token_timeout,rate_limit_storm
agentic-chaos chaos run my_app.py --inject silent_degradation --save chaos_run.json
```

The script's `chaos_call()` sites select which active fault applies where. If you
inject more than one fault, each call site must pass `faults=[...]`.

## `agentic-chaos agent run`

Run a script with agent-level or handoff faults active.

```bash
agentic-chaos agent run <script.py> --inject <fault[,fault...]> [--save <report.json>]
```

| Option | Description |
| --- | --- |
| `--inject` | `tool_failure`, `memory_corruption`, `infinite_loop`, `handoff_corruption` |
| `--save` | Write the report to this path |

```bash
agentic-chaos agent run my_agent.py --inject tool_failure,memory_corruption --save report.json
agentic-chaos agent run my_agent.py --inject handoff_corruption --save report.json
```

## `agentic-chaos chaos list-faults`

List every available fault type.

```bash
agentic-chaos chaos list-faults
```

## `agentic-chaos drift snapshot`

Capture a baseline from your current prompt, output, retrieval results and model
identity.

```bash
agentic-chaos drift snapshot \
  --name support-agent \
  --save baseline.json \
  --prompt-file prompt.txt \
  --output-file baseline_output.txt \
  --retrieval-file retrieval.txt \
  --model gpt-5-mini \
  --model-fingerprint provider-fp-001 \
  --embedding-model text-embed-1
```

| Option | Description |
| --- | --- |
| `--name` | Name for this baseline |
| `--save` | Path to write the baseline JSON |
| `--prompt-file` | File containing the prompt |
| `--output-file` | File containing a representative model output |
| `--retrieval-file` | File containing the fixed retrieval results |
| `--model` | Model name |
| `--model-fingerprint` | Provider-reported model or system fingerprint |
| `--embedding-model` | Embedding model identifier |

## `agentic-chaos drift compare`

Compare a current run against a saved baseline.

```bash
agentic-chaos drift compare baseline.json \
  --prompt-file prompt.txt \
  --output-file current_output.txt \
  --retrieval-file retrieval.txt \
  --model gpt-5-mini \
  --model-fingerprint provider-fp-002 \
  --save drift_report.json
```

| Option | Description |
| --- | --- |
| `<baseline.json>` | Baseline created by `drift snapshot` |
| `--prompt-file`, `--output-file`, `--retrieval-file` | Current prompt, output and retrieval results |
| `--model`, `--model-fingerprint`, `--embedding-model` | Current model identity |
| `--save` | Path to write the drift report JSON |
| `--state-path` | File that remembers the previous result between scheduled runs |
| `--cooldown-minutes` | Minimum minutes before the same drift is emitted again |
| `--emit-only-on-change` | Stay quiet unless the drift result changed since the last run |

**Exit code:** `drift compare` exits with code **`2`** when drift is detected, so it can
fail a CI job. A JSON report is still written when the emission rules allow it.

Quiet scheduled run:

```bash
agentic-chaos drift compare baseline.json \
  --prompt-file prompt.txt \
  --output-file current_output.txt \
  --save drift_report.json \
  --state-path .agentic-chaos/drift-state.json \
  --cooldown-minutes 1440 \
  --emit-only-on-change
```

## Fault names

| Name | Family | Used with |
| --- | --- | --- |
| `token_timeout` | LLM | `chaos run` |
| `rate_limit_storm` | LLM | `chaos run` |
| `silent_degradation` | LLM | `chaos run` |
| `tool_failure` | Agent | `agent run` |
| `memory_corruption` | Agent | `agent run` |
| `infinite_loop` | Agent | `agent run` |
| `handoff_corruption` | Agent / edge | `agent run` |

## Resilience options (v0.9)

`chaos run`, `agent run`, `experiment run` and `chaos workflow run` print a
probe table and a resilience report after every run, and accept:

| Option | Description |
| --- | --- |
| `--probe SPEC` | `chaos run` and `agent run` only, repeatable. An `http(s)://` URL must answer 200. A `file.py:function` or `module:function` spec must return without raising. Runs before and after the chaos; a failure before it exits 1 without injecting anything. |
| `--min-score N` | Exit 1 unless the resilience score is at least N (0-100). An inconclusive score fails. |
| `--history PATH` | Record the score in a run-history file and print the trend. |
| `--history-max-runs N` | Keep the newest N runs per name in that file. |
| `--history-max-age-days D` | Drop runs older than D days from that file. |
| `--baseline PATH` | A fault-free report for the latency and cost components (and the contracts that compare against one). |

## `agentic-chaos score`

```bash
agentic-chaos score show chaos_run.json [--baseline baseline.json] [--weight recovery=0.5] \
    [--min-score 70] [--history h.json] [--json] [--save score.json]
agentic-chaos score history [--history .agentic-chaos/resilience-history.json] [--name NAME] [--json]
agentic-chaos score prune [--history ...] [--max-runs N] [--max-age-days D]
```

`score show` recomputes the score from a saved native, merged or workflow
report, so it works on CI artifacts. See the [v0.9 guide](v0.9.md).

