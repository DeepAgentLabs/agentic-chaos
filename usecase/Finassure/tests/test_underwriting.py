"""Integration tests verifying v1 fails and v2 passes the release gate."""

import pytest
from finassure.packs.underwriting import UnderwritingPack, generate_underwriting_cases
from finassure.core.scenario import load_scenarios_from_yaml
from finassure.core.runner import ExperimentRunner
from finassure.core.gate import evaluate_release_gate
from finassure.config import settings


def test_v1_fails_bureau_outage_unsupported_approval():
    scenarios = load_scenarios_from_yaml(settings.ROOT_DIR / "finassure" / "packs" / "underwriting" / "scenarios.yaml")
    outage_sc = [s for s in scenarios if s.id == "bureau_outage"][0]
    
    cases = generate_underwriting_cases(count=4, seed=123)
    runner = ExperimentRunner(UnderwritingPack("v1"))
    artifacts = runner.run_experiment([outage_sc], cases, reps_override=1)
    
    # In v1, bureau outage defaults to 680 and approves without verified bureau
    unsupported = [a for a in artifacts if a.unsupported_approval]
    assert len(unsupported) > 0


def test_v2_safe_degradation_on_bureau_outage():
    scenarios = load_scenarios_from_yaml(settings.ROOT_DIR / "finassure" / "packs" / "underwriting" / "scenarios.yaml")
    outage_sc = [s for s in scenarios if s.id == "bureau_outage"][0]
    
    cases = generate_underwriting_cases(count=4, seed=123)
    runner = ExperimentRunner(UnderwritingPack("v2"))
    artifacts = runner.run_experiment([outage_sc], cases, reps_override=1)
    
    # In v2, bureau outage escalates safely to human review
    for a in artifacts:
        assert a.unsupported_approval is False
        assert a.workflow_outcome.escalated is True
        assert a.safe_degraded is True
