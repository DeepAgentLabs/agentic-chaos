import pytest
import agenticlens
from finassure.packs.aml import AMLPack
from finassure.packs.aml.generator import generate_aml_cases
from finassure.packs.aml.oracle import aml_oracle
from finassure.core.models import DecisionOutcome
from finassure.core.scenario import load_scenarios_from_yaml
from finassure.core.runner import ExperimentRunner
from finassure.config import settings


def test_aml_clean_run_matches_oracle():
    """Clean AML runs must match oracle determinations."""
    pack = AMLPack("v2")
    cases = generate_aml_cases(count=8, seed=88)
    with agenticlens.profile("aml:v2:clean_test"):
        for c in cases:
            oracle_res = pack.oracle(c)
            wf_res = pack.run(c)
            assert wf_res.decision == oracle_res.decision


def test_aml_jurisdiction_outage_v1_fails_vs_v2_escalates():
    """FATF jurisdiction tool failure must cause v1 naive to assume clear domestic, whereas v2 strictly escalates."""
    scenarios = load_scenarios_from_yaml(settings.ROOT_DIR / "finassure" / "packs" / "aml" / "scenarios.yaml")
    outage_sc = [s for s in scenarios if s.id == "jurisdiction_outage"][0]
    
    cases = generate_aml_cases(count=4, seed=88)

    # v1 Naive: defaults to LOW risk without verified lookup -> unsupported / silent failure
    runner_v1 = ExperimentRunner(AMLPack("v1"))
    artifacts_v1 = runner_v1.run_experiment([outage_sc], cases, reps_override=1)
    # Check that at least some v1 runs proceed unescalated
    unescalated_v1 = [a for a in artifacts_v1 if not a.workflow_outcome.escalated]
    assert len(unescalated_v1) > 0

    # v2 Hardened: catches lookup failure and escalates safely
    runner_v2 = ExperimentRunner(AMLPack("v2"))
    artifacts_v2 = runner_v2.run_experiment([outage_sc], cases, reps_override=1)
    for a in artifacts_v2:
        assert a.workflow_outcome.escalated is True
        assert a.safe_degraded is True
        assert "JURISDICTION" in (a.workflow_outcome.escalation_reason or "")


def test_aml_dropped_handoff_v2_escalation():
    """Dropped screening handoff triggers contract validation and safe escalation in v2."""
    scenarios = load_scenarios_from_yaml(settings.ROOT_DIR / "finassure" / "packs" / "aml" / "scenarios.yaml")
    drop_sc = [s for s in scenarios if s.id == "dropped_jurisdiction_handoff"][0]

    cases = generate_aml_cases(count=4, seed=88)
    runner_v2 = ExperimentRunner(AMLPack("v2"))
    artifacts_v2 = runner_v2.run_experiment([drop_sc], cases, reps_override=1)
    for a in artifacts_v2:
        assert a.workflow_outcome.escalated is True
        assert a.safe_degraded is True
