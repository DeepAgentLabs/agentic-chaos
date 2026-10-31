"""Local run-history store for resilience trends, with retention.

One JSON file holds a compact entry per scored run (score, grade, component
and per-fault values -- never the full report). Trends compare a new score to
the most recent *scored* entry with the same name. Retention keeps the file
bounded on CI machines that run chaos nightly:

- ``max_runs`` keeps the newest N entries per name
- ``max_age_days`` drops entries older than that, for every name

Retention is applied on every `record()` and by `prune()`. Writes go to a
temporary file that replaces the store, so an interrupted run never leaves a
half-written history. The store is not locked: give concurrent jobs separate
files.
"""

import json
import math
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentic_chaos.resilience.score import ResilienceScore

HISTORY_VERSION = 1
DEFAULT_HISTORY_PATH = Path(".agentic-chaos") / "resilience-history.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


class ResilienceHistory:
    """Scores of past runs, used for trend comparisons; see the module docstring."""

    def __init__(
        self,
        path: str | Path = DEFAULT_HISTORY_PATH,
        *,
        max_runs: int | None = None,
        max_age_days: float | None = None,
    ) -> None:
        if max_runs is not None and (
            isinstance(max_runs, bool) or not isinstance(max_runs, int) or max_runs < 1
        ):
            raise ValueError("max_runs must be a positive integer")
        if max_age_days is not None and (
            isinstance(max_age_days, bool)
            or not isinstance(max_age_days, (int, float))
            or not math.isfinite(max_age_days)
            or max_age_days <= 0
        ):
            raise ValueError("max_age_days must be a finite number > 0")
        self.path = Path(path)
        self.max_runs = max_runs
        self.max_age_days = max_age_days

    # -- reading ------------------------------------------------------------

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"resilience history {self.path} is not valid JSON: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
            raise ValueError(f"resilience history {self.path} has no 'entries' list")
        return [entry for entry in data["entries"] if isinstance(entry, dict)]

    def entries(self, name: str | None = None) -> list[dict[str, Any]]:
        """Stored entries, oldest first, optionally only those for `name`."""
        entries = self._load()
        return entries if name is None else [e for e in entries if e.get("name") == name]

    def names(self) -> list[str]:
        return sorted({str(e.get("name")) for e in self._load()})

    def latest(self, name: str) -> dict[str, Any] | None:
        """The most recent entry for `name` that has a score."""
        scored = [e for e in self.entries(name) if isinstance(e.get("score"), int)]
        return scored[-1] if scored else None

    def trend(self, name: str, score: int | None) -> dict[str, Any] | None:
        """How `score` compares to the latest scored entry for `name` (None without one)."""
        previous = self.latest(name)
        if previous is None:
            return None
        previous_score = int(previous["score"])
        delta = None if score is None else score - previous_score
        direction = (
            None if delta is None else "up" if delta > 0 else "down" if delta < 0 else "flat"
        )
        return {
            "previous": previous_score,
            "delta": delta,
            "direction": direction,
            "previous_report_id": previous.get("report_id"),
            "previous_recorded_at": previous.get("recorded_at"),
            "runs": len(self.entries(name)),
        }

    # -- writing ------------------------------------------------------------

    def record(
        self,
        score: ResilienceScore,
        *,
        name: str | None = None,
        recorded_at: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Store `score`, attach its trend to it, apply retention; return the trend."""
        key = name or score.report_name
        score.trend = self.trend(key, score.score)
        when = recorded_at or _now()
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        entry = {
            "name": key,
            "report_id": score.report_id,
            "recorded_at": when.isoformat(),
            "score": score.score,
            "status": score.status,
            "grade": score.grade,
            "components": {c.name: c.score for c in score.components},
            "faults": {f.fault_type: f.score for f in score.faults},
        }
        self._save(self._retain([*self._load(), entry], now=when))
        return score.trend

    def prune(self, *, now: datetime | None = None) -> int:
        """Apply retention now; return how many entries were removed."""
        entries = self._load()
        kept = self._retain(entries, now=now or _now())
        if len(kept) != len(entries):
            self._save(kept)
        return len(entries) - len(kept)

    def _retain(self, entries: list[dict[str, Any]], *, now: datetime) -> list[dict[str, Any]]:
        if self.max_age_days is not None:
            cutoff = now - timedelta(days=self.max_age_days)
            entries = [
                e
                for e in entries
                if (when := _parse(e.get("recorded_at"))) is None or when >= cutoff
            ]
        if self.max_runs is not None:
            seen: dict[str, int] = {}
            kept: list[dict[str, Any]] = []
            for entry in reversed(entries):
                key = str(entry.get("name"))
                seen[key] = seen.get(key, 0) + 1
                if seen[key] <= self.max_runs:
                    kept.append(entry)
            entries = list(reversed(kept))
        return entries

    def _save(self, entries: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"version": HISTORY_VERSION, "entries": entries}, indent=2)
        handle, temporary = tempfile.mkstemp(
            dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(payload)
            os.replace(temporary, self.path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
