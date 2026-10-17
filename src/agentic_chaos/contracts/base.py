"""Contract protocol, results and the `check_contracts()` entry point.

A contract is a pass/fail check over a finished `ChaosReport` (and, for the
comparative contracts, a baseline report). It reads the same native JSON that
AgenticLens, Control Tower and MCP consume, so a contract failure and a
downstream recommendation come from one record of the run.

Contracts fail closed: when the report cannot show what a contract needs (no
baseline, no injected failure, a truncated call log), the result is
``inconclusive``, and an inconclusive result does not pass.
"""

import json
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Literal

from agentic_chaos.models.report import ChaosReport

Status = Literal["passed", "failed", "inconclusive"]

ReportLike = ChaosReport | Mapping[str, Any] | str | Path


@dataclass(frozen=True)
class ContractResult:
    """Outcome of one contract against one report."""

    contract: str
    status: Status
    message: str
    parameters: dict[str, Any] = field(default_factory=dict)
    observed: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def as_json(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "status": self.status,
            "message": self.message,
            "parameters": self.parameters,
            "observed": self.observed,
        }


class Contract(ABC):
    """A reusable pass/fail check over a chaos report."""

    name: ClassVar[str]

    @abstractmethod
    def check(self, report: ChaosReport, *, baseline: ChaosReport | None = None) -> ContractResult:
        """Evaluate this contract; never raises for a failing run."""
        raise NotImplementedError

    def parameters(self) -> dict[str, Any]:
        """JSON-safe constructor parameters, recorded with each result."""
        return {}

    def result(self, status: Status, message: str, **observed: Any) -> ContractResult:
        """Build a result carrying this contract's name and parameters."""
        return ContractResult(
            contract=self.name,
            status=status,
            message=message,
            parameters=self.parameters(),
            observed=observed,
        )

    def __repr__(self) -> str:
        args = ", ".join(f"{key}={value!r}" for key, value in self.parameters().items())
        return f"{type(self).__name__}({args})"


@dataclass(frozen=True)
class ContractReport:
    """All contract results for one report; `passed` only when every result passed."""

    report_id: str
    report_name: str
    results: list[ContractResult]
    baseline_report_id: str | None = None

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    @property
    def failures(self) -> list[ContractResult]:
        """Results that did not pass, including inconclusive ones."""
        return [result for result in self.results if not result.passed]

    def summary(self) -> str:
        lines = [
            f"{len(self.results) - len(self.failures)}/{len(self.results)} chaos contracts "
            f"passed for '{self.report_name}'"
        ]
        lines.extend(
            f"  [{result.status}] {result.contract}: {result.message}" for result in self.results
        )
        return "\n".join(lines)

    def as_json(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "report_name": self.report_name,
            "baseline_report_id": self.baseline_report_id,
            "passed": self.passed,
            "results": [result.as_json() for result in self.results],
        }

    def raise_for_failures(self) -> None:
        """Raise `ContractViolationError` if any contract failed or was inconclusive."""
        if not self.passed:
            raise ContractViolationError(self)


class ContractViolationError(AssertionError):
    """Raised when chaos contracts do not pass.

    Subclasses `AssertionError` so pytest reports it as an ordinary test
    failure, with the contract summary as the message.
    """

    def __init__(self, contract_report: ContractReport) -> None:
        super().__init__(contract_report.summary())
        self.contract_report = contract_report


def load_report(report: ReportLike) -> ChaosReport:
    """Accept a `ChaosReport`, its JSON-compatible dict, or a path to saved JSON."""
    if isinstance(report, ChaosReport):
        return report
    if isinstance(report, (str, Path)):
        return ChaosReport.model_validate(json.loads(Path(report).read_text(encoding="utf-8")))
    return ChaosReport.model_validate(dict(report))


def check_contracts(
    report: ReportLike,
    contracts: Iterable[Contract],
    *,
    baseline: ReportLike | None = None,
) -> ContractReport:
    """Evaluate every contract against `report` (and `baseline`, when given)."""
    chaos_report = load_report(report)
    baseline_report = load_report(baseline) if baseline is not None else None
    results = [
        contract.check(chaos_report, baseline=baseline_report) for contract in list(contracts)
    ]
    return ContractReport(
        report_id=chaos_report.id,
        report_name=chaos_report.name,
        results=results,
        baseline_report_id=baseline_report.id if baseline_report is not None else None,
    )


def assert_contracts(
    report: ReportLike,
    contracts: Iterable[Contract],
    *,
    baseline: ReportLike | None = None,
) -> ContractReport:
    """`check_contracts()`, raising `ContractViolationError` unless all pass."""
    contract_report = check_contracts(report, contracts, baseline=baseline)
    contract_report.raise_for_failures()
    return contract_report
