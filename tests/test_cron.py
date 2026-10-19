"""Cron expressions used by experiment schedules."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from agentic_chaos.experiments import CronSchedule, parse_cron

START = datetime(2026, 10, 18, 12, 30, tzinfo=timezone.utc)  # a Sunday


def runs(expression, count=3, after=START, tz=None):
    return [
        m.strftime("%Y-%m-%d %H:%M %a")
        for m in parse_cron(expression).next_runs(count, after=after, tz=tz)
    ]


def test_nightly_and_steps():
    assert runs("0 2 * * *") == [
        "2026-10-19 02:00 Mon",
        "2026-10-20 02:00 Tue",
        "2026-10-21 02:00 Wed",
    ]
    assert runs("*/15 * * * *", 4) == [
        "2026-10-18 12:45 Sun",
        "2026-10-18 13:00 Sun",
        "2026-10-18 13:15 Sun",
        "2026-10-18 13:30 Sun",
    ]
    assert runs("10-20/5 9 * * *", 3) == [
        "2026-10-19 09:10 Mon",
        "2026-10-19 09:15 Mon",
        "2026-10-19 09:20 Mon",
    ]


def test_names_lists_and_sunday_as_seven():
    assert runs("0 6 * * mon-fri", 2) == ["2026-10-19 06:00 Mon", "2026-10-20 06:00 Tue"]
    assert runs("0 0 1 jan,jul *", 2) == ["2027-01-01 00:00 Fri", "2027-07-01 00:00 Thu"]
    assert runs("0 0 * * 7", 1) == runs("0 0 * * sun", 1) == ["2026-10-25 00:00 Sun"]


def test_day_of_month_or_day_of_week_when_both_restricted():
    # Vixie cron: the 1st of the month OR any Friday.
    assert runs("0 0 1 * fri", 3) == [
        "2026-10-23 00:00 Fri",
        "2026-10-30 00:00 Fri",
        "2026-11-01 00:00 Sun",
    ]


def test_macros_and_matches():
    assert runs("@daily", 1) == ["2026-10-19 00:00 Mon"]
    assert runs("@hourly", 1) == ["2026-10-18 13:00 Sun"]
    assert runs("@weekly", 1) == ["2026-10-25 00:00 Sun"]
    assert runs("@monthly", 1) == ["2026-11-01 00:00 Sun"]
    assert runs("@yearly", 1) == ["2027-01-01 00:00 Fri"]
    schedule = parse_cron("30 12 * * *")
    assert schedule.matches(START)
    assert not schedule.matches(START.replace(minute=31))


def test_time_zones_and_impossible_dates():
    local = runs("0 2 * * *", 1, tz=ZoneInfo("Asia/Kolkata"))
    assert local == ["2026-10-19 02:00 Mon"]
    assert parse_cron("0 0 31 2 *").next_runs(1, after=START) == []
    assert runs("0 0 29 2 *", 1) == ["2028-02-29 00:00 Tue"]


@pytest.mark.parametrize(
    "expression,message",
    [
        ("", "non-empty"),
        ("* * * *", "5 fields"),
        ("60 * * * *", "outside 0-59"),
        ("* 24 * * *", "outside 0-23"),
        ("* * 0 * *", "outside 1-31"),
        ("* * * 13 *", "outside 1-12"),
        ("* * * * 8", "outside 0-7"),
        ("*/0 * * * *", "step"),
        ("5-1 * * * *", "reversed"),
        ("1,,2 * * * *", "empty item"),
        ("x * * * *", "invalid minute"),
        ("* * * foo *", "invalid month"),
    ],
)
def test_invalid_expressions(expression, message):
    with pytest.raises(ValueError, match=message):
        CronSchedule.parse(expression)


def test_next_runs_count_validation_and_default_now():
    schedule = parse_cron("* * * * *")
    with pytest.raises(ValueError):
        schedule.next_runs(0)
    assert len(schedule.next_runs(2)) == 2
