import json
from pathlib import Path

from agentic_chaos.drift.models import DriftAlertState, DriftReport, DriftSnapshot


def load_snapshot(path: Path) -> DriftSnapshot:
    return DriftSnapshot.model_validate_json(path.read_text(encoding="utf-8"))


def save_snapshot(path: Path, snapshot: DriftSnapshot) -> None:
    path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")


def load_report(path: Path) -> DriftReport:
    return DriftReport.model_validate_json(path.read_text(encoding="utf-8"))


def save_report(path: Path, report: DriftReport) -> None:
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")


def default_state_path(baseline_path: Path) -> Path:
    return baseline_path.with_name(f"{baseline_path.stem}.drift-state.json")


def load_alert_state(path: Path) -> DriftAlertState:
    if not path.exists():
        return DriftAlertState()
    return DriftAlertState.model_validate_json(path.read_text(encoding="utf-8"))


def save_alert_state(path: Path, state: DriftAlertState) -> None:
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")


def load_retrieval_items(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(raw)
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise ValueError("Retrieval JSON must be a list of strings.")
        return data
    return [line.strip() for line in raw.splitlines() if line.strip()]
