"""FastAPI server for FinAssure dashboard and runner."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from finassure.config import settings
from finassure.core.evidence import evidence_generator
from finassure.core.gate import evaluate_release_gate
from finassure.core.pack import BaseWorkflowPack
from finassure.core.runner import ExperimentRunner
from finassure.core.scenario import load_scenarios_from_yaml
from finassure.core.storage import storage
from finassure.packs.aml import AMLPack
from finassure.packs.kyc import KYCPack
from finassure.packs.underwriting import UnderwritingPack

app = FastAPI(title="FinAssure API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_pack_instance(pack_name: str, version: str = "v1") -> BaseWorkflowPack:
    if pack_name.lower() == "underwriting":
        return UnderwritingPack(version=version)
    elif pack_name.lower() == "kyc":
        return KYCPack(version=version)
    elif pack_name.lower() == "aml":
        return AMLPack(version=version)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown pack: {pack_name}")


class RunExperimentRequest(BaseModel):
    pack: str = "underwriting"
    version: str = "v2"
    scenario_ids: list[str] = Field(default_factory=list)
    case_count: int = 10
    reps_per_case: int = 1


@app.get("/api/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "has_gemini_key": settings.has_gemini_key(),
        "gemini_model": settings.FLASH_MODEL,
        "artifacts_dir": str(settings.ARTIFACTS_DIR),
    }


@app.get("/api/packs")
def list_packs() -> dict[str, Any]:
    return {
        "packs": [
            {
                "id": "underwriting",
                "name": "Loan Underwriting",
                "versions": ["v1", "v2"],
                "description": (
                    "5-agent financial underwriting pipeline with DTI, "
                    "bureau lookup, and compliance review."
                ),
            },
            {
                "id": "kyc",
                "name": "KYC Onboarding",
                "versions": ["v1", "v2"],
                "description": "Identity verification, sanctions, and PEP screening.",
            },
            {
                "id": "aml",
                "name": "AML Suspicious Activity",
                "versions": ["v1", "v2"],
                "description": (
                    "Anti-money laundering transaction structuring and FATF corridor screening."
                ),
            },
        ]
    }


@app.get("/api/scenarios")
def list_scenarios(pack: str = "underwriting") -> list[dict[str, Any]]:
    scenario_file = settings.ROOT_DIR / "finassure" / "packs" / pack / "scenarios.yaml"
    if not scenario_file.exists():
        raise HTTPException(status_code=404, detail="Scenarios not found for pack")
    scenarios = load_scenarios_from_yaml(scenario_file)
    return [s.model_dump() for s in scenarios]


@app.post("/api/experiments/run")
def trigger_experiment(req: RunExperimentRequest) -> dict[str, Any]:
    pack = get_pack_instance(req.pack, req.version)
    scenario_file = settings.ROOT_DIR / "finassure" / "packs" / req.pack / "scenarios.yaml"
    all_scenarios = load_scenarios_from_yaml(scenario_file)

    if req.scenario_ids:
        selected_scenarios = [s for s in all_scenarios if s.id in req.scenario_ids]
    else:
        selected_scenarios = all_scenarios

    cases = pack.generate_cases(count=req.case_count, seed=42)
    runner = ExperimentRunner(pack)

    # Run experiment
    artifacts = runner.run_experiment(
        scenarios=selected_scenarios,
        cases=cases,
        reps_override=req.reps_per_case,
    )

    # Evaluate gate
    verdict = evaluate_release_gate(artifacts)
    storage.save_verdict(verdict)

    # Generate evidence pack automatically
    evidence_files = evidence_generator.generate(verdict, artifacts)

    return {
        "verdict": verdict.model_dump(),
        "total_runs": len(artifacts),
        "evidence_files": {k: str(v) for k, v in evidence_files.items()},
    }


@app.get("/api/verdicts")
@app.get("/releases")
@app.get("/api/releases")
def get_verdicts(pack: str = "underwriting", version: str = "v2") -> dict[str, Any]:
    latest = storage.get_latest_verdict(pack, version)
    history = storage.get_verdict_history(pack)
    return {
        "latest": latest.model_dump() if latest else None,
        "history": history,
    }


@app.get("/experiments")
@app.get("/api/experiments")
def list_experiments(pack: str = "underwriting") -> list[dict[str, Any]]:
    return list_scenarios(pack=pack)


@app.get("/runs/{run_id}")
@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    artifact = storage.get_run_artifact(run_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Run artifact not found")
    return artifact.model_dump()


@app.get("/runs/{run_id}/trace")
@app.get("/api/runs/{run_id}/trace")
def get_run_trace(run_id: str) -> dict[str, Any]:
    artifact = storage.get_run_artifact(run_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Run artifact not found")
    return {
        "run_id": run_id,
        "trace_steps": artifact.trace_steps,
        "chaos_events": artifact.chaos_events,
        "total_cost": artifact.total_cost,
        "total_tokens": artifact.total_tokens,
        "latency_ms": artifact.latency_ms,
    }


@app.get("/cases/{case_id}")
@app.get("/api/cases/{case_id}")
def get_case(case_id: str, pack: str = "underwriting") -> dict[str, Any]:
    p = get_pack_instance(pack, "v2")
    cases = p.generate_cases(count=200, seed=42)
    matched = next((c for c in cases if c.id == case_id), None)
    if not matched:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    oracle_res = p.oracle(matched)
    return {
        "case": matched.model_dump(),
        "oracle": oracle_res.model_dump(),
    }


@app.get("/compare")
@app.get("/api/compare")
def compare_versions(
    pack: str = "underwriting",
    version_a: str = "v1",
    version_b: str = "v2",
    a: str | None = None,
    b: str | None = None,
) -> dict[str, Any]:
    va = a or version_a
    vb = b or version_b
    verdict_a = storage.get_latest_verdict(pack, va)
    verdict_b = storage.get_latest_verdict(pack, vb)

    return {
        "pack": pack,
        "version_a": {
            "version": va,
            "verdict": verdict_a.verdict if verdict_a else "N/A",
            "score": verdict_a.overall_score if verdict_a else None,
            "silent_failure_rate": verdict_a.silent_failure_rate if verdict_a else None,
            "safe_degradation_rate": verdict_a.safe_degradation_rate if verdict_a else None,
            "unsupported_approvals": verdict_a.unsupported_approvals_count if verdict_a else None,
            "escalation_rate": verdict_a.escalation_rate if verdict_a else None,
            "latency_ms": verdict_a.p95_latency_ms if verdict_a else None,
            "cost_per_app": verdict_a.cost_per_application if verdict_a else None,
        },
        "version_b": {
            "version": vb,
            "verdict": verdict_b.verdict if verdict_b else "N/A",
            "score": verdict_b.overall_score if verdict_b else None,
            "silent_failure_rate": verdict_b.silent_failure_rate if verdict_b else None,
            "safe_degradation_rate": verdict_b.safe_degradation_rate if verdict_b else None,
            "unsupported_approvals": verdict_b.unsupported_approvals_count if verdict_b else None,
            "escalation_rate": verdict_b.escalation_rate if verdict_b else None,
            "latency_ms": verdict_b.p95_latency_ms if verdict_b else None,
            "cost_per_app": verdict_b.cost_per_application if verdict_b else None,
        },
        "deltas": {
            "silent_failure_reduction": (
                (verdict_a.silent_failure_rate - verdict_b.silent_failure_rate)
                if verdict_a and verdict_b
                else None
            ),
            "safe_degradation_gain": (
                (verdict_b.safe_degradation_rate - verdict_a.safe_degradation_rate)
                if verdict_a and verdict_b
                else None
            ),
            "cost_overhead": (
                (verdict_b.cost_per_application - verdict_a.cost_per_application)
                if verdict_a and verdict_b
                else None
            ),
            "latency_overhead_ms": (
                (verdict_b.p95_latency_ms - verdict_a.p95_latency_ms)
                if verdict_a and verdict_b
                else None
            ),
        },
    }


@app.get("/fairness")
@app.get("/api/fairness")
def get_fairness_breakdown(pack: str = "underwriting", version: str = "v2") -> dict[str, Any]:
    runs = storage.get_runs(pack_name=pack, pack_version=version, limit=500)
    groups: dict[str, dict[str, int]] = {}
    for r in runs:
        grp = r.get("synthetic_group", "unknown")
        if grp not in groups:
            groups[grp] = {"total": 0, "silent_failures": 0, "safe_degraded": 0, "escalated": 0}
        groups[grp]["total"] += 1
        if r.get("silent_failure"):
            groups[grp]["silent_failures"] += 1
        if r.get("safe_degraded"):
            groups[grp]["safe_degraded"] += 1
        if r.get("escalated"):
            groups[grp]["escalated"] += 1

    summary = []
    for grp, counts in groups.items():
        tot = max(counts["total"], 1)
        summary.append(
            {
                "group": grp,
                "total_runs": counts["total"],
                "silent_failure_rate": round(counts["silent_failures"] / tot, 4),
                "safe_degradation_rate": round(counts["safe_degraded"] / tot, 4),
                "escalation_rate": round(counts["escalated"] / tot, 4),
            }
        )

    return {"pack": pack, "version": version, "groups": summary}


@app.get("/topology")
@app.get("/api/topology")
def get_topology(pack: str = "underwriting") -> dict[str, Any]:
    if pack.lower() == "underwriting":
        nodes = [
            {
                "id": "intake_agent",
                "label": "Intake Agent",
                "role": "Application intake validator",
                "type": "agent",
            },
            {
                "id": "doc_extraction_agent",
                "label": "Document Extraction",
                "role": "Financial information extractor",
                "type": "agent",
            },
            {
                "id": "bureau_lookup",
                "label": "Credit Bureau API",
                "role": "External Bureau tool",
                "type": "tool",
            },
            {
                "id": "bureau_agent",
                "label": "Bureau Agent",
                "role": "Bureau coordinator",
                "type": "agent",
            },
            {
                "id": "risk_scorer_agent",
                "label": "Risk Scorer Agent",
                "role": "Deterministic policy scoring",
                "type": "agent",
            },
            {
                "id": "compliance_reviewer_agent",
                "label": "Compliance Reviewer",
                "role": "Regulatory adverse notice reviewer",
                "type": "agent",
            },
            {
                "id": "hitl_review_queue",
                "label": "Human Reviewer Queue",
                "role": "HITL escalation queue",
                "type": "human",
            },
        ]
        edges = [
            {"from": "intake_agent", "to": "doc_extraction_agent", "label": "Raw Application"},
            {
                "from": "doc_extraction_agent",
                "to": "bureau_agent",
                "label": "Extracted Financials",
                "fault_point": "handoff_corruption",
            },
            {
                "from": "bureau_agent",
                "to": "bureau_lookup",
                "label": "SSN & Credit Lookup",
                "fault_point": "tool_failure",
            },
            {"from": "bureau_agent", "to": "risk_scorer_agent", "label": "Credit File Data"},
            {
                "from": "risk_scorer_agent",
                "to": "compliance_reviewer_agent",
                "label": "Preliminary Determination",
            },
            {
                "from": "compliance_reviewer_agent",
                "to": "hitl_review_queue",
                "label": "Escalate (Refer)",
            },
        ]
    elif pack.lower() == "aml":
        nodes = [
            {
                "id": "transaction_ingestion_agent",
                "label": "Transaction Ingestion Agent",
                "role": "SWIFT MT103 parsing",
                "type": "agent",
            },
            {
                "id": "jurisdiction_lookup",
                "label": "FATF Watchlist API",
                "role": "Offshore jurisdiction check",
                "type": "tool",
            },
            {
                "id": "jurisdiction_agent",
                "label": "Jurisdiction Agent",
                "role": "Corridor risk classification",
                "type": "agent",
            },
            {
                "id": "aml_triage_agent",
                "label": "AML Triage Agent",
                "role": "Structuring & threshold triage",
                "type": "agent",
            },
            {
                "id": "aml_reviewer_agent",
                "label": "AML Reviewer Agent",
                "role": "SAR filing justification memo",
                "type": "agent",
            },
            {
                "id": "hitl_aml_queue",
                "label": "AML Compliance Officer Queue",
                "role": "SAR/EDD human sign-off",
                "type": "human",
            },
        ]
        edges = [
            {
                "from": "transaction_ingestion_agent",
                "to": "jurisdiction_agent",
                "label": "Parsed Transaction",
                "fault_point": "silent_degradation",
            },
            {
                "from": "jurisdiction_agent",
                "to": "jurisdiction_lookup",
                "label": "FATF/Offshore Query",
                "fault_point": "tool_failure",
            },
            {
                "from": "jurisdiction_agent",
                "to": "aml_triage_agent",
                "label": "Jurisdiction Risk Flag",
                "fault_point": "handoff_corruption",
            },
            {
                "from": "aml_triage_agent",
                "to": "aml_reviewer_agent",
                "label": "Triage Factors & Decision",
            },
            {"from": "aml_reviewer_agent", "to": "hitl_aml_queue", "label": "Escalate (SAR/EDD)"},
        ]
    else:
        nodes = [
            {
                "id": "id_check_agent",
                "label": "Identity Check Agent",
                "role": "Government ID verification",
                "type": "agent",
            },
            {
                "id": "sanctions_screening",
                "label": "Watchlist Screening API",
                "role": "OFAC/PEP Watchlist tool",
                "type": "tool",
            },
            {
                "id": "sanctions_agent",
                "label": "Sanctions Agent",
                "role": "Watchlist screening coordinator",
                "type": "agent",
            },
            {
                "id": "kyc_risk_agent",
                "label": "KYC Risk Rating Agent",
                "role": "Risk level classification",
                "type": "agent",
            },
            {
                "id": "kyc_reviewer_agent",
                "label": "KYC Compliance Reviewer",
                "role": "KYC sign-off documentation",
                "type": "agent",
            },
            {
                "id": "hitl_kyc_queue",
                "label": "Compliance Officer Queue",
                "role": "Enhanced due diligence",
                "type": "human",
            },
        ]
        edges = [
            {
                "from": "id_check_agent",
                "to": "sanctions_agent",
                "label": "Verified Identity",
                "fault_point": "silent_degradation",
            },
            {
                "from": "sanctions_agent",
                "to": "sanctions_screening",
                "label": "Watchlist Lookup",
                "fault_point": "tool_failure",
            },
            {
                "from": "sanctions_agent",
                "to": "kyc_risk_agent",
                "label": "Screening Results",
                "fault_point": "handoff_corruption",
            },
            {
                "from": "kyc_risk_agent",
                "to": "kyc_reviewer_agent",
                "label": "Risk Score & PEP Flag",
            },
            {"from": "kyc_reviewer_agent", "to": "hitl_kyc_queue", "label": "Escalate (EDD)"},
        ]

    return {"pack": pack, "nodes": nodes, "edges": edges}


class EvidencePackRequest(BaseModel):
    pack: str = "underwriting"
    version: str = "v2"


@app.post("/evidence-pack")
@app.post("/api/evidence-pack")
def generate_evidence_pack(req: EvidencePackRequest) -> dict[str, Any]:
    verdict = storage.get_latest_verdict(req.pack, req.version)
    if not verdict:
        raise HTTPException(status_code=404, detail="No verdict found to generate evidence pack")
    raw_runs = storage.get_runs(pack_name=req.pack, pack_version=req.version, limit=100)
    # Reconstruct minimal RunArtifact list
    artifacts = [
        storage.get_run_artifact(r["run_id"])
        for r in raw_runs
        if storage.get_run_artifact(r["run_id"])
    ]
    files = evidence_generator.generate(verdict, artifacts)
    return {
        "status": "generated",
        "pack": req.pack,
        "version": req.version,
        "files": {k: str(v) for k, v in files.items()},
    }


@app.get("/evidence-pack/latest")
@app.get("/api/evidence-pack/latest")
def get_latest_evidence_pack(
    pack: str = "underwriting", version: str = "v2", format: str = "html"
) -> FileResponse:
    ext = "md" if format in ("md", "markdown") else format.lower()
    files = list(evidence_generator.evidence_dir.glob(f"evidence_{pack}_{version}_*.{ext}"))
    if not files:
        raise HTTPException(status_code=404, detail="No evidence packs generated yet.")
    latest_file = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)[0]
    media_map = {
        "html": "text/html",
        "md": "text/markdown",
        "json": "application/json",
        "csv": "text/csv",
    }
    media_type = media_map.get(ext, "application/octet-stream")
    return FileResponse(latest_file, media_type=media_type, filename=latest_file.name)


# Serve Static UI
ui_dist_path = settings.ROOT_DIR / "finassure" / "static"
if ui_dist_path.exists():
    app.mount("/static", StaticFiles(directory=str(ui_dist_path)), name="static")

# Serve Use Cases Page & Assets
usecases_dir = settings.ROOT_DIR / "usecases"
if usecases_dir.exists():
    app.mount(
        "/usecases/assets",
        StaticFiles(directory=str(usecases_dir / "assets")),
        name="usecases_assets",
    )


@app.get("/usecase", response_class=HTMLResponse)
@app.get("/usecases", response_class=HTMLResponse)
def serve_usecase_page():
    usecase_html = settings.ROOT_DIR / "usecases" / "index.html"
    if usecase_html.exists():
        with open(usecase_html, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>FinAssure Use Case Page not found</h1>", status_code=404)


@app.get("/usecases/styles.css")
def serve_usecases_styles():
    css_file = settings.ROOT_DIR / "usecases" / "styles.css"
    if css_file.exists():
        return FileResponse(css_file, media_type="text/css")
    return HTMLResponse("", status_code=404)


@app.get("/usecases/app.js")
def serve_usecases_js():
    js_file = settings.ROOT_DIR / "usecases" / "app.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript")
    return HTMLResponse("", status_code=404)


@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    index_html = settings.ROOT_DIR / "finassure" / "static" / "index.html"
    if index_html.exists():
        with open(index_html, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>FinAssure Dashboard loading...</h1>")
