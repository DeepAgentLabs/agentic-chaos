# Agentic Chaos developer guide

Use this simple guide to choose a capability and run a bounded local experiment. The [AI Reference (robust)](https://deepagentlabs.io/agentic-chaos/docs/llms-full.md) contains the detailed topic guides and declarations from both distributed Python packages. Fault injection alone does not establish recovery or containment.

[Capability index](#capability-index) · [Quickstart](#quickstart) · [Configuration](#settings) · [Troubleshooting](#troubleshooting) · [Reference](#reference)

## Capability index

Every capability links to a short workflow below, with a detailed reference for its parameters and limitations.

| Capability | What you can do |
| --- | --- |
| [Core fault injection](#injection) | Simulate timeouts, rate limits and degraded responses at explicit call boundaries. |
| [Agent faults and topology](#agent-faults) | Exercise tool, memory, loop and handoff failures; record agent/tool edges. |
| [Async calls](#async) | Inject into async callables with cancellation-aware execution. |
| [Streaming faults](#streaming) | Cut or hang streams, delay first tokens or slow chunk delivery. |
| [Provider patching](#provider-patching) | Patch explicit OpenAI, Anthropic or Google Gen AI client instances. |
| [Probability and profiles](#profiles) | Control seeded sampling and load reusable TOML fault profiles. |
| [Safety and dry runs](#safety) | Bound instrumented injections, failure rate, duration and caller-reported cost; preview faults. |
| [Fidelity judges](#fidelity) | Score fault-event fidelity using heuristic or external evaluator adapters. |
| [Drift detection](#drift) | Compare prompt, model, output and retrieval snapshots with emission controls. |
| [Pytest plugin](#pytest) | Activate fault markers, fixtures, baseline runs, contracts and saved reports. |
| [Chaos contracts](#contracts) | Assert completion, recovery, retry limits, cost impact and topology traversal. |
| [Cascades and breaking-point search](#advanced) | Compose fault stages and search for a deterministic recovery threshold. |
| [Response poisoning](#poisoning) | Simulate wrong answers, fabricated references, malformed formats and adversarial instructions. |
| [Explicit cost estimates](#estimates) | Model failure/retry budget scenarios from caller-supplied assumptions. |
| [Scope controls](#scope) | Limit injection to included steps/providers and apply exclusions before sampling. |
| [Chaos workflows](#workflows) | Compose Step, Parallel, HealthCheck, Suspend and Template nodes with stage reports. |
| [Declarative experiments and schedules](#experiments) | Validate/run JSON, TOML or optional YAML; print cron/CI scheduling snippets. |
| [Topology fuzzing](#fuzzing) | Discover topology, place seeded single faults and report reached/unreached trials. |
| [Resilience probes](#probes) | Check HTTP, function, response-quality and latency signals before/during/after faults. |
| [Scores, CI gates and history](#scores) | Recompute evidence-based resilience scores, inspect trends and prune retained runs. |
| [Authenticated containment assertions](#containment) | Verify scoped observations and check dispatch after stop/revocation acknowledgements. |
| [ChaosHub recipes and exchange](#hub) | Discover bundled recipes, bind scripts and exchange pinned remote recipes explicitly. |
| [Fault plugins](#plugins) | Discover installed entry points and explicitly load trusted custom fault implementations. |
| [Reporting, AIOS and ecosystem integrations](#integrations) | Save native reports/topology, export draft AIOS Runs and correlate Lens evidence. |
| [Configuration and limitations](#settings) | Choose fault parameters, optional extras, host-owned targets and evidence boundaries. |

## Quickstart

Requires Python 3.10 or newer and an activated virtual environment:

```bash
python -m pip install agentic-chaos
agentic-chaos chaos list-faults
```

Save this complete file as `chaos_quickstart.py`:

```python
from agentic_chaos.chaos import TokenTimeoutError, chaos_call


def search(question):
    return [f"Document about {question}"]


try:
    result = chaos_call(search, "refund policy", faults=["token_timeout"], step_name="Search")
except TokenTimeoutError:
    result = []
print("Search result:", result)
```

[Download chaos_quickstart.py](guide/examples/chaos_quickstart.py)

```bash
python chaos_quickstart.py
agentic-chaos chaos run chaos_quickstart.py --inject token_timeout --save chaos_run.json
```

The first command returns a document. Under the CLI's active session, the timeout is caught and the result is empty; the saved report records the event. An empty fallback is an observed behavior, not proof that the user task succeeded. Define useful recovery assertions before treating it as a pass.

## Usage

Commands referencing `examples/` assume a source checkout and run from its root. Other named files are inputs you supply. Outside an active session, call wrappers pass through to the real target. Keep configured faults and call-site selection consistent when using multiple faults.

<span id="injection"></span>

### Core fault injection

```python
from pathlib import Path
from agentic_chaos import TokenTimeoutFault, chaos_call, chaos_session
from agentic_chaos.chaos import TokenTimeoutError

with chaos_session([TokenTimeoutFault(hang_seconds=0)]) as session:
    try:
        chaos_call(lambda: "normal result", faults=["token_timeout"], step_name="search")
    except TokenTimeoutError:
        pass
report = session.to_report("local-timeout")
assert len(report.chaos_events) == 1
Path("report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
```

`TokenTimeoutFault` raises or delays; `RateLimitStormFault` fails an initial burst; `SilentDegradationFault` corrupts a successful return. Select faults explicitly at each call site. See [core faults](features.md) and [fault parameters](configuration.md).

<span id="agent-faults"></span>

### Agent faults and topology

`ToolCallFailureFault` supports error, timeout and empty results. `MemoryCorruptionFault` garbles, truncates, injects or decays memory; `InfiniteLoopFault` forces bounded continuation; `HandoffCorruptionFault` corrupts, drops or delays a selected edge. `wrap_tool()` and `wrap_node()` instrument framework-neutral callables, while `TopologyTracker` records nodes and edges for agent attribution.

```bash
agentic-chaos agent run my_agent.py --inject tool_failure --save agent-report.json
```

Your script must use the wrappers. See [agent faults and topology](features.md#tool-and-node-wrapping-and-topology) and [framework integrations](integrations.md).

<span id="async"></span>

### Async calls

```python
import asyncio
from agentic_chaos import chaos_acall, chaos_session


async def answer():
    return "offline answer"


async def main():
    with chaos_session([]):
        assert await chaos_acall(answer) == "offline answer"


asyncio.run(main())
```

Supply call faults to the session to exercise failures. The provider coroutine stays on the event loop; blocking legacy fault delays use a worker. Stateful faults should not be shared across concurrent calls. See [async and provider semantics](v0.5.md#provider-patching).

<span id="streaming"></span>

### Streaming faults

```python
from agentic_chaos import StreamCutFault, chaos_session, chaos_stream

with chaos_session([StreamCutFault(after_chunks=2)]):
    chunks = list(chaos_stream(iter(["Hello", " world", "!"])))
assert chunks == ["Hello", " world"]
```

Use `StreamHangFault`, `SlowTTFTFault` or `SlowChunksFault` for other stream boundaries. `chaos_astream()` supports async iterators. Consume inside the session and close abandoned streams. Streaming faults belong on stream wrappers. See [stream lifecycle, cancellation and faults](v0.5.md#streaming).

<span id="provider-patching"></span>

### Provider patching

`patch_openai(client)`, `patch_anthropic(client)` and `patch_google(client)` patch an explicitly supplied client during an active session and restore its methods afterward. Install `agentic-chaos[providers]` or the individual SDK you use. Auth/context faults (`AuthErrorFault`, `ContextLengthFault`) raise package exceptions; stream faults use the documented SDK streaming methods.

Select one configured fault when patching a multi-fault session. High-level stream accumulators and cloned clients have separate limitations. See [supported sync/async SDK methods and restoration](v0.5.md#provider-patching).

<span id="profiles"></span>

### Probability and profiles

Faults accept `probability` and `seed`. TOML profiles collect fault names, common sampling settings and per-fault constructor parameters:

```toml
[profiles.quick-timeout]
faults = ["token_timeout"]
probability = 1.0
seed = 42
[profiles.quick-timeout.parameters.token_timeout]
hang_seconds = 0
```

Save as `chaos.toml`, then choose exactly one of `--inject` and `--profile` (or a bundled `--experiment` recipe):

```bash
agentic-chaos chaos run chaos_quickstart.py --profile quick-timeout --profile-file chaos.toml
```

`load_profile(name, path)` returns fresh instances for Python callers. See [sampling, seeds and profile validation](v0.5.md#probability-and-profiles).

<span id="safety"></span>

### Safety and dry runs

```bash
agentic-chaos chaos run chaos_quickstart.py --inject token_timeout \
  --dry-run --max-injections 5 --max-duration-seconds 10 --save preview.json
```

`CircuitBreaker` also supports failure-rate and explicitly reported cost limits. Use `session.record_cost()` or `record_usage()` for cost accounting. Limits are cooperative and do not kill arbitrary target code. Dry runs record `planned_events` while executing real targets unchanged, so target side effects and spending remain possible. See [limits, accounting, aborts and dry-run semantics](safety.md).

<span id="fidelity"></span>

### Fidelity judges

Nest a chaos session inside `fidelity_session(judge)` to attach fidelity scores to recorded fault events. Choose `HeuristicJudge` or supply an already constructed evaluator to `DeepEvalJudge`/`PydanticEvalsJudge`. Fidelity is separate from successful task recovery and containment. See [judge setup and interpretation](features.md#fidelity-judges).

<span id="drift"></span>

### Drift detection

Create the input files first, then capture and compare:

```bash
agentic-chaos drift snapshot --name support --prompt-file prompt.txt --save baseline.json
agentic-chaos drift compare baseline.json --prompt-file current-prompt.txt --save drift.json
```

Snapshots can include model/fingerprint/embedding identity, output text and retrieval items. `--state-path`, `--cooldown-minutes` and `--emit-only-on-change` control repeated emission. Detected drift exits 2. See [drift CLI flags](cli-reference.md#agentic-chaos-drift-snapshot) and [snapshot/report fields](output-formats.md#drift-report-and-state).

<span id="pytest"></span>

### Pytest plugin

Install `agentic-chaos[pytest]`. Save this complete test as `test_chaos_recovery.py`:

```python
import pytest
from agentic_chaos import TokenTimeoutFault, chaos_call
from agentic_chaos.chaos import TokenTimeoutError


@pytest.mark.chaos(faults=[TokenTimeoutFault(hang_seconds=0)], must_recover=True)
def test_timeout_fallback():
    try:
        result = chaos_call(lambda: "answer", faults=["token_timeout"], step_name="answer")
    except TokenTimeoutError:
        result = "fallback"
    assert result in {"answer", "fallback"}
```

[Download test_chaos_recovery.py](guide/examples/test_chaos_recovery.py)

```bash
pytest test_chaos_recovery.py
pytest --chaos test_chaos_recovery.py --chaos-report-dir chaos-reports
```

Without `--chaos`, markers are inert. With it, faults and contracts activate; the `chaos` fixture can record usage/topology. Optional baseline runs execute the test twice with the same fixture instances. See [markers, fixture, async tests and plugin options](v0.6.md).

<span id="contracts"></span>

### Chaos contracts

```bash
agentic-chaos contracts list
agentic-chaos contracts check chaos_run.json --contract no_unhandled_error
```

The seven built-ins check completion time, unhandled errors, per-step retries, recovery after failure, cost impact, retry storms and topology traversal. Use `check_contracts()` to inspect results or `assert_contracts()` to raise on failure. Missing evidence is inconclusive and does not pass. `--contract` and `--save-contracts` can also gate a script run. See [contract definitions and evidence requirements](v0.6.md#contracts).

<span id="advanced"></span>

### Cascades and breaking-point search

`cascade(first=..., then=..., delay_between=...)` schedules fault stages across successive instrumented calls; it does not execute a target twice per call. Use fresh stateful instances per campaign.

`find_breaking_point(target, fault=..., param=..., range=(low, high))` searches an inclusive integer severity range and records trials. It assumes deterministic, monotonic recovery; reset external state between trials and define `recovered(output)` when returning normally is insufficient. See [cascades and threshold assumptions](v0.7.md).

<span id="poisoning"></span>

### Response poisoning

`PoisonedResponseFault` supports `confident_wrong`, `partial_hallucination`, `format_violation`, `prompt_injection` and `policy_bypass`. These are synthetic transformations of supported text/envelopes. Custom payloads are retained in native event detail. Pair them with task-quality or authenticated containment checks. See [strategy parameters and synthetic controls](v0.7.md#response-poisoning-and-containment-evidence).

<span id="estimates"></span>

### Explicit cost estimates

```bash
agentic-chaos estimate scenario.py --fault rate_limit_storm --retries 3 \
  --calls 1 --cost-per-call-usd 0.04
```

The path is only a label and is not executed. The supplied assumptions model a baseline of $0.04, extra retries of $0.12 and total of $0.16. This is a budget scenario, not provider billing evidence. See [estimate assumptions](v0.7.md#explicit-cost-estimates).

<span id="scope"></span>

### Scope controls

Attach `Scope(steps=["search"], exclude_steps=["safety_check"])` to a fault to limit eligible call labels. Provider scopes use `chaos_provider` labels, supplied by provider patches or explicitly at call sites. Exclusions win; missing labels fail include lists closed. Scope is checked before probability and state advancement. See [Scope configuration and intersection](v0.8.md#explosion-radius-scope).

<span id="workflows"></span>

### Chaos workflows

Compose `Step`, `Parallel`, `HealthCheck`, `Suspend` and `Template` nodes inside `ChaosWorkflow`. Workflows retain stage events, calls, contracts, probe results and native merged evidence. Unapproved Suspend gates stop execution; resuming re-runs the definition after the selected approved gate rather than restoring process state.

```bash
agentic-chaos chaos workflow validate workflow.json
agentic-chaos chaos workflow run workflow.json --no-input --save workflow-report.json
```

See [node semantics, approvals, reports and statuses](v0.8.md#chaos-workflows). Workflow files name executable targets supplied by the host.

<span id="experiments"></span>

### Declarative experiments and schedules

Define single-stage experiments or multi-stage workflows in JSON/TOML, or install `agentic-chaos[yaml]` for YAML. This complete JSON document uses the quickstart script in the same folder:

```json
{
  "name": "local-timeout",
  "target": "./chaos_quickstart.py",
  "faults": [{"type": "token_timeout", "hang_seconds": 0}],
  "assertions": ["no_unhandled_error"]
}
```

Save it as `experiment.json`:

```bash
agentic-chaos experiment validate experiment.json --json
agentic-chaos experiment run experiment.json --no-input --save workflow-report.json
```

Validation checks document shape, constructor fields, scopes, assertions and target definitions without executing targets. `experiment schedule` prints upcoming runs and cron/GitHub Actions snippets for a document's `schedule` section; it installs no scheduler. See [document fields, target resolution and scheduling](v0.8.md#declarative-experiments).

<span id="fuzzing"></span>

### Topology fuzzing

```bash
agentic-chaos agent fuzz my_agent.py --n 10 --seed 42 --save fuzz-report.json
```

`fuzz_topology()` discovers a fault-free baseline topology, weights single-fault placements by fan-out, and records reached/unreached trials and recovery. Repeatable `--step`, `--exclude-step` and `--fault` constrain the CLI campaign. See [fuzzer assumptions, reports and bounded execution](v0.8.md#topology-fuzzer).

<span id="probes"></span>

### Resilience probes

`chaos_run()` manages pre/during/post probes around a target. `HttpProbe`, `FunctionProbe`, `ResponseQualityProbe` and `LatencyProbe` support different health and quality checks. A failing pre-check normally blocks injection; during probes run inside the active session after the target, not as a continuous background monitor.

```bash
agentic-chaos chaos run my_app.py --inject rate_limit_storm \
  --probe health_checks.py:check_health --save probed-report.json
```

The probe callable is host-owned code. Configure richer probes and phases in Python or experiment files. See [probe setup, retries, lifecycle and weights](v0.9.md#probes).

<span id="scores"></span>

### Scores, CI gates and history

```bash
agentic-chaos score show probed-report.json --min-score 70 --history history.json --json
agentic-chaos score history --history history.json --json
agentic-chaos score prune --history history.json --max-runs 100
```

`compute_resilience()` recomputes the 0–100 score from saved native evidence. Recovery, steady-state, latency and cost components depend on available observations/baselines; insufficient evidence yields an inconclusive score, which fails a minimum-score gate. `ResilienceHistory` records trends and retention. See [scoring method, weighting and CI flags](v0.9.md).

<span id="containment"></span>

### Authenticated containment assertions

Install `agentic-chaos[containment]` for the Lens verifier adapter. `assert_contained()` authenticates an exact ordered observation snapshot, then checks effective stop/revocation acknowledgements, denied attempts and forbidden later dispatches within the specified subject/task scope. The host supplies trusted keys and expected stream/scope. In-flight completions are preserved; failed, unknown or incomplete evidence cannot pass.

See [authenticated observation requirements](api-reference.md#authenticated-containment-assertions-0100), [coordinated containment boundaries](phase6-containment.md), and the offline checkout example `examples/containment_demo.py`. Producer-declared capture coverage remains separate from snapshot authentication.

<span id="hub"></span>

### ChaosHub recipes and exchange

```bash
agentic-chaos hub list
agentic-chaos hub search rag
agentic-chaos hub pull rag-context-poisoning recipe.json
```

Six bundled recipes cover retriever failure, context poisoning, reasoning-loop resilience, coordinator failure, support escalation and rate-limit storms. Bind a bundled recipe to your instrumented script with `chaos run my_app.py --experiment RECIPE_NAME`, or customize a pulled file and validate/run it as an experiment. Remote exchange is opt-in and requires a full commit SHA; `hub push` stages a contribution in a local registry checkout without publishing it. See [recipe identities, pinned exchange and contribution workflow](v0.11.md).

<span id="plugins"></span>

### Fault plugins

Publish a concrete `BaseFault` subclass through the `agentic_chaos.plugins` entry-point group, with its entry-point name matching its fault name. `hub list` discovers installed plugin metadata without importing it. Enable trusted plugin code with `chaos run my_app.py --plugins --inject custom_timeout` or Python `load_plugins()`; loading validates constructors/names and rejects collisions before registry mutation. See [plugin packaging and lifecycle](v0.11.md#fault-plugins).

<span id="integrations"></span>

### Reporting, AIOS and ecosystem integrations

Save native `ChaosReport` JSON, workflow reports, topology, contracts, scores, drift and history through their own APIs/commands. `--save-aios` on script/workflow runs and Python `to_aios_run()` export a draft `0.4-draft` AIOS Run with producer-local extensions. Native reports and AIOS exports have different contracts.

The optional Lens bridge provides `attach_events`, `step_kwargs`, `span_attributes`, `mark_span` and `attach_drift_report`. Lens consumes evidence; Sidecar owns supervision, Evals owns independent output scoring/release gates, Tower keeps deployment health separate, and MCP is a separate delivery surface. See [integration setup](integrations.md), [output formats and AIOS mapping](output-formats.md), and [coordinated readiness](coordinated-v1-readiness.md). Version-labelled integration notes describe their stated releases.

<span id="settings"></span>

## Configuration and limitations

Use constructor arguments for faults, `chaos.toml` for named profiles, declarative documents for campaigns, and CLI flags for script runs. Optional extras are `[providers]`, `[yaml]`, `[pytest]`, `[agenticlens]` and `[containment]`; core injection does not require sibling packages. See [configuration](configuration.md), [safety](safety.md) and [limitations](limitations.md).

Work bypassing explicit wrappers is outside captured evidence. Cooperative guards do not terminate already-running external operations. Judges, retry success, resilience scores and containment assertions establish different things. Keep original native artifacts and preserve inconclusive states. Package 1.0.x does not promote draft schemas or certify production deployment safety.

## Troubleshooting

Check that the session is active, the fault is configured and selected, the scope matches recorded labels, and streams are consumed inside the session. Inspect events, planned events, calls and probe/contract results. Use `agentic-chaos COMMAND --help` for exact options. See [troubleshooting](troubleshooting.md).

## Reference

- [API reference](api-reference.md) and [CLI reference](cli-reference.md).
- [AI Reference (robust)](https://deepagentlabs.io/agentic-chaos/docs/llms-full.md) and [capability/source index](ai-reference-index.md).
- [Source manifest and checksums](ai-docs-manifest.json).
