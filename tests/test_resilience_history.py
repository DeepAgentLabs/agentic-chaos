"""v0.9 run-history store: trends and max_runs / max_age_days retention."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from agentic_chaos.resilience import ResilienceHistory, ResilienceScore

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


def scored(value: int | None, name: str = "agent") -> ResilienceScore:
    return ResilienceScore(
        score=value,
        status="scored" if value is not None else "inconclusive",
        report_id=f"r-{value}",
        report_name=name,
        components=[],
        faults=[],
    )


def test_first_run_has_no_trend_and_later_runs_compare(tmp_path) -> None:
    history = ResilienceHistory(tmp_path / "nested" / "history.json")
    first = scored(64)
    assert history.record(first, recorded_at=T0) is None and first.trend is None
    second = scored(72)
    trend = history.record(second, recorded_at=T0 + timedelta(days=1))
    assert trend is not None
    assert trend["previous"] == 64 and trend["delta"] == 8 and trend["direction"] == "up"
    assert second.trend == trend and trend["runs"] == 1
    assert history.record(scored(72), recorded_at=T0 + timedelta(days=2))["direction"] == "flat"
    assert history.record(scored(50), recorded_at=T0 + timedelta(days=3))["direction"] == "down"


def test_trend_skips_inconclusive_entries_and_other_names(tmp_path) -> None:
    history = ResilienceHistory(tmp_path / "h.json")
    history.record(scored(70), recorded_at=T0)
    history.record(scored(None), recorded_at=T0 + timedelta(hours=1))
    history.record(scored(10, name="other"), recorded_at=T0 + timedelta(hours=2))
    trend = history.trend("agent", 75)
    assert trend is not None and trend["previous"] == 70 and trend["delta"] == 5
    assert history.trend("agent", None)["delta"] is None
    assert history.trend("never-run", 50) is None
    assert history.names() == ["agent", "other"]


def test_entries_are_compact(tmp_path) -> None:
    history = ResilienceHistory(tmp_path / "h.json")
    history.record(scored(80), name="nightly", recorded_at=T0)
    (entry,) = history.entries("nightly")
    assert entry == {
        "name": "nightly",
        "report_id": "r-80",
        "recorded_at": T0.isoformat(),
        "score": 80,
        "status": "scored",
        "grade": "B",
        "components": {},
        "faults": {},
    }
    stored = json.loads((tmp_path / "h.json").read_text())
    assert stored["version"] == 1


def test_max_runs_keeps_the_newest_runs_per_name(tmp_path) -> None:
    history = ResilienceHistory(tmp_path / "h.json", max_runs=2)
    for day, value in enumerate((10, 20, 30)):
        history.record(scored(value), recorded_at=T0 + timedelta(days=day))
        history.record(scored(value, name="other"), recorded_at=T0 + timedelta(days=day))
    assert [e["score"] for e in history.entries("agent")] == [20, 30]
    assert [e["score"] for e in history.entries("other")] == [20, 30]


def test_max_age_days_drops_old_runs(tmp_path) -> None:
    path = tmp_path / "h.json"
    ResilienceHistory(path).record(scored(10), recorded_at=T0)
    ResilienceHistory(path).record(scored(20), recorded_at=T0 + timedelta(days=20))
    aged = ResilienceHistory(path, max_age_days=7)
    aged.record(scored(30), recorded_at=T0 + timedelta(days=25))
    assert [e["score"] for e in aged.entries()] == [20, 30]


def test_prune_applies_retention_on_demand(tmp_path) -> None:
    path = tmp_path / "h.json"
    for day in range(5):
        ResilienceHistory(path).record(scored(day), recorded_at=T0 + timedelta(days=day))
    assert ResilienceHistory(path, max_runs=3).prune() == 2
    assert ResilienceHistory(path, max_age_days=1).prune(now=T0 + timedelta(days=4)) == 1
    assert ResilienceHistory(path).prune() == 0
    assert [e["score"] for e in ResilienceHistory(path).entries()] == [3, 4]


def test_invalid_options_and_files(tmp_path) -> None:
    with pytest.raises(ValueError, match="max_runs"):
        ResilienceHistory(tmp_path / "h.json", max_runs=0)
    with pytest.raises(ValueError, match="max_age_days"):
        ResilienceHistory(tmp_path / "h.json", max_age_days=float("inf"))
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    with pytest.raises(ValueError, match="not valid JSON"):
        ResilienceHistory(broken).entries()
    shapeless = tmp_path / "shapeless.json"
    shapeless.write_text("[]")
    with pytest.raises(ValueError, match="'entries'"):
        ResilienceHistory(shapeless).entries()
    assert ResilienceHistory(tmp_path / "missing.json").entries() == []


def test_writes_leave_no_temporary_files(tmp_path) -> None:
    history = ResilienceHistory(tmp_path / "h.json")
    history.record(scored(1))
    assert [p.name for p in tmp_path.iterdir()] == ["h.json"]


def test_naive_timestamps_are_treated_as_utc(tmp_path) -> None:
    history = ResilienceHistory(tmp_path / "h.json", max_age_days=1)
    history.record(scored(1), recorded_at=datetime(2026, 10, 1, 12))
    assert history.entries()[0]["recorded_at"].endswith("+00:00")
