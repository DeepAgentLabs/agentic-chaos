import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from finassure.config import settings
from finassure.core.evidence import evidence_generator
from finassure.core.gate import evaluate_release_gate
from finassure.core.runner import ExperimentRunner
from finassure.core.scenario import load_scenarios_from_yaml
from finassure.core.storage import storage
from finassure.packs.aml import AMLPack
from finassure.packs.kyc import KYCPack
from finassure.packs.underwriting import UnderwritingPack


def seed(count: int = 12, reps: int = 1, pack_filter: str = "all"):
    print(f"=== FinAssure Reliability Harness Baseline Runner (count={count}, reps={reps}) ===")

    if pack_filter in ("all", "underwriting"):
        print("\n[1/3] Generating baseline runs for Underwriting Pack...")
        uw_scenarios_file = (
            settings.ROOT_DIR / "finassure" / "packs" / "underwriting" / "scenarios.yaml"
        )
        uw_scenarios = load_scenarios_from_yaml(uw_scenarios_file)

        # 1. Underwriting v1
        pack_v1 = UnderwritingPack("v1")
        cases = pack_v1.generate_cases(count=count, seed=42)
        runner_v1 = ExperimentRunner(pack_v1)
        artifacts_v1 = runner_v1.run_experiment(uw_scenarios, cases, reps_override=reps)
        verdict_v1 = evaluate_release_gate(artifacts_v1)
        storage.save_verdict(verdict_v1)
        evidence_generator.generate(verdict_v1, artifacts_v1)
        print(
            f"  -> Underwriting v1 Gate: {verdict_v1.verdict} "
            f"(Silent Fail Rate: {verdict_v1.silent_failure_rate * 100:.1f}%, "
            f"Unsupp Approvals: {verdict_v1.unsupported_approvals_count})"
        )

        # 2. Underwriting v2
        pack_v2 = UnderwritingPack("v2")
        runner_v2 = ExperimentRunner(pack_v2)
        artifacts_v2 = runner_v2.run_experiment(uw_scenarios, cases, reps_override=reps)
        verdict_v2 = evaluate_release_gate(artifacts_v2)
        storage.save_verdict(verdict_v2)
        evidence_generator.generate(verdict_v2, artifacts_v2)
        print(
            f"  -> Underwriting v2 Gate: {verdict_v2.verdict} "
            f"(Safe Degradation: {verdict_v2.safe_degradation_rate * 100:.1f}%, "
            f"Score: {verdict_v2.overall_score * 100:.1f}%)"
        )

    if pack_filter in ("all", "kyc"):
        # 2. KYC Onboarding Pack baseline
        print("\n[2/3] Generating baseline runs for KYC Onboarding Pack...")
        kyc_scenarios_file = settings.ROOT_DIR / "finassure" / "packs" / "kyc" / "scenarios.yaml"
        kyc_scenarios = load_scenarios_from_yaml(kyc_scenarios_file)

        pack_kyc_v1 = KYCPack("v1")
        kyc_cases = pack_kyc_v1.generate_cases(count=count, seed=77)
        runner_kyc_v1 = ExperimentRunner(pack_kyc_v1)
        artifacts_kyc_v1 = runner_kyc_v1.run_experiment(
            kyc_scenarios, kyc_cases, reps_override=reps
        )
        verdict_kyc_v1 = evaluate_release_gate(artifacts_kyc_v1)
        storage.save_verdict(verdict_kyc_v1)
        evidence_generator.generate(verdict_kyc_v1, artifacts_kyc_v1)
        print(
            f"  -> KYC v1 Gate: {verdict_kyc_v1.verdict} "
            f"(Silent Fail: {verdict_kyc_v1.silent_failure_rate * 100:.1f}%)"
        )

        pack_kyc_v2 = KYCPack("v2")
        runner_kyc_v2 = ExperimentRunner(pack_kyc_v2)
        artifacts_kyc_v2 = runner_kyc_v2.run_experiment(
            kyc_scenarios, kyc_cases, reps_override=reps
        )
        verdict_kyc_v2 = evaluate_release_gate(artifacts_kyc_v2)
        storage.save_verdict(verdict_kyc_v2)
        evidence_generator.generate(verdict_kyc_v2, artifacts_kyc_v2)
        print(
            f"  -> KYC v2 Gate: {verdict_kyc_v2.verdict} "
            f"(Safe Degradation: {verdict_kyc_v2.safe_degradation_rate * 100:.1f}%)"
        )

    if pack_filter in ("all", "aml"):
        # 3. AML Triage Pack baseline
        print("\n[3/3] Generating baseline runs for AML Triage Pack...")
        aml_scenarios_file = settings.ROOT_DIR / "finassure" / "packs" / "aml" / "scenarios.yaml"
        aml_scenarios = load_scenarios_from_yaml(aml_scenarios_file)

        pack_aml_v1 = AMLPack("v1")
        aml_cases = pack_aml_v1.generate_cases(count=count, seed=88)
        runner_aml_v1 = ExperimentRunner(pack_aml_v1)
        artifacts_aml_v1 = runner_aml_v1.run_experiment(
            aml_scenarios, aml_cases, reps_override=reps
        )
        verdict_aml_v1 = evaluate_release_gate(artifacts_aml_v1)
        storage.save_verdict(verdict_aml_v1)
        evidence_generator.generate(verdict_aml_v1, artifacts_aml_v1)
        print(
            f"  -> AML v1 Gate: {verdict_aml_v1.verdict} "
            f"(Silent Fail: {verdict_aml_v1.silent_failure_rate * 100:.1f}%)"
        )

        pack_aml_v2 = AMLPack("v2")
        runner_aml_v2 = ExperimentRunner(pack_aml_v2)
        artifacts_aml_v2 = runner_aml_v2.run_experiment(
            aml_scenarios, aml_cases, reps_override=reps
        )
        verdict_aml_v2 = evaluate_release_gate(artifacts_aml_v2)
        storage.save_verdict(verdict_aml_v2)
        evidence_generator.generate(verdict_aml_v2, artifacts_aml_v2)
        print(
            f"  -> AML v2 Gate: {verdict_aml_v2.verdict} "
            f"(Safe Degradation: {verdict_aml_v2.safe_degradation_rate * 100:.1f}%)"
        )

    print("\n[OK] Baseline seeding complete! Evidence packs written to artifacts/evidence_packs/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinAssure Baseline Seed Runner")
    parser.add_argument(
        "--count", type=int, default=10, help="Number of applicant cases (up to 200)"
    )
    parser.add_argument("--reps", type=int, default=1, help="Reps per scenario x case")
    parser.add_argument(
        "--pack",
        type=str,
        default="all",
        choices=["all", "underwriting", "kyc", "aml"],
        help="Target pack",
    )
    args = parser.parse_args()
    seed(count=args.count, reps=args.reps, pack_filter=args.pack)
