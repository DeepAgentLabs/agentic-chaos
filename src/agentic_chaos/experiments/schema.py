"""Validate and compile declarative experiment documents into `ChaosWorkflow`s.

Validation collects every problem it finds (with a location such as
``workflow[2].step.faults[0].burst_count``) instead of stopping at the first,
and never executes target code: targets compile to lazy callables that are
imported on first use, and `check_targets` only parses their source.
"""

import difflib
import inspect
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import agentic_chaos.agents  # noqa: F401 -- registers agent faults by name
from agentic_chaos.chaos.advanced import FaultCascade
from agentic_chaos.chaos.faults import FAULT_REGISTRY, BaseFault
from agentic_chaos.chaos.scope import Scope
from agentic_chaos.contracts.base import Contract
from agentic_chaos.contracts.registry import CONTRACT_REGISTRY, describe_contracts
from agentic_chaos.experiments.cron import CronSchedule
from agentic_chaos.safety import CircuitBreaker
from agentic_chaos.workflows.engine import ChaosWorkflow
from agentic_chaos.workflows.nodes import (
    HealthCheck,
    Parallel,
    Step,
    Suspend,
    Template,
    TemplateUse,
)
from agentic_chaos.workflows.targets import _is_file, _split, check_target, resolve_target

EXPERIMENT_VERSION = 1
Severity = Literal["error", "warning"]

_TOP_LEVEL = {
    "version",
    "name",
    "description",
    "target",
    "faults",
    "assertions",
    "repeat",
    "dry_run",
    "safety",
    "scope",
    "schedule",
    "templates",
    "workflow",
    "stop_on_failure",
}
_SINGLE_STEP_ONLY = ("faults", "assertions", "repeat")
_NODE_KEYS = {
    "step": {"name", "faults", "assertions", "repeat", "target", "dry_run", "safety", "scope"},
    "health_check": {
        "name",
        "target",
        "query",
        "expect_success",
        "expect_contains",
        "retries",
        "retry_delay_seconds",
        "halt_on_failure",
    },
    "parallel": {"name", "branches", "max_workers"},
    "suspend": {"name", "reason"},
    "use": {"template", "name", "with"},
}
_SAFETY_KEYS = {
    "max_cost_usd": "max_cost_usd",
    "max_failure_rate": "max_failure_rate",
    "failure_window": "window_size",
    "min_calls": "min_calls",
    "max_duration_seconds": "max_duration_seconds",
    "max_injections": "max_injections",
}
# Bounds checked before constructing a fault: (kind, minimum, maximum).
_BOUNDS: dict[str, tuple[str, float | None, float | None]] = {
    "probability": ("float", 0.0, 1.0),
    "seed": ("int", None, None),
    "burst_count": ("int", 0, None),
    "force_turns": ("int", 0, None),
    "after_chunks": ("int", 0, None),
    "status_code": ("int", None, None),
    "hang_seconds": ("float", 0.0, None),
    "retry_after": ("float", 0.0, None),
    "timeout_seconds": ("float", 0.0, None),
    "delay_seconds": ("float", 0.0, None),
    "delay_between": ("float", 0.0, None),
    "rate": ("float", 0.0, 1.0),
}
_STRINGS = {
    "mode",
    "strategy",
    "payload",
    "error_message",
    "tool_name",
    "from_node",
    "to_node",
}
_CODE_ONLY = {"degrade_fn"}
_PARAM = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True)
class ExperimentIssue:
    """One validation problem, located by a dotted/indexed path in the document."""

    location: str
    message: str
    severity: Severity = "error"

    def __str__(self) -> str:
        prefix = "warning: " if self.severity == "warning" else ""
        return f"{self.location}: {prefix}{self.message}"

    def as_json(self) -> dict[str, str]:
        return {"location": self.location, "message": self.message, "severity": self.severity}


class ExperimentError(ValueError):
    """An experiment document failed validation."""

    def __init__(self, source: str, issues: list[ExperimentIssue]) -> None:
        self.source = source
        self.issues = issues
        details = "\n".join(f"  {issue}" for issue in issues)
        super().__init__(f"invalid experiment {source}:\n{details}")


class LazyTarget:
    """A target spec that is imported the first time it is called."""

    def __init__(self, spec: str, base_dir: Path | None) -> None:
        self.spec = spec
        self.base_dir = base_dir
        self._resolved: Callable[..., Any] | None = None
        self.is_script = _is_file(_split(spec)[0]) and _split(spec)[1] is None

    def resolve(self) -> Callable[..., Any]:
        if self._resolved is None:
            self._resolved = resolve_target(self.spec, self.base_dir)
        return self._resolved

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.resolve()(*args, **kwargs)

    def __repr__(self) -> str:
        return f"LazyTarget({self.spec!r})"


@dataclass
class Experiment:
    """A validated experiment: its workflow plus schedule and run defaults."""

    name: str
    workflow: ChaosWorkflow
    document: dict[str, Any]
    source: str
    base_dir: Path | None
    description: str = ""
    schedule: CronSchedule | None = None
    timezone: str = "UTC"
    dry_run: bool = False
    warnings: list[ExperimentIssue] = field(default_factory=list)

    @property
    def kind(self) -> str:
        return "workflow" if "workflow" in self.document else "experiment"

    def metadata(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
            "source": self.source,
            "version": self.document.get("version", EXPERIMENT_VERSION),
        }
        if self.description:
            data["description"] = self.description
        if self.schedule is not None:
            data["schedule"] = {"cron": self.schedule.expression, "timezone": self.timezone}
        return data

    def run(
        self,
        *,
        dry_run: bool | None = None,
        approve: Any = None,
        resume_from: str | None = None,
    ) -> Any:
        """Run the compiled workflow (importing targets now) and return its report."""
        return self.workflow.run(
            dry_run=self.dry_run if dry_run is None else dry_run,
            approve=approve,
            resume_from=resume_from,
            experiment=self.metadata(),
        )


class _Compiler:
    def __init__(self, base_dir: Path | None, check_targets: bool) -> None:
        self.base_dir = base_dir
        self.check_targets = check_targets
        self.issues: list[ExperimentIssue] = []
        self.templates: dict[str, Any] = {}
        self.used_templates: set[str] = set()
        self.default_target: LazyTarget | None = None

    # -- reporting ----------------------------------------------------------

    def error(self, location: str, message: str) -> None:
        self.issues.append(ExperimentIssue(location, message))

    def warn(self, location: str, message: str) -> None:
        self.issues.append(ExperimentIssue(location, message, "warning"))

    def unknown_keys(self, location: str, data: dict[str, Any], allowed: set[str]) -> None:
        for key in sorted(set(data) - allowed, key=str):
            hint = _suggest(str(key), allowed)
            self.error(_join(location, str(key)), f"unknown field{hint}")

    # -- scalars ------------------------------------------------------------

    def string(self, location: str, value: Any, *, required: bool = False) -> str | None:
        if value is None and not required:
            return None
        if not isinstance(value, str) or not value.strip():
            self.error(location, "must be a non-empty string")
            return None
        return value

    def boolean(self, location: str, value: Any, default: bool) -> bool:
        if value is None:
            return default
        if not isinstance(value, bool):
            self.error(location, "must be true or false")
            return default
        return value

    def integer(self, location: str, value: Any, default: int, minimum: int) -> int:
        if value is None:
            return default
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            self.error(location, f"must be an integer >= {minimum}")
            return default
        return value

    def number(self, location: str, value: Any, default: float) -> float:
        if value is None:
            return default
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            self.error(location, "must be a finite number >= 0")
            return default
        return float(value)

    def target(self, location: str, value: Any) -> LazyTarget | None:
        spec = self.string(location, value)
        if spec is None:
            return None
        try:
            lazy = LazyTarget(spec, self.base_dir)
        except ValueError as exc:
            self.error(location, str(exc))
            return None
        if self.check_targets:
            problem = check_target(spec, self.base_dir)
            if problem is not None:
                self.error(location, problem)
        return lazy

    # -- building blocks ----------------------------------------------------

    def scope(self, location: str, value: Any) -> Scope | None:
        if value is None:
            return None
        try:
            return Scope.from_json(value)
        except ValueError as exc:
            self.error(location, str(exc))
            return None

    def safety(self, location: str, value: Any) -> CircuitBreaker | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            self.error(location, "must be a mapping of circuit-breaker limits")
            return None
        self.unknown_keys(location, value, set(_SAFETY_KEYS))
        kwargs = {_SAFETY_KEYS[k]: v for k, v in value.items() if k in _SAFETY_KEYS}
        try:
            return CircuitBreaker(**kwargs)
        except (TypeError, ValueError) as exc:
            self.error(location, str(exc))
            return None

    def faults(self, location: str, value: Any) -> list[BaseFault]:
        if value is None:
            return []
        if not isinstance(value, list):
            self.error(location, "must be a list of faults")
            return []
        faults = []
        for index, entry in enumerate(value):
            fault = self.fault(f"{location}[{index}]", entry)
            if fault is not None:
                faults.append(fault)
        return faults

    def fault(self, location: str, entry: Any) -> BaseFault | None:
        if isinstance(entry, str):
            entry = {"type": entry}
        if not isinstance(entry, dict):
            self.error(location, "must be a fault name or a mapping with a 'type'")
            return None
        options = dict(entry)
        name = options.pop("type", None)
        if not isinstance(name, str) or not name:
            self.error(_join(location, "type"), "is required (a fault name)")
            return None
        scope = self.scope(_join(location, "scope"), options.pop("scope", None))
        if name == "cascade":
            return self.cascade(location, options, scope)
        cls = FAULT_REGISTRY.get(name)
        if cls is None:
            hint = _suggest(name, set(FAULT_REGISTRY) | {"cascade"})
            self.error(_join(location, "type"), f"unknown fault '{name}'{hint}")
            return None
        if not self.parameters(location, name, cls, options):
            return None
        try:
            fault = cls(**options)
        except (TypeError, ValueError) as exc:
            self.error(location, f"invalid parameters for '{name}': {exc}")
            return None
        if scope is not None:
            fault.scope = scope
        return fault

    def parameters(
        self, location: str, name: str, cls: type[BaseFault], options: dict[str, Any]
    ) -> bool:
        ok = True
        params = inspect.signature(cls.__init__).parameters
        accepts_any = any(p.kind is p.VAR_KEYWORD for p in params.values())
        allowed = {key for key in params if key not in ("self", "scope")} - _CODE_ONLY
        for key, value in options.items():
            where = _join(location, str(key))
            if key in _CODE_ONLY:
                self.error(where, "takes a Python callable and cannot be set from an experiment")
                ok = False
            elif key not in allowed and not accepts_any:
                hint = _suggest(str(key), allowed)
                listed = ", ".join(sorted(allowed)) or "none"
                self.error(where, f"unknown parameter for '{name}'{hint} (allowed: {listed})")
                ok = False
            elif not self.bounded(where, str(key), value):
                ok = False
        return ok

    def bounded(self, location: str, key: str, value: Any) -> bool:
        if key in _STRINGS and value is not None and not isinstance(value, str):
            self.error(location, "must be a string")
            return False
        if key not in _BOUNDS:
            return True
        kind, low, high = _BOUNDS[key]
        if value is None and key == "seed":
            return True
        if kind == "int":
            valid = not isinstance(value, bool) and isinstance(value, int)
        else:
            valid = (
                not isinstance(value, bool)
                and isinstance(value, (int, float))
                and math.isfinite(value)
            )
        if not valid:
            self.error(location, f"must be {'an integer' if kind == 'int' else 'a finite number'}")
            return False
        if (low is not None and value < low) or (high is not None and value > high):
            span = f"between {low:g} and {high:g}" if high is not None else f">= {low:g}"
            self.error(location, f"{value!r} is out of range (must be {span})")
            return False
        return True

    def cascade(
        self, location: str, options: dict[str, Any], scope: Scope | None
    ) -> BaseFault | None:
        self.unknown_keys(location, options, {"first", "then", "delay_between"})
        first = self.fault(_join(location, "first"), options.get("first"))
        then = self.fault(_join(location, "then"), options.get("then"))
        delay = options.get("delay_between", 0)
        if not self.bounded(_join(location, "delay_between"), "delay_between", delay):
            return None
        if first is None or then is None:
            return None
        try:
            return FaultCascade(first, then, delay, scope=scope)
        except ValueError as exc:
            self.error(location, str(exc))
            return None

    def assertions(self, location: str, value: Any) -> list[Contract]:
        if value is None:
            return []
        if not isinstance(value, list):
            self.error(location, "must be a list of assertions")
            return []
        described = {entry["name"]: entry for entry in describe_contracts()}
        contracts = []
        for index, item in enumerate(value):
            where = f"{location}[{index}]"
            if isinstance(item, str):
                item = {item: True}
            if not isinstance(item, dict) or len(item) != 1:
                self.error(where, "must be a contract name or a one-key mapping {name: value}")
                continue
            ((name, argument),) = item.items()
            if name not in CONTRACT_REGISTRY:
                hint = _suggest(str(name), set(CONTRACT_REGISTRY))
                self.error(where, f"unknown assertion '{name}'{hint}")
                continue
            spec = described[name]
            where = _join(where, str(name))
            kwargs: dict[str, Any]
            if argument is True:
                kwargs = {}
            elif argument is False or argument is None:
                self.error(where, "must be true, a value or a mapping; remove it to disable")
                continue
            elif isinstance(argument, dict):
                kwargs = dict(argument)
                for key in sorted(set(kwargs) - set(spec["parameters"]), key=str):
                    listed = ", ".join(spec["parameters"]) or "none"
                    self.error(_join(where, str(key)), f"unknown parameter (allowed: {listed})")
                if set(kwargs) - set(spec["parameters"]):
                    continue
            elif not spec["positional"]:
                self.error(where, "takes no value; use true or a mapping of parameters")
                continue
            else:
                kwargs = {spec["positional"][0]: argument}
            try:
                contracts.append(CONTRACT_REGISTRY[name](**kwargs))
            except (TypeError, ValueError) as exc:
                self.error(where, str(exc))
        return contracts

    def schedule(self, location: str, value: Any) -> tuple[CronSchedule | None, str]:
        if value is None:
            return None, "UTC"
        if isinstance(value, str):
            value = {"cron": value}
        if not isinstance(value, dict):
            self.error(location, "must be a cron string or a mapping with 'cron'")
            return None, "UTC"
        self.unknown_keys(location, value, {"cron", "timezone"})
        zone_name = value.get("timezone", "UTC")
        zone = None
        if not isinstance(zone_name, str):
            self.error(_join(location, "timezone"), "must be an IANA time zone name")
        else:
            try:
                zone = ZoneInfo(zone_name)
            except (ZoneInfoNotFoundError, ValueError):
                self.error(_join(location, "timezone"), f"unknown time zone '{zone_name}'")
        try:
            schedule = CronSchedule.parse(value.get("cron", ""))
        except ValueError as exc:
            self.error(_join(location, "cron"), str(exc))
            return None, "UTC"
        if not schedule.next_runs(1, tz=zone):
            self.warn(_join(location, "cron"), "this schedule never fires")
        return schedule, zone_name if isinstance(zone_name, str) else "UTC"

    # -- nodes --------------------------------------------------------------

    def nodes(self, location: str, value: Any, stack: tuple[str, ...] = ()) -> list[Any]:
        if not isinstance(value, list) or not value:
            self.error(location, "must be a non-empty list of workflow nodes")
            return []
        nodes = []
        for index, item in enumerate(value):
            node = self.node(f"{location}[{index}]", item, stack)
            if node is not None:
                nodes.append(node)
        return nodes

    def node(self, location: str, item: Any, stack: tuple[str, ...]) -> Any:
        if not isinstance(item, dict) or len(item) != 1:
            self.error(location, f"must be a one-key mapping: one of {', '.join(_NODE_KEYS)}")
            return None
        ((kind, body),) = item.items()
        if kind not in _NODE_KEYS:
            hint = _suggest(str(kind), set(_NODE_KEYS))
            self.error(location, f"unknown node type '{kind}'{hint}")
            return None
        where = _join(location, kind)
        if body is None and kind == "suspend":
            body = {}
        if not isinstance(body, dict):
            self.error(where, "must be a mapping")
            return None
        self.unknown_keys(where, body, _NODE_KEYS[kind])
        try:
            if kind == "step":
                return self.step(where, body)
            if kind == "health_check":
                return self.health_check(where, body)
            if kind == "parallel":
                return self.parallel(where, body, stack)
            if kind == "suspend":
                name = self.string(_join(where, "name"), body.get("name"), required=True)
                reason = body.get("reason", "")
                if not isinstance(reason, str):
                    self.error(_join(where, "reason"), "must be a string")
                    reason = ""
                return Suspend(name, reason=reason) if name else None
            return self.use(where, body, stack)
        except ValueError as exc:
            self.error(where, str(exc))
            return None

    def step(self, location: str, body: dict[str, Any]) -> Step | None:
        name = self.string(_join(location, "name"), body.get("name"), required=True)
        faults = self.faults(_join(location, "faults"), body.get("faults"))
        contracts = self.assertions(_join(location, "assertions"), body.get("assertions"))
        repeat = self.integer(_join(location, "repeat"), body.get("repeat"), 1, 1)
        target = self.target(_join(location, "target"), body.get("target"))
        dry_run = self.boolean(_join(location, "dry_run"), body.get("dry_run"), False)
        breaker = self.safety(_join(location, "safety"), body.get("safety"))
        scope = self.scope(_join(location, "scope"), body.get("scope"))
        if target is None and self.default_target is None and "target" not in body:
            self.error(location, "has no target and the experiment defines no top-level target")
        if name is None:
            return None
        return Step(
            name,
            faults=faults,
            target=target,
            repeat=repeat,
            contracts=contracts,
            breaker=breaker,
            dry_run=dry_run,
            scope=scope,
        )

    def health_check(self, location: str, body: dict[str, Any]) -> HealthCheck | None:
        name = self.string(_join(location, "name"), body.get("name"))
        target = self.target(_join(location, "target"), body.get("target"))
        effective = target if target is not None else self.default_target
        if effective is None and "target" not in body:
            self.error(location, "has no target and the experiment defines no top-level target")
        if "query" in body and effective is not None and effective.is_script:
            self.error(_join(location, "query"), "needs a function target ('file.py:function')")
        contains = body.get("expect_contains")
        if contains is not None and not isinstance(contains, str):
            self.error(_join(location, "expect_contains"), "must be a string")
            contains = None
        kwargs: dict[str, Any] = {
            "fn": effective,
            "name": name,
            "expect_success": self.boolean(
                _join(location, "expect_success"), body.get("expect_success"), True
            ),
            "expect_contains": contains,
            "retries": self.integer(_join(location, "retries"), body.get("retries"), 0, 0),
            "retry_delay_seconds": self.number(
                _join(location, "retry_delay_seconds"), body.get("retry_delay_seconds"), 0.0
            ),
            "halt_on_failure": self.boolean(
                _join(location, "halt_on_failure"), body.get("halt_on_failure"), True
            ),
        }
        if "query" in body:
            kwargs["query"] = body["query"]
        return HealthCheck(**kwargs)

    def parallel(
        self, location: str, body: dict[str, Any], stack: tuple[str, ...]
    ) -> Parallel | None:
        branches_value = body.get("branches")
        if not isinstance(branches_value, list) or len(branches_value) < 2:
            self.error(_join(location, "branches"), "must be a list of at least two branches")
            return None
        branches: list[Any] = []
        for index, branch in enumerate(branches_value):
            where = f"{_join(location, 'branches')}[{index}]"
            if isinstance(branch, list):
                compiled = self.nodes(where, branch, stack)
                if compiled:
                    branches.append(compiled)
            else:
                node = self.node(where, branch, stack)
                if node is not None:
                    branches.append(node)
        name = self.string(_join(location, "name"), body.get("name"))
        workers = body.get("max_workers")
        if workers is not None:
            workers = self.integer(_join(location, "max_workers"), workers, 0, 1) or None
        if len(branches) != len(branches_value):
            return None
        return Parallel(*branches, name=name, max_workers=workers)

    def use(self, location: str, body: dict[str, Any], stack: tuple[str, ...]) -> Any:
        template_name = self.string(
            _join(location, "template"), body.get("template"), required=True
        )
        if template_name is None:
            return None
        definition = self.templates.get(template_name)
        if definition is None:
            hint = _suggest(template_name, set(self.templates))
            self.error(_join(location, "template"), f"unknown template '{template_name}'{hint}")
            return None
        if template_name in stack:
            cycle = " -> ".join((*stack, template_name))
            self.error(_join(location, "template"), f"recursive template use: {cycle}")
            return None
        self.used_templates.add(template_name)
        params = body.get("with", {})
        if not isinstance(params, dict):
            self.error(_join(location, "with"), "must be a mapping of template parameters")
            return None
        declared = definition.get("params") or {}
        for key in sorted(set(params) - set(declared), key=str):
            hint = _suggest(str(key), set(declared))
            self.error(_join(_join(location, "with"), str(key)), f"unknown parameter{hint}")
        values = {**declared, **params}
        missing: set[str] = set()
        steps = _substitute(definition.get("steps"), values, missing)
        for name in sorted(missing):
            self.error(location, f"template '{template_name}' references undefined ${{{name}}}")
        if missing:
            return None
        where = f"{location}<{template_name}>.steps"
        nodes = self.nodes(where, steps, (*stack, template_name))
        use_name = self.string(_join(location, "name"), body.get("name")) or template_name
        return TemplateUse(Template(template_name, nodes), use_name)

    def template_definitions(self, value: Any) -> None:
        if value is None:
            return
        if not isinstance(value, dict):
            self.error("templates", "must be a mapping of template name to definition")
            return
        for name, definition in value.items():
            where = _join("templates", str(name))
            if not isinstance(definition, dict):
                self.error(where, "must be a mapping with 'steps' (and optional 'params')")
                continue
            self.unknown_keys(where, definition, {"params", "steps"})
            params = definition.get("params")
            if params is not None and not isinstance(params, dict):
                self.error(_join(where, "params"), "must be a mapping of parameter defaults")
                continue
            if not isinstance(definition.get("steps"), list) or not definition["steps"]:
                self.error(_join(where, "steps"), "must be a non-empty list of workflow nodes")
                continue
            self.templates[str(name)] = definition

    # -- document -----------------------------------------------------------

    def document(self, data: Any, source: str) -> Experiment | None:
        if not isinstance(data, dict):
            self.error("<document>", "an experiment must be a mapping at the top level")
            return None
        self.unknown_keys("<document>", data, _TOP_LEVEL)
        version = data.get("version", EXPERIMENT_VERSION)
        if version != EXPERIMENT_VERSION:
            self.error("version", f"unsupported experiment version {version!r}; use 1")
        name = self.string("name", data.get("name"), required=True)
        description = data.get("description", "")
        if not isinstance(description, str):
            self.error("description", "must be a string")
            description = ""
        self.default_target = self.target("target", data.get("target"))
        dry_run = self.boolean("dry_run", data.get("dry_run"), False)
        stop = self.boolean("stop_on_failure", data.get("stop_on_failure"), True)
        breaker = self.safety("safety", data.get("safety"))
        scope = self.scope("scope", data.get("scope"))
        schedule, zone = self.schedule("schedule", data.get("schedule"))
        self.template_definitions(data.get("templates"))
        nodes: list[Any]
        if "workflow" in data:
            for key in _SINGLE_STEP_ONLY:
                if key in data:
                    self.error(key, "belongs to a step in workflow experiments")
            nodes = self.nodes("workflow", data["workflow"])
            breaker_for_steps = breaker
        else:
            if "faults" not in data:
                self.error("<document>", "needs either 'faults' or a 'workflow'")
            if self.default_target is None and "target" not in data:
                self.error("target", "is required")
            faults = self.faults("faults", data.get("faults"))
            if "faults" in data and not faults and not self._located("faults"):
                self.error("faults", "must list at least one fault")
            contracts = self.assertions("assertions", data.get("assertions"))
            repeat = self.integer("repeat", data.get("repeat"), 1, 1)
            nodes = []
            if name is not None:
                nodes = [Step(name.strip(), faults=faults, repeat=repeat, contracts=contracts)]
            breaker_for_steps = breaker
        for template in sorted(set(self.templates) - self.used_templates):
            self.warn(_join("templates", template), "is defined but never used")
        if self.has_errors or name is None:
            return None
        try:
            workflow = ChaosWorkflow(
                name,
                nodes,
                target=self.default_target,
                stop_on_failure=stop,
                breaker=breaker_for_steps,
                scope=scope,
            )
        except ValueError as exc:
            self.error("workflow" if "workflow" in data else "<document>", str(exc))
            return None
        return Experiment(
            name=name,
            workflow=workflow,
            document=data,
            source=source,
            base_dir=self.base_dir,
            description=description,
            schedule=schedule,
            timezone=zone,
            dry_run=dry_run,
            warnings=[issue for issue in self.issues if issue.severity == "warning"],
        )

    def _located(self, prefix: str) -> bool:
        return any(issue.location.startswith(prefix) for issue in self.issues)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)


def _join(location: str, key: str) -> str:
    if location == "<document>":
        return key
    return f"{location}.{key}"


def _suggest(value: str, choices: set[str]) -> str:
    matches = difflib.get_close_matches(value, sorted(choices), n=1, cutoff=0.6)
    return f"; did you mean '{matches[0]}'?" if matches else ""


def _substitute(value: Any, params: dict[str, Any], missing: set[str]) -> Any:
    """Replace ``${name}`` with template parameters; a whole-string reference keeps its type."""
    if isinstance(value, str):
        whole = _PARAM.fullmatch(value)
        if whole:
            if whole.group(1) not in params:
                missing.add(whole.group(1))
                return value
            return params[whole.group(1)]

        def replace(match: re.Match[str]) -> str:
            if match.group(1) not in params:
                missing.add(match.group(1))
                return match.group(0)
            return str(params[match.group(1)])

        return _PARAM.sub(replace, value.replace("$${", "\0")).replace("\0", "${")
    if isinstance(value, list):
        return [_substitute(item, params, missing) for item in value]
    if isinstance(value, dict):
        return {key: _substitute(item, params, missing) for key, item in value.items()}
    return value


def compile_document(
    data: Any,
    *,
    source: str = "<experiment>",
    base_dir: Path | None = None,
    check_targets: bool = True,
) -> tuple[Experiment | None, list[ExperimentIssue]]:
    """Validate a parsed document; return the experiment (None on errors) and all issues."""
    compiler = _Compiler(base_dir, check_targets)
    experiment = compiler.document(data, source)
    return experiment, compiler.issues
