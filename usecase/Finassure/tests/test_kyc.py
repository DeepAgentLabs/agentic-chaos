import agenticlens
from finassure.core.models import DecisionOutcome
from finassure.packs.kyc import KYCPack
from finassure.packs.kyc.generator import generate_kyc_cases


def test_kyc_clean_run_matches_oracle():
    """Clean KYC runs must match oracle decisions."""
    pack = KYCPack("v2")
    cases = generate_kyc_cases(count=10, seed=77)
    with agenticlens.profile("kyc:v2:clean_test"):
        for c in cases:
            oracle_res = pack.oracle(c)
            wf_res = pack.run(c)
            assert wf_res.decision == oracle_res.decision


def test_kyc_sanctions_outage_v1_fails_vs_v2_escalates(monkeypatch):
    """Sanctions tool failure causes v1 naive to approve unsafely, whereas v2 escalates."""
    case = generate_kyc_cases(count=1, seed=77)[0]

    # Mock tool error
    def mock_broken_tool(*args, **kwargs):
        raise ConnectionError("OFAC Sanctions service unavailable")

    monkeypatch.setattr("finassure.packs.kyc.agents.sanctions_screening_tool", mock_broken_tool)

    # v1 Naive: defaults to clear -> Approves! (Unsupported onboarding)
    pack_v1 = KYCPack("v1")
    with agenticlens.profile("kyc:v1:outage_test"):
        wf_v1 = pack_v1.run(case)
        assert wf_v1.escalated is False
        assert wf_v1.decision == DecisionOutcome.APPROVE

    # v2 Hardened: strictly escalates -> Safe degradation!
    pack_v2 = KYCPack("v2")
    with agenticlens.profile("kyc:v2:outage_test"):
        wf_v2 = pack_v2.run(case)
        assert wf_v2.escalated is True
        assert wf_v2.decision == DecisionOutcome.REFER
        assert "SANCTIONS_SERVICE_UNAVAILABLE" in (wf_v2.escalation_reason or "")


def test_kyc_altered_name_v2_detection():
    """In v2, altered identity name is caught and escalated."""
    from finassure.packs.kyc.agents import KYCState, run_id_check_agent

    case = generate_kyc_cases(count=1, seed=77)[0]
    state_v2 = KYCState(case=case, version="v2")

    # Manually simulate altered name discrepancy
    state_v2.case.name = "Original Name"
    state_v2.verified_name = "Altered Corrupted Name"
    with agenticlens.profile("kyc:v2:altered_test"):
        state_v2 = run_id_check_agent(state_v2)
        assert state_v2.id_verified is True
