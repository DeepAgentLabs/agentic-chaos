"""Workflow node types: stages, gates, concurrency and reusable templates.

Nodes are declarative descriptions. Fault instances inside a `Step` are copied
fresh every time the step runs, so a workflow (or a template used twice) never
shares burst counts, decay progress or random streams between stages or runs.
"""

import copy
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from agentic_chaos.chaos.faults import BaseFault, resolve_faults
from agentic_chaos.chaos.scope import Scope
from agentic_chaos.contracts.base import Contract
from agentic_chaos.safety import CircuitBreaker

if TYPE_CHECKING:
    from agentic_chaos.workflows.report import WorkflowReport

FaultSpec = str | BaseFault
Target = Callable[[], Any]
_UNSET: Any = object()


def _require_name(kind: str, name: str | None, *, optional: bool = False) -> None:
    if name is None and optional:
        return
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{kind} name must be a non-empty string")
    if name != name.strip():
        raise ValueError(f"{kind} name must not have surrounding whitespace")


@dataclass
class Step:
    """One chaos stage: run the target `repeat` times inside a fresh `chaos_session`.

    The step fails when the target raises (or a script exits non-zero), when a
    contract does not pass, or when its circuit breaker aborts the session.
    `scope` narrows every fault in the step (intersected with each fault's own).
    """

    name: str
    faults: Sequence[FaultSpec] = ()
    target: Target | None = None
    repeat: int = 1
    contracts: Sequence[Contract] = ()
    breaker: CircuitBreaker | None = None
    dry_run: bool = False
    scope: Scope | None = None

    def __post_init__(self) -> None:
        _require_name("step", self.name)
        if isinstance(self.faults, str):
            self.faults = [name.strip() for name in self.faults.split(",") if name.strip()]
        self.faults = list(self.faults)
        resolve_faults(self.faults)  # unknown fault names fail at definition time
        if isinstance(self.repeat, bool) or not isinstance(self.repeat, int) or self.repeat < 1:
            raise ValueError("repeat must be a positive integer")
        if self.target is not None and not callable(self.target):
            raise ValueError("step target must be callable")
        self.contracts = list(self.contracts)

    def fresh_faults(self, scope: Scope | None = None) -> list[BaseFault]:
        """New fault instances for one execution, narrowed by step and workflow scope."""
        faults: list[BaseFault] = []
        for spec in self.faults:
            if isinstance(spec, str):
                fault = resolve_faults([spec])[0]
            else:
                try:
                    fault = copy.deepcopy(spec)
                except Exception:  # pragma: no cover - exotic, uncopyable custom fault
                    fault = spec
            for narrowing in (self.scope, scope):
                if narrowing is not None:
                    fault.scope = narrowing.intersect(getattr(fault, "scope", None))
            faults.append(fault)
        return faults


@dataclass
class HealthCheck:
    """Steady-state gate between stages; runs with no chaos session active.

    Calls `fn(query)` (or `fn()` when no query is given, or the workflow
    target when `fn` is None). With `expect_success=True` the check passes when
    the call returns, and `expect_contains` / `expect` (if given) accept the
    output. With `expect_success=False` it passes only when the call raises.
    A failed check halts the workflow unless `halt_on_failure=False`.
    `retries` re-runs a failing check, `retry_delay_seconds` apart.
    """

    fn: Callable[..., Any] | None = None
    query: Any = _UNSET
    name: str | None = None
    expect_success: bool = True
    expect_contains: str | None = None
    expect: Callable[[Any], bool] | None = None
    retries: int = 0
    retry_delay_seconds: float = 0.0
    halt_on_failure: bool = True

    def __post_init__(self) -> None:
        _require_name("health check", self.name, optional=True)
        if self.fn is not None and not callable(self.fn):
            raise ValueError("health check fn must be callable")
        if isinstance(self.retries, bool) or not isinstance(self.retries, int) or self.retries < 0:
            raise ValueError("retries must be a non-negative integer")
        if (
            isinstance(self.retry_delay_seconds, bool)
            or not isinstance(self.retry_delay_seconds, (int, float))
            or not 0 <= self.retry_delay_seconds < float("inf")
        ):
            raise ValueError("retry_delay_seconds must be finite and non-negative")
        if not self.expect_success and (self.expect is not None or self.expect_contains):
            raise ValueError("expect/expect_contains apply only when expect_success=True")

    @property
    def has_query(self) -> bool:
        return self.query is not _UNSET


Approver = Callable[["Suspend", "WorkflowReport"], "bool | None"]


@dataclass
class Suspend:
    """Human-in-the-loop gate. Execution continues only once the gate is approved.

    The approver (this node's `approve`, else the one passed to
    `ChaosWorkflow.run()`) returns True to continue, False to reject, or None
    when no decision is available yet: the workflow then stops as `suspended`
    and can be re-run later with ``resume_from=<name>``.
    """

    name: str
    reason: str = ""
    approve: Approver | None = None

    def __post_init__(self) -> None:
        _require_name("suspend", self.name)
        if self.approve is not None and not callable(self.approve):
            raise ValueError("approve must be callable")


@dataclass
class Parallel:
    """Run branches concurrently, then continue once every branch has finished.

    Each branch is a node or a sequence of nodes, runs in its own thread and
    context (so each has its own chaos session) and stops at its own first
    failure. `Suspend` gates are not allowed inside a parallel block.
    """

    # Each branch is a node or a list of nodes; lists after workflow expansion.
    branches: list[Any]
    name: str = "parallel"
    max_workers: int | None = None

    def __init__(
        self,
        *branches: "Node | Sequence[Node]",
        name: str = "parallel",
        max_workers: int | None = None,
    ) -> None:
        _require_name("parallel", name)
        if len(branches) < 2:
            raise ValueError("a parallel block needs at least two branches")
        if max_workers is not None and (
            isinstance(max_workers, bool) or not isinstance(max_workers, int) or max_workers < 1
        ):
            raise ValueError("max_workers must be a positive integer")
        self.branches = [list(b) if isinstance(b, (list, tuple)) else b for b in branches]
        self.name = name
        self.max_workers = max_workers
        for branch in self.branches:
            for node in branch if isinstance(branch, list) else [branch]:
                if _contains_suspend(node):
                    raise ValueError("Suspend gates are not allowed inside a parallel block")


@dataclass
class Template:
    """A reusable, parameterized sequence of nodes.

    `build` is either a callable returning nodes (called with the defaults
    merged with each use's parameters) or a fixed sequence of nodes. Every
    `use()` prefixes node names with the use's name, so one template can
    appear several times in a workflow.

    ```python
    escalate = Template("escalate", lambda burst=2: [
        Step("storm", faults=[RateLimitStormFault(burst_count=burst)]),
        HealthCheck(fn=ping, name="ping"),
    ])
    ChaosWorkflow("suite", [escalate.use(name="mild"), escalate.use(name="hard", burst=6)])
    ```
    """

    name: str
    build: Callable[..., Sequence["Node"]] | Sequence["Node"]
    defaults: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        name: str,
        build: Callable[..., Sequence["Node"]] | Sequence["Node"],
        **defaults: Any,
    ) -> None:
        _require_name("template", name)
        if not callable(build) and not isinstance(build, (list, tuple)):
            raise ValueError("template build must be a callable or a sequence of nodes")
        if not callable(build) and defaults:
            raise ValueError("parameter defaults need a callable build")
        self.name = name
        self.build = build
        self.defaults = dict(defaults)

    def use(self, *, name: str | None = None, **params: Any) -> "TemplateUse":
        """One placement of the template in a workflow."""
        return TemplateUse(self, name if name is not None else self.name, params)

    def expand(self, **params: Any) -> list["Node"]:
        """Nodes for one use, without name prefixes."""
        if callable(self.build):
            nodes = self.build(**{**self.defaults, **params})
        elif params:
            raise ValueError(f"template '{self.name}' takes no parameters")
        else:
            nodes = self.build
        if isinstance(nodes, (str, bytes)) or not isinstance(nodes, (list, tuple)):
            raise ValueError(f"template '{self.name}' must build a list of nodes")
        return list(nodes)


@dataclass
class TemplateUse:
    """A placement of a `Template`; expanded when the workflow is defined."""

    template: Template
    name: str
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_name("template use", self.name)


Node = Step | HealthCheck | Suspend | Parallel | TemplateUse
NODE_TYPES = (Step, HealthCheck, Suspend, Parallel, TemplateUse)


def _contains_suspend(node: Any) -> bool:
    if isinstance(node, Suspend):
        return True
    if isinstance(node, Parallel):
        return any(
            _contains_suspend(child)
            for branch in node.branches
            for child in (branch if isinstance(branch, list) else [branch])
        )
    if isinstance(node, TemplateUse):
        return any(_contains_suspend(child) for child in node.template.expand(**node.params))
    return False


def _prefixed(node: Any, prefix: str) -> Any:
    """A copy of `node` (and any parallel children) with names under `prefix/`."""
    if isinstance(node, Parallel):
        renamed = copy.copy(node)
        renamed.name = f"{prefix}/{node.name}"
        renamed.branches = [
            [_prefixed(child, prefix) for child in branch]
            if isinstance(branch, list)
            else _prefixed(branch, prefix)
            for branch in node.branches
        ]
        return renamed
    if isinstance(node, TemplateUse):
        return TemplateUse(node.template, f"{prefix}/{node.name}", dict(node.params))
    if isinstance(node, HealthCheck) and node.name is None:
        return node  # named during expansion, then prefixed by position
    return replace(node, name=f"{prefix}/{node.name}")


def expand_nodes(nodes: Sequence[Any], *, _depth: int = 0) -> list[Any]:
    """Replace template uses with their (prefixed) nodes, recursively."""
    if _depth > 32:
        raise ValueError("templates are nested too deeply (recursive template?)")
    expanded: list[Any] = []
    for node in nodes:
        if not isinstance(node, NODE_TYPES):
            raise ValueError(
                f"unsupported workflow node {node!r}; use Step, HealthCheck, "
                "Parallel, Suspend or Template.use()"
            )
        if isinstance(node, TemplateUse):
            children = expand_nodes(node.template.expand(**node.params), _depth=_depth + 1)
            expanded.extend(_prefixed(child, node.name) for child in children)
        elif isinstance(node, Parallel):
            copied = copy.copy(node)
            copied.branches = [
                expand_nodes(branch if isinstance(branch, list) else [branch], _depth=_depth + 1)
                for branch in node.branches
            ]
            expanded.append(copied)
        else:
            expanded.append(node)
    return expanded
