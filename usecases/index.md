# Agentic Chaos Use Cases

End-to-end walkthroughs that inject faults into real multi-agent workflows and
show what breaks, what holds and what the release gate decides. Each one runs
locally from this repository, with no model, API key or network connection.

## Catalog

| Use case | Summary | Difficulty | Capabilities | Verified with |
|---|---|---|---|---|
| [Block an unsafe lending release](finassure-release-gate.md) | A naive five-agent loan underwriter approves 34 applications it never verified when the credit bureau fails. The hardened version escalates them instead, and a seven-rule release gate tells the two apart. | Intermediate | [Tool-call failure](https://deepagentlabs.io/agentic-chaos/docs/features/#tool-call-failure), [Silent degradation](https://deepagentlabs.io/agentic-chaos/docs/features/#silent-degradation), [AgenticLens integration](https://deepagentlabs.io/agentic-chaos/docs/integrations/#agenticlens) | agentic-chaos main, agenticlens 0.10.0 |

## Verified versions

- **Packages:** agentic-chaos from this repository's `main`, agenticlens 0.10.0
  from PyPI
- **Environment:** Python 3.12 on Linux, no `GEMINI_API_KEY` (the offline
  judge)
- **Verification date:** 2026-10-26
- **Scope:** the commands and numbers on each page were run and copied from
  their output. The same numbers are pinned in
  [`examples/finassure/tests/test_usecase_page.py`](https://github.com/DeepAgentLabs/agentic-chaos/blob/main/examples/finassure/tests/test_usecase_page.py),
  which runs in CI, so a change that moves them fails the build.

## Quick navigation

- [Agentic Chaos documentation](https://deepagentlabs.io/agentic-chaos/docs/)
- [Agentic Chaos product page](https://deepagentlabs.io/agentic-chaos/)
