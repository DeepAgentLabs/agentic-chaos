"""pytest plugin: run ``@pytest.mark.chaos`` tests under faults and check contracts.

Registered through the ``pytest11`` entry point, so installing agentic-chaos is
enough. Markers do nothing unless chaos is enabled with ``--chaos`` (or the
``chaos = true`` ini option): without it, marked tests run normally.

This module imports only pytest and the standard library at load time;
agentic_chaos is imported when a chaos test actually runs.
"""

import copy
import functools
import hashlib
import inspect
import json
import re
from collections.abc import Callable, Coroutine, Generator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

import pytest

if TYPE_CHECKING:
    from agentic_chaos.agents.topology import TopologyTracker
    from agentic_chaos.chaos.context import ChaosSession
    from agentic_chaos.chaos.faults import BaseFault
    from agentic_chaos.contracts import Contract, ContractReport
    from agentic_chaos.models.report import ChaosReport
    from agentic_chaos.probes import Probe, ProbeResult
    from agentic_chaos.safety import CircuitBreaker

MARKER_HELP = (
    "chaos(faults=None, *, profile=None, profile_file='chaos.toml', contracts=(), "
    "must_recover=False, baseline=False, breaker=None, dry_run=False, probes=(), "
    "min_score=None): run the test under agentic-chaos faults, check contracts, run "
    "probes and gate on the resilience score. Inactive unless pytest runs with --chaos."
)

_MARKER_KWARGS = {
    "faults",
    "profile",
    "profile_file",
    "contracts",
    "must_recover",
    "baseline",
    "breaker",
    "dry_run",
    "probes",
    "min_score",
}


@dataclass
class ChaosOutcome:
    """What one chaos test produced, kept for the terminal summary."""

    nodeid: str
    report: "ChaosReport"
    contracts: "ContractReport | None"
    baseline: "ChaosReport | None" = None


@dataclass
class PluginState:
    enabled: bool
    report_dir: Path | None
    global_contracts: list[str]
    outcomes: list[ChaosOutcome] = field(default_factory=list)


_STATE = pytest.StashKey[PluginState]()
_IN_BASELINE = pytest.StashKey[bool]()
_LIVE_SESSION = pytest.StashKey["ChaosSession | None"]()


class ChaosHandle:
    """What the ``chaos`` fixture returns: access to the test's live chaos session.

    Every method is a safe no-op when chaos is disabled or no session is active,
    so the same test body runs with and without ``--chaos``.
    """

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.tracker: TopologyTracker | None = None
        self.report: ChaosReport | None = None
        self.baseline_report: ChaosReport | None = None
        self.contract_report: ContractReport | None = None

    @property
    def session(self) -> "ChaosSession | None":
        """The chaos session active right now (the baseline one during a baseline run)."""
        if not self.enabled:
            return None
        from agentic_chaos.chaos.context import get_active_session

        return get_active_session()

    @property
    def active(self) -> bool:
        return self.session is not None

    def record_cost(self, cost_usd: float) -> None:
        session = self.session
        if session is not None:
            session.record_cost(cost_usd)

    def record_usage(self, **usage: Any) -> None:
        session = self.session
        if session is not None:
            session.record_usage(**usage)

    def attach_topology(self, tracker: "TopologyTracker") -> "TopologyTracker":
        """Use this tracker's topology for the run (needed when it was not auto-activated)."""
        self.tracker = tracker
        return tracker


_HANDLE = pytest.StashKey[ChaosHandle]()


@dataclass
class ChaosSpec:
    """Validated ``@pytest.mark.chaos`` arguments."""

    faults: "str | Sequence[str | BaseFault] | None" = None
    profile: str | None = None
    profile_file: str | Path = "chaos.toml"
    contracts: "list[Contract]" = field(default_factory=list)
    must_recover: bool = False
    baseline: bool = False
    breaker: "CircuitBreaker | None" = None
    dry_run: bool = False
    probes: "Sequence[Probe]" = ()
    min_score: float | None = None

    @classmethod
    def from_marker(cls, marker: pytest.Mark, global_contracts: Sequence[str]) -> "ChaosSpec":
        from agentic_chaos.contracts import Contract, parse_contract

        if len(marker.args) > 1:
            raise ValueError("pass faults as the only positional argument")
        unknown = set(marker.kwargs) - _MARKER_KWARGS
        if unknown:
            raise ValueError(f"unknown argument(s): {', '.join(sorted(unknown))}")
        kwargs = dict(marker.kwargs)
        if marker.args:
            if "faults" in kwargs:
                raise ValueError("faults given both positionally and by keyword")
            kwargs["faults"] = marker.args[0]
        contracts = kwargs.pop("contracts", ())
        if isinstance(contracts, Contract):
            contracts = [contracts]
        spec = cls(**kwargs)
        spec.contracts = [
            parse_contract(item) if isinstance(item, str) else item for item in contracts
        ]
        spec.contracts.extend(parse_contract(item) for item in global_contracts)
        if not all(isinstance(item, Contract) for item in spec.contracts):
            raise ValueError("contracts must be Contract instances or spec strings")
        if (spec.faults is None) == (spec.profile is None):
            raise ValueError("give exactly one of faults=[...] or profile='name'")
        if spec.baseline and spec.dry_run:
            raise ValueError("baseline=True compares against a dry run; drop dry_run=True")
        from agentic_chaos.probes import check_probes

        spec.probes = check_probes(spec.probes)
        if spec.min_score is not None and (
            isinstance(spec.min_score, bool)
            or not isinstance(spec.min_score, (int, float))
            or not 0 <= spec.min_score <= 100
        ):
            raise ValueError("min_score must be a number between 0 and 100")
        spec.fresh_faults()  # validate fault names and profiles before running anything
        return spec

    def fresh_faults(self) -> "list[BaseFault]":
        """New fault state for every run: burst counters and RNGs never carry over."""
        from agentic_chaos.chaos.faults import BaseFault, resolve_faults
        from agentic_chaos.chaos.profiles import load_profile

        if self.profile is not None:
            return load_profile(self.profile, self.profile_file)
        assert self.faults is not None
        if isinstance(self.faults, (str, BaseFault)):
            entries: Sequence[str | BaseFault] = (
                [self.faults] if isinstance(self.faults, BaseFault) else self.faults.split(",")
            )
        else:
            entries = self.faults
        prepared: list[str | BaseFault] = []
        for entry in entries:
            if isinstance(entry, BaseFault):
                prepared.append(copy.deepcopy(entry))
            elif isinstance(entry, str):
                if entry.strip():
                    prepared.append(entry.strip())
            else:
                raise ValueError(
                    f"faults entries must be fault names or BaseFault instances, got {entry!r}"
                )
        faults = resolve_faults(prepared)
        if not faults:
            raise ValueError("faults must name at least one fault")
        return faults

    def all_contracts(self) -> "list[Contract]":
        from agentic_chaos.contracts import RecoveredAfterFailure

        contracts = list(self.contracts)
        if self.must_recover and not any(
            isinstance(item, RecoveredAfterFailure) for item in contracts
        ):
            contracts.insert(0, RecoveredAfterFailure())
        return contracts


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("agentic-chaos", "agentic-chaos fault injection")
    group.addoption(
        "--chaos",
        action="store_true",
        default=None,
        help="Activate @pytest.mark.chaos markers (without it, marked tests run normally).",
    )
    group.addoption(
        "--chaos-report-dir",
        default=None,
        metavar="DIR",
        help="Write each chaos test's ChaosReport and contract results as JSON into DIR.",
    )
    group.addoption(
        "--chaos-contract",
        action="append",
        default=[],
        metavar="SPEC",
        help="Contract applied to every chaos test, e.g. 'no_retry_storm:10'. Repeatable.",
    )
    parser.addini("chaos", type="bool", default=False, help="Enable chaos markers by default.")
    parser.addini("chaos_report_dir", default="", help="Default for --chaos-report-dir.")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", MARKER_HELP)
    option = config.getoption("--chaos")
    enabled = bool(option) if option is not None else bool(config.getini("chaos"))
    report_dir = config.getoption("--chaos-report-dir") or config.getini("chaos_report_dir")
    config.stash[_STATE] = PluginState(
        enabled=enabled,
        report_dir=Path(report_dir) if report_dir else None,
        global_contracts=list(config.getoption("--chaos-contract") or []),
    )


def pytest_report_header(config: pytest.Config) -> str | None:
    state = config.stash.get(_STATE, None)
    if state is None or not state.enabled:
        return None
    return "agentic-chaos: chaos markers enabled"


@pytest.fixture
def chaos(request: pytest.FixtureRequest) -> ChaosHandle:
    """Handle on the current test's chaos session (inactive without --chaos)."""
    node: pytest.Item = request.node
    handle = node.stash.get(_HANDLE, None)
    if handle is None:
        state = request.config.stash.get(_STATE, None)
        marked = node.get_closest_marker("chaos") is not None
        handle = ChaosHandle(enabled=bool(state and state.enabled and marked))
        node.stash[_HANDLE] = handle
    return handle


def _chaos_active(item: pytest.Item) -> bool:
    state = item.config.stash.get(_STATE, None)
    return bool(state and state.enabled and item.get_closest_marker("chaos") is not None)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Generator[None, object, object]:
    """Bind the session inside coroutine tests.

    Async plugins (pytest-asyncio, anyio) run the test coroutine in an event
    loop context created before the chaos session exists, so the session's
    context variable would not be visible there. Wrapping the coroutine
    function sets it inside the task instead.
    """
    original = getattr(item, "obj", None)
    if not (
        isinstance(item, pytest.Function)
        and _chaos_active(item)
        and inspect.iscoroutinefunction(original)
    ):
        return (yield)
    item.obj = _bind_session(item, original)
    try:
        return (yield)
    finally:
        item.obj = original


def _bind_session(
    item: pytest.Function, fn: Callable[..., Coroutine[Any, Any, Any]]
) -> Callable[..., Coroutine[Any, Any, Any]]:
    from agentic_chaos.agents.topology import get_active_tracker, reset_active_tracker
    from agentic_chaos.chaos.context import active_session

    @functools.wraps(fn)
    async def bound(*args: Any, **kwargs: Any) -> Any:
        session = item.stash.get(_LIVE_SESSION, None)
        if session is None or active_session.get() is session:
            return await fn(*args, **kwargs)
        before = get_active_tracker()
        token = active_session.set(session)
        try:
            return await fn(*args, **kwargs)
        finally:
            active_session.reset(token)
            tracker = get_active_tracker()
            if tracker is not None and tracker is not before:
                handle = item.stash.get(_HANDLE, None)
                if handle is not None and handle.tracker is None:
                    handle.tracker = tracker
                # Deactivate here, in the task's context: an event loop that
                # outlives the test would otherwise keep the tracker active.
                try:
                    tracker.deactivate()
                except (ValueError, RuntimeError):
                    reset_active_tracker()

    return bound


@pytest.hookimpl(wrapper=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> Generator[None, object, object]:
    state = pyfuncitem.config.stash.get(_STATE, None)
    marker = pyfuncitem.get_closest_marker("chaos")
    if (
        state is None
        or not state.enabled
        or marker is None
        or pyfuncitem.stash.get(_IN_BASELINE, False)
    ):
        return (yield)

    try:
        spec = ChaosSpec.from_marker(marker, state.global_contracts)
    except (ValueError, TypeError, OSError) as exc:
        pytest.fail(f"invalid @pytest.mark.chaos: {exc}", pytrace=False)

    handle = pyfuncitem.stash.get(_HANDLE, None)
    if handle is None:
        handle = ChaosHandle(enabled=True)
        pyfuncitem.stash[_HANDLE] = handle

    baseline = _run_baseline(pyfuncitem, spec, handle) if spec.baseline else None

    from agentic_chaos.agents.topology import get_active_tracker
    from agentic_chaos.chaos.session import chaos_session
    from agentic_chaos.probes import run_probes
    from agentic_chaos.resilience import compute_resilience

    probe_results = run_probes(spec.probes, "pre")
    unsteady = [result for result in probe_results if not result.passed]
    if unsteady:
        _fail_unsteady(pyfuncitem, state, handle, probe_results, unsteady)

    handle.tracker = None
    tracker_before = get_active_tracker()
    error: BaseException | None = None
    result: object = None
    with chaos_session(spec.fresh_faults(), breaker=spec.breaker, dry_run=spec.dry_run) as session:
        pyfuncitem.stash[_LIVE_SESSION] = session
        try:
            result = yield
        except BaseException as exc:
            error = exc
        finally:
            pyfuncitem.stash[_LIVE_SESSION] = None
        if error is None or not _is_control_flow(error):
            probe_results.extend(run_probes(spec.probes, "during"))
    if error is not None and _is_control_flow(error):
        raise error
    probe_results.extend(run_probes(spec.probes, "post"))

    report = session.to_report(
        pyfuncitem.name,
        error=error,
        agent_topology=_take_topology(handle, tracker_before),
    )
    report.probes = [probe_result.as_json() for probe_result in probe_results]
    score = compute_resilience(report, baseline=baseline)
    report.resilience = score.as_json()
    contracts = spec.all_contracts()
    contract_report = None
    if contracts:
        from agentic_chaos.contracts import check_contracts

        contract_report = check_contracts(report, contracts, baseline=baseline)
    handle.report, handle.baseline_report, handle.contract_report = (
        report,
        baseline,
        contract_report,
    )
    state.outcomes.append(ChaosOutcome(pyfuncitem.nodeid, report, contract_report, baseline))
    _write_artifacts(state, pyfuncitem.nodeid, report, baseline, contract_report)
    if contract_report is not None:
        pyfuncitem.add_report_section("call", "chaos contracts", contract_report.summary())
    pyfuncitem.add_report_section("call", "chaos resilience", score.summary())

    if error is not None:
        raise error
    if contract_report is not None:
        contract_report.raise_for_failures()
    if spec.min_score is not None and not score.meets(spec.min_score):
        raise AssertionError(f"{score.summary()}; required at least {spec.min_score:g}")
    return result


def _fail_unsteady(
    item: pytest.Function,
    state: PluginState,
    handle: ChaosHandle,
    probe_results: "Sequence[ProbeResult]",
    unsteady: "Sequence[ProbeResult]",
) -> NoReturn:
    """Record an uninjected, inconclusive report (outcome and artifacts), then fail."""
    from datetime import datetime, timezone

    from agentic_chaos.models.report import ChaosReport
    from agentic_chaos.resilience import compute_resilience

    now = datetime.now(timezone.utc)
    report = ChaosReport(
        name=item.name,
        start_time=now,
        end_time=now,
        probes=[result.as_json() for result in probe_results],
    )
    score = compute_resilience(report)
    score.reasons.append("chaos was not injected")
    report.resilience = score.as_json()
    handle.report = report
    state.outcomes.append(ChaosOutcome(item.nodeid, report, None))
    _write_artifacts(state, item.nodeid, report, None, None)
    details = "; ".join(f"{r.probe}: {r.message}" for r in unsteady)
    pytest.fail(f"pre-chaos probes failed, no fault injected: {details}", pytrace=False)


def _run_baseline(item: pytest.Function, spec: ChaosSpec, handle: ChaosHandle) -> "ChaosReport":
    """Run the test once as a dry run: same fault selection, nothing injected."""
    from agentic_chaos.agents.topology import get_active_tracker
    from agentic_chaos.chaos.session import chaos_session

    handle.tracker = None
    tracker_before = get_active_tracker()
    error: BaseException | None = None
    item.stash[_IN_BASELINE] = True
    try:
        with chaos_session(spec.fresh_faults(), breaker=spec.breaker, dry_run=True) as session:
            item.stash[_LIVE_SESSION] = session
            try:
                item.ihook.pytest_pyfunc_call(pyfuncitem=item)
            except BaseException as exc:
                error = exc
    finally:
        item.stash[_IN_BASELINE] = False
        item.stash[_LIVE_SESSION] = None
    if error is not None:
        if _is_control_flow(error):
            raise error
        pytest.fail(
            f"chaos baseline run (no faults injected) failed: {type(error).__name__}: {error}",
            pytrace=False,
        )
    return session.to_report(
        f"{item.name}[baseline]", agent_topology=_take_topology(handle, tracker_before)
    )


def _is_control_flow(error: BaseException) -> bool:
    """skip / xfail / exit / Ctrl-C end the test without a chaos result."""
    return isinstance(
        error,
        (pytest.skip.Exception, pytest.xfail.Exception, pytest.exit.Exception, KeyboardInterrupt),
    )


def _take_topology(handle: ChaosHandle, before: "TopologyTracker | None") -> dict[str, Any] | None:
    """Topology from an attached tracker, or one the test auto-activated."""
    from agentic_chaos.agents.topology import get_active_tracker, reset_active_tracker

    tracker = handle.tracker
    if tracker is None:
        current = get_active_tracker()
        if current is not None and current is not before:
            tracker = current
            try:
                current.deactivate()
            except (ValueError, RuntimeError):
                reset_active_tracker()
    handle.tracker = None
    return tracker.topology.as_json() if tracker is not None else None


def _artifact_stem(nodeid: str) -> str:
    """Readable, filesystem-safe and unique: sanitizing alone can map two IDs together."""
    readable = re.sub(r"[^A-Za-z0-9_.-]+", "_", nodeid).strip("_")[:120] or "chaos_test"
    digest = hashlib.sha256(nodeid.encode("utf-8")).hexdigest()[:12]
    return f"{readable}-{digest}"


def _write_artifacts(
    state: PluginState,
    nodeid: str,
    report: "ChaosReport",
    baseline: "ChaosReport | None",
    contracts: "ContractReport | None",
) -> None:
    if state.report_dir is None:
        return
    state.report_dir.mkdir(parents=True, exist_ok=True)
    stem = _artifact_stem(nodeid)
    (state.report_dir / f"{stem}.chaos.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    if baseline is not None:
        (state.report_dir / f"{stem}.baseline.json").write_text(
            baseline.model_dump_json(indent=2), encoding="utf-8"
        )
    if contracts is not None:
        payload = {"nodeid": nodeid, **contracts.as_json()}
        (state.report_dir / f"{stem}.contracts.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )


def pytest_terminal_summary(terminalreporter: Any, config: pytest.Config) -> None:
    state = config.stash.get(_STATE, None)
    if state is None or not state.enabled or not state.outcomes:
        return
    checked = [outcome for outcome in state.outcomes if outcome.contracts is not None]
    failing = [outcome for outcome in checked if outcome.contracts and not outcome.contracts.passed]
    events = sum(len(outcome.report.chaos_events) for outcome in state.outcomes)
    terminalreporter.section("agentic-chaos")
    terminalreporter.write_line(
        f"{len(state.outcomes)} chaos test(s), {events} fault event(s), "
        f"{len(checked) - len(failing)}/{len(checked)} passed their contracts"
    )
    scores = [o.report.resilience_score for o in state.outcomes]
    scored = [value for value in scores if value is not None]
    if scored:
        terminalreporter.write_line(
            f"resilience scores: lowest {min(scored)}/100, {len(scored)}/{len(scores)} scored"
        )
    for outcome in failing:
        assert outcome.contracts is not None
        for result in outcome.contracts.failures:
            terminalreporter.write_line(
                f"  {outcome.nodeid}: [{result.status}] {result.contract}: {result.message}"
            )
    if state.report_dir is not None:
        terminalreporter.write_line(f"chaos reports written to {state.report_dir}")
