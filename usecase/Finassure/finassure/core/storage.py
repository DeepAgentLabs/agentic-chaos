"""Local-first storage engine using SQLite index and JSON run artifacts."""

from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Any, List, Optional
from finassure.config import settings
from finassure.core.models import GateVerdict, RunArtifact


class StorageEngine:
    """Manages run artifact persistence on disk and fast indexed queries in SQLite."""

    def __init__(self, db_path: Path | None = None, artifacts_dir: Path | None = None) -> None:
        self.artifacts_dir = artifacts_dir or settings.ARTIFACTS_DIR
        self.runs_dir = self.artifacts_dir / "runs"
        self.db_path = db_path or settings.STORAGE_DB_PATH
        
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    pack_name TEXT NOT NULL,
                    pack_version TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    synthetic_group TEXT NOT NULL,
                    clean_run INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    oracle_decision TEXT NOT NULL,
                    escalated INTEGER NOT NULL,
                    silent_failure INTEGER NOT NULL,
                    safe_degraded INTEGER NOT NULL,
                    unsupported_approval INTEGER NOT NULL,
                    total_cost REAL NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    latency_ms REAL NOT NULL,
                    passed_evaluations INTEGER NOT NULL,
                    artifact_path TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS verdicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pack_name TEXT NOT NULL,
                    pack_version TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    overall_score REAL NOT NULL,
                    total_runs INTEGER NOT NULL,
                    silent_failure_rate REAL NOT NULL,
                    safe_degradation_rate REAL NOT NULL,
                    unsupported_approvals_count INTEGER NOT NULL,
                    escalation_rate REAL NOT NULL,
                    p95_latency_ms REAL NOT NULL,
                    cost_per_application REAL NOT NULL,
                    data_json TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_run(self, artifact: RunArtifact) -> Path:
        """Persist full run artifact to JSON and update SQLite index."""
        file_path = self.runs_dir / f"{artifact.run_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(artifact.model_dump_json(indent=2))

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO runs (
                    run_id, pack_name, pack_version, scenario_id, case_id, synthetic_group,
                    clean_run, decision, oracle_decision, escalated, silent_failure,
                    safe_degraded, unsupported_approval, total_cost, total_tokens,
                    latency_ms, passed_evaluations, artifact_path, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                artifact.run_id,
                artifact.pack_name,
                artifact.pack_version,
                artifact.scenario_id,
                artifact.case_id,
                artifact.synthetic_group,
                1 if artifact.clean_run else 0,
                artifact.workflow_outcome.decision.value,
                artifact.oracle_result.decision.value,
                1 if artifact.workflow_outcome.escalated else 0,
                1 if artifact.silent_failure else 0,
                1 if artifact.safe_degraded else 0,
                1 if artifact.unsupported_approval else 0,
                artifact.total_cost,
                artifact.total_tokens,
                artifact.latency_ms,
                1 if artifact.passed_evaluations else 0,
                str(file_path),
                artifact.timestamp,
            ))
            conn.commit()
        return file_path

    def save_verdict(self, verdict: GateVerdict) -> None:
        """Store gate verdict evaluation in database."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO verdicts (
                    pack_name, pack_version, verdict, overall_score, total_runs,
                    silent_failure_rate, safe_degradation_rate, unsupported_approvals_count,
                    escalation_rate, p95_latency_ms, cost_per_application, data_json, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                verdict.pack_name,
                verdict.pack_version,
                verdict.verdict,
                verdict.overall_score,
                verdict.total_runs,
                verdict.silent_failure_rate,
                verdict.safe_degradation_rate,
                verdict.unsupported_approvals_count,
                verdict.escalation_rate,
                verdict.p95_latency_ms,
                verdict.cost_per_application,
                verdict.model_dump_json(),
                verdict.timestamp,
            ))
            conn.commit()

    def get_runs(
        self,
        pack_name: str | None = None,
        pack_version: str | None = None,
        scenario_id: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Query index of runs with optional filters."""
        query = "SELECT * FROM runs WHERE 1=1"
        params: list[Any] = []
        if pack_name:
            query += " AND pack_name = ?"
            params.append(pack_name)
        if pack_version:
            query += " AND pack_version = ?"
            params.append(pack_version)
        if scenario_id:
            query += " AND scenario_id = ?"
            params.append(scenario_id)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cur = conn.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def get_run_artifact(self, run_id: str) -> RunArtifact | None:
        """Fetch the full JSON artifact for a given run ID."""
        file_path = self.runs_dir / f"{run_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return RunArtifact.model_validate(data)

    def get_latest_verdict(self, pack_name: str, pack_version: str) -> GateVerdict | None:
        """Retrieve most recent release gate verdict for a pack version."""
        with self._get_connection() as conn:
            cur = conn.execute("""
                SELECT data_json FROM verdicts
                WHERE pack_name = ? AND pack_version = ?
                ORDER BY timestamp DESC LIMIT 1
            """, (pack_name, pack_version))
            row = cur.fetchone()
            if row:
                return GateVerdict.model_validate_json(row["data_json"])
        return None

    def get_verdict_history(self, pack_name: str | None = None) -> list[dict[str, Any]]:
        """Get timeline of past release gate verdicts."""
        query = "SELECT id, pack_name, pack_version, verdict, overall_score, total_runs, silent_failure_rate, safe_degradation_rate, unsupported_approvals_count, escalation_rate, p95_latency_ms, cost_per_application, timestamp FROM verdicts"
        params: list[Any] = []
        if pack_name:
            query += " WHERE pack_name = ?"
            params.append(pack_name)
        query += " ORDER BY id ASC"

        with self._get_connection() as conn:
            cur = conn.execute(query, params)
            return [dict(row) for row in cur.fetchall()]


storage = StorageEngine()
