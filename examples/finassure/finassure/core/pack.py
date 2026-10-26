"""Abstract Pack Contract for pluggable workflow packs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from finassure.core.models import CaseApplicant, OracleResult, WorkflowOutcome


class BaseWorkflowPack(ABC):
    """Abstract base class that all FinAssure workflow packs must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Domain name of the pack (e.g. 'underwriting' or 'kyc')."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Version identifier, e.g. 'v1' (naive) or 'v2' (hardened)."""
        pass

    @property
    def required_tools(self) -> list[str]:
        """Verification tools that must have run before an approval."""
        return ["bureau_lookup"]

    @abstractmethod
    def oracle(self, case: CaseApplicant) -> OracleResult:
        """Deterministic policy oracle defining ground truth for a given case."""
        pass

    @abstractmethod
    def run(self, case: CaseApplicant) -> WorkflowOutcome:
        """Execute the multi-agent workflow for this case."""
        pass

    @abstractmethod
    def generate_cases(self, count: int = 200, seed: int = 42) -> Sequence[CaseApplicant]:
        """Generate synthetic test cases for evaluation."""
        pass
