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
    """The altered_name scenario changes the name at the id-check boundary; v2 escalates."""
    from finassure.core.scenario import ChaosScenario
    from finassure.packs.kyc.agents import KYCState, run_id_check_agent

    from agentic_chaos import chaos_session

    scenario = ChaosScenario(
        id="altered_name",
        name="Altered name",
        pack="kyc",
        fault_type="silent_degradation",
        target="id_check_agent.name",
        params={"corruption": "alter_text"},
        hypothesis="test",
    )
    case = generate_kyc_cases(count=1, seed=77)[0]
    for version, escalated in (("v1", False), ("v2", True)):
        state = KYCState(case=case, version=version)
        with (
            chaos_session(scenario.instantiate_faults()),
            agenticlens.profile(f"kyc:{version}:altered_test"),
        ):
            state = run_id_check_agent(state)
        assert state.verified_name != case.name
        assert state.escalated is escalated
        if escalated:
            assert state.escalation_reason == "IDENTITY_NAME_MISMATCH"
