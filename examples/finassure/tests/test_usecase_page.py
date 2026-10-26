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

# (pack, version): (verdict, runs, unsupported approvals, silent failure %, safe degradation %,
#                   overall score, clean-run escalation %, cost per application)
EXPECTED = {
    ("underwriting", "v1"): ("FAILED", 90, 34, 37.5, 62.5, 0.83, 0.0, 0.0015),
    ("underwriting", "v2"): ("PASSED", 90, 0, 0.0, 100.0, 0.94, 30.0, 0.0028),
    ("kyc", "v1"): ("FAILED", 50, 30, 50.0, 50.0, 0.80, 0.0, 0.0015),
    ("kyc", "v2"): ("PASSED", 50, 0, 0.0, 100.0, 0.91, 0.0, 0.0028),
    ("aml", "v1"): ("FAILED", 40, 17, 33.3, 66.7, 0.86, 0.0, 0.0015),
    ("aml", "v2"): ("PASSED", 40, 0, 0.0, 100.0, 0.92, 0.0, 0.0028),
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

    (expected_verdict, runs, unsupported, silent, safe, score, escalation, cost) = EXPECTED[
        (pack_name, version)
    ]
    assert verdict.verdict == expected_verdict
    assert verdict.total_runs == runs
    assert verdict.unsupported_approvals_count == unsupported
    assert round(verdict.silent_failure_rate * 100, 1) == silent
    assert round(verdict.safe_degradation_rate * 100, 1) == safe
    assert round(verdict.overall_score, 2) == score
    assert round(verdict.escalation_rate * 100, 1) == escalation
    assert verdict.cost_per_application == cost
    # Wall-clock latency varies; the page quotes it only approximately.
    assert verdict.p95_latency_ms < 4000
