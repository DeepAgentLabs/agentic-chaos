"""Pins the gate results quoted on the published FinAssure use-case page.

usecases/finassure-release-gate.md reports these numbers from
`python scripts/seed_baseline.py`; if a change moves them, update the page too.
"""

import pytest
from finassure.config import settings
from finassure.core.gate import evaluate_release_gate
from finassure.core.runner import ExperimentRunner
from finassure.core.scenario import load_scenarios_from_yaml
from finassure.packs.aml import AMLPack
from finassure.packs.kyc import KYCPack
from finassure.packs.underwriting import UnderwritingPack

PACKS = {"underwriting": (UnderwritingPack, 42), "kyc": (KYCPack, 77), "aml": (AMLPack, 88)}

# (pack, version): (verdict, runs, unsupported approvals, silent failure %, safe degradation %)
EXPECTED = {
    ("underwriting", "v1"): ("FAILED", 90, 29, 38.8, 61.3),
    ("underwriting", "v2"): ("PASSED", 90, 0, 0.0, 100.0),
    ("kyc", "v1"): ("FAILED", 50, 21, 45.0, 55.0),
    ("kyc", "v2"): ("PASSED", 50, 0, 0.0, 100.0),
    ("aml", "v1"): ("FAILED", 40, 10, 33.3, 66.7),
    ("aml", "v2"): ("PASSED", 40, 0, 0.0, 100.0),
}


@pytest.mark.parametrize(("pack_name", "version"), sorted(EXPECTED))
def test_seed_baseline_matches_usecase_page(pack_name, version):
    pack_cls, seed = PACKS[pack_name]
    scenarios = load_scenarios_from_yaml(
        settings.ROOT_DIR / "finassure" / "packs" / pack_name / "scenarios.yaml"
    )
    pack = pack_cls(version)
    cases = pack_cls("v1").generate_cases(count=10, seed=seed)
    verdict = evaluate_release_gate(
        ExperimentRunner(pack).run_experiment(scenarios, cases, reps_override=1)
    )

    expected_verdict, runs, unsupported, silent, safe = EXPECTED[(pack_name, version)]
    assert verdict.verdict == expected_verdict
    assert verdict.total_runs == runs
    assert verdict.unsupported_approvals_count == unsupported
    assert round(verdict.silent_failure_rate * 100, 1) == silent
    assert round(verdict.safe_degradation_rate * 100, 1) == safe
