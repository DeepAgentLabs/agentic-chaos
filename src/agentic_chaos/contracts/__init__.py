"""Chaos contracts: pass/fail resilience checks over a finished chaos run (v0.6).

```python
from agentic_chaos import chaos_call, chaos_session
from agentic_chaos.contracts import MaxRetries, NoUnhandledError, assert_contracts

with chaos_session(["rate_limit_storm"]) as session:
    answer = my_agent("What's the weather?")
assert_contracts(session.to_report("weather"), [NoUnhandledError(), MaxRetries(3)])
```

Contracts read the native `ChaosReport` -- its fault events, call log,
topology and safety fields -- so they work on a live session's report or on
JSON saved by `agentic-chaos chaos run --save`. See docs/v0.6.md.
"""

from agentic_chaos.contracts.base import (
    Contract,
    ContractReport,
    ContractResult,
    ContractViolationError,
    assert_contracts,
    check_contracts,
    load_report,
)
from agentic_chaos.contracts.builtin import (
    BUILTIN_CONTRACTS,
    CompletesWithin,
    FullTopologyTraversal,
    MaxCostImpact,
    MaxRetries,
    NoRetryStorm,
    NoUnhandledError,
    RecoveredAfterFailure,
)
from agentic_chaos.contracts.registry import CONTRACT_REGISTRY, describe_contracts, parse_contract

__all__ = [
    "BUILTIN_CONTRACTS",
    "CONTRACT_REGISTRY",
    "CompletesWithin",
    "Contract",
    "ContractReport",
    "ContractResult",
    "ContractViolationError",
    "FullTopologyTraversal",
    "MaxCostImpact",
    "MaxRetries",
    "NoRetryStorm",
    "NoUnhandledError",
    "RecoveredAfterFailure",
    "assert_contracts",
    "check_contracts",
    "describe_contracts",
    "load_report",
    "parse_contract",
]
