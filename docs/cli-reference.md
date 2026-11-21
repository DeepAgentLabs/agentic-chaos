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
├── hub
│   ├── list [--repository REPO --ref COMMIT_SHA]
│   ├── search <query>
│   ├── pull <name> <output>
│   └── push <source> <checkout>
└── estimate
```

Get help for any command with `--help`, for example
`agentic-chaos drift compare --help`.

## Complete command inventory

Every registered command is listed below, including the two experiment/workflow `run` aliases registered through their shared implementation. Use `agentic-chaos COMMAND --help` for all options. Source declarations in the robust AI reference preserve exact options for public CLI functions; shared run options are documented below.

| Command (after `agentic-chaos`) | Purpose |
| --- | --- |
| `agent fuzz` | Fuzz the agent graph: place one fault per trial, weighted by node fan-out. |
| `agent run` | Run an agent script with agent-level faults active, then report what happened. |
| `chaos list-faults` | List the fault types available to --inject. |
| `chaos run` | Run a script with the requested faults active, then report what happened. |
| `chaos workflow run` | Validate, then run an experiment or workflow and report every stage. |
| `chaos workflow validate` | Lint workflow files without running them (same as `experiment validate`). |
| `contracts check` | Check contracts against a saved chaos report; exits 1 unless all pass. |
| `contracts list` | List the built-in contracts and their spec parameters. |
| `drift compare` | Compare a current snapshot to a stored baseline, with cooldown-aware emission. |
| `drift snapshot` | Capture a prompt/model/output/retrieval baseline snapshot. |
| `estimate` | Estimate retry cost as JSON from explicit inputs, without executing the target. |
| `experiment run` | Validate, then run an experiment or workflow and report every stage. |
| `experiment schedule` | Show upcoming runs and print a crontab or GitHub Actions schedule snippet. |
| `experiment validate` | Lint experiments without running them; exits 1 when any file is invalid. |
| `hub list` | List recipes and installed plugin metadata. |
| `hub pull` | Copy a validated bundled or commit-pinned remote recipe. |
| `hub push` | Stage a validated contribution in a local registry checkout. |
| `hub search` | Search recipe metadata. |
| `score history` | List recorded resilience scores, oldest first, with run-over-run deltas. |
| `score prune` | Apply retention to a run-history file now. |
| `score show` | Recompute the resilience score of a saved report, offline. |

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

| Name | Family / intended wrapper |
| --- | --- |
| `token_timeout` | Call timeout/delay: `chaos_call` / `chaos_acall` |
| `rate_limit_storm` | Initial call-error burst |
| `silent_degradation` | Successful-response corruption |
| `tool_failure` | Tool error, timeout or empty result |
| `memory_corruption` | Memory transformation |
| `infinite_loop` | Bounded forced continuation |
| `handoff_corruption` | Selected agent edge |
| `auth_error` | Provider-style authentication failure |
| `context_length` | Provider-style context overflow |
| `stream_cut` | Streaming only: early end |
| `stream_hang` | Streaming only: bounded hang then error |
| `slow_ttft` | Streaming only: first-token delay |
| `slow_chunks` | Streaming only: subsequent-chunk delay |
| `poisoned_response` | Synthetic adversarial response |

Use `chaos list-faults` for the installed registry. Fault plugins are opt-in; cascades compose fault instances through the Python API. See [fault parameters](configuration.md), [stream/provider faults](v0.5.md) and [poisoning](v0.7.md).

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



## Script-run selection, safety and reporting

`chaos run` and `agent run` accept `--inject`, `--profile` with `--profile-file`, or a bundled ChaosHub recipe via `--experiment`. These are mutually exclusive selection modes. `--plugins` explicitly loads trusted installed fault plugins.

| Options | Purpose |
| --- | --- |
| `--dry-run` | Execute targets unchanged and record planned faults |
| `--max-cost-usd` | Limit explicitly recorded cost |
| `--max-failure-rate`, `--failure-window`, `--min-calls` | Bound rolling wrapped-operation failures |
| `--max-duration-seconds`, `--max-injections` | Cooperative elapsed-time and injection limits |
| `--save`, `--save-aios` | Native report JSON and AIOS `0.4-draft` Run export |
| `--contract`, `--save-contracts`, `--baseline` | Contract checks, their report and optional baseline evidence |
| `--probe`, `--min-score`, `--history` | Steady-state probes, score gate and trend store |
| `--history-max-runs`, `--history-max-age-days` | History retention limits |

See [profiles and provider/stream wrappers](v0.5.md), [safety](safety.md), [contracts](v0.6.md), [probes/scores](v0.9.md) and [recipe/plugin selection](v0.11.md).

## `agentic-chaos contracts`

```bash
agentic-chaos contracts list
agentic-chaos contracts check chaos.json --contract no_unhandled_error \
  --contract max_retries:3 --baseline baseline.json --save contracts.json
```

Contract specs are repeatable. Missing evidence produces `inconclusive`, which fails the gate. See [all seven definitions and call-log semantics](v0.6.md#contracts).

## `agentic-chaos experiment` and `chaos workflow`

```bash
agentic-chaos experiment validate experiment.json [MORE_FILES...] \
  [--json] [--strict] [--no-target-check] [--base-dir DIRECTORY]
agentic-chaos chaos workflow validate workflow.json [MORE_FILES...] \
  [--json] [--strict] [--no-target-check] [--base-dir DIRECTORY]
agentic-chaos experiment run experiment.json [OPTIONS]
agentic-chaos chaos workflow run workflow.json [OPTIONS]
```

The `run` commands share exactly these options:

| Option | Purpose |
| --- | --- |
| `--save PATH` | Workflow report JSON |
| `--save-report PATH` | Merged native ChaosReport |
| `--save-aios PATH` | Merged AIOS draft Run |
| `--dry-run` | Preview faults while executing targets and health checks |
| `--approve NAME` | Approve a named Suspend gate; repeatable |
| `--approve-all` | Approve all gates explicitly |
| `--resume-from NAME` | Skip to after the named approved gate |
| `--no-input` | Never prompt; stop at unapproved gates |
| `--no-target-check`, `--base-dir DIRECTORY` | Control structural target checking and path resolution |
| `--min-score N`, `--baseline PATH` | Score threshold and baseline evidence |
| `--history PATH`, `--history-max-runs N`, `--history-max-age-days D` | Trend recording and retention |

Exit 0 means passed, 3 means suspended at an unapproved gate, and 1 means failed (including an inconclusive/below-threshold score). Validation never executes targets; running executes host-supplied definitions. See [declarative syntax, approvals and target resolution](v0.8.md).

```bash
agentic-chaos experiment schedule experiment.json [--format crontab|github-actions] \
  [--next 5] [--command "agentic-chaos experiment run experiment.json --no-input"]
```

Scheduling prints upcoming runs and snippets; it does not install or run a scheduler. GitHub Actions cron uses UTC; timezone handling is described in the [scheduling guide](v0.8.md#scheduling).

## `agentic-chaos agent fuzz`

```bash
agentic-chaos agent fuzz my_agent.py --n 10 --seed 42 \
  [--step NAME] [--exclude-step NAME] [--fault NAME] [--save fuzz.json]
```

Scope/fault options are repeatable. A fault-free baseline discovers topology, then single-fault trials test reached nodes. A reached trial that fails recovery produces exit 1. See [topology fuzzing](v0.8.md#topology-fuzzer).

## `agentic-chaos estimate`

```bash
agentic-chaos estimate scenario.py --fault rate_limit_storm --retries 3 \
  --calls 1 --cost-per-call-usd 0.04
```

Prints caller-assumption budget JSON without executing the path. See [estimate semantics](v0.7.md#explicit-cost-estimates).

## `agentic-chaos hub`

```bash
agentic-chaos hub list
agentic-chaos hub search rag
agentic-chaos hub pull rag-context-poisoning recipe.json
agentic-chaos hub push my-recipe.json /path/to/registry-checkout
```

`list`, `search` and `pull` optionally accept `--repository OWNER/REPO --ref COMMIT_SHA`; use a full 40-character lowercase commit SHA. `pull` refuses overwrite. `push` stages a local contribution and does not publish it. Installed fault-plugin code is only loaded when explicitly requested. See [ChaosHub recipes, exchange and plugins](v0.11.md).
