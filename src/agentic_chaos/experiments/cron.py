"""Five-field cron expressions for experiment schedules (no scheduler is embedded).

Supports ``*``, lists, ranges, steps (``*/15``, ``1-5/2``), month and weekday
names, ``7`` as Sunday and the macros ``@hourly``, ``@daily`` (``@midnight``),
``@weekly``, ``@monthly`` and ``@yearly`` (``@annually``). As in Vixie cron,
when both day-of-month and day-of-week are restricted a day matching either
field matches. `next_runs()` lets reviewers check a schedule before it is
installed in cron, a systemd timer or a CI scheduler.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo

_MACROS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
    )
}
_DAYS = {d: i for i, d in enumerate(["sun", "mon", "tue", "wed", "thu", "fri", "sat"])}
_FIELDS: tuple[tuple[str, int, int, dict[str, int]], ...] = (
    ("minute", 0, 59, {}),
    ("hour", 0, 23, {}),
    ("day of month", 1, 31, {}),
    ("month", 1, 12, _MONTHS),
    ("day of week", 0, 7, _DAYS),
)
_SEARCH_LIMIT = timedelta(days=366 * 5)


def _value(text: str, label: str, low: int, high: int, names: dict[str, int]) -> int:
    lowered = text.lower()
    if lowered in names:
        return names[lowered]
    if not text.isdigit():
        raise ValueError(f"invalid {label} value '{text}'")
    value = int(text)
    if not low <= value <= high:
        raise ValueError(f"{label} value {value} is outside {low}-{high}")
    return value


def _field(text: str, label: str, low: int, high: int, names: dict[str, int]) -> frozenset[int]:
    values: set[int] = set()
    for part in text.split(","):
        if not part:
            raise ValueError(f"empty item in {label} field '{text}'")
        base, sep, step_text = part.partition("/")
        step = 1
        if sep:
            if not step_text.isdigit() or int(step_text) < 1:
                raise ValueError(f"invalid {label} step '{step_text}'")
            step = int(step_text)
        if base == "*":
            start, end = low, high
        elif "-" in base:
            first, _, last = base.partition("-")
            start = _value(first, label, low, high, names)
            end = _value(last, label, low, high, names)
            if start > end:
                raise ValueError(f"{label} range '{base}' is reversed")
        else:
            start = _value(base, label, low, high, names)
            end = high if sep else start
        values.update(range(start, end + 1, step))
    return frozenset(values)


@dataclass(frozen=True)
class CronSchedule:
    """A parsed cron expression; `matches()` and `next_runs()` evaluate it."""

    expression: str
    minutes: frozenset[int]
    hours: frozenset[int]
    days: frozenset[int]
    months: frozenset[int]
    weekdays: frozenset[int]
    day_restricted: bool
    weekday_restricted: bool

    @classmethod
    def parse(cls, expression: str) -> "CronSchedule":
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError("cron expression must be a non-empty string")
        text = expression.strip()
        fields = _MACROS.get(text.lower(), text).split()
        if len(fields) != 5:
            raise ValueError(
                f"cron expression '{text}' must have 5 fields "
                "(minute hour day-of-month month day-of-week) or be a macro like @daily"
            )
        parsed = [
            _field(value, label, low, high, names)
            for value, (label, low, high, names) in zip(fields, _FIELDS, strict=True)
        ]
        weekdays = frozenset(day % 7 for day in parsed[4])
        return cls(
            expression=text,
            minutes=parsed[0],
            hours=parsed[1],
            days=parsed[2],
            months=parsed[3],
            weekdays=weekdays,
            day_restricted=not fields[2].startswith("*"),
            weekday_restricted=not fields[4].startswith("*"),
        )

    def _day_matches(self, moment: datetime) -> bool:
        day = moment.day in self.days
        weekday = (moment.isoweekday() % 7) in self.weekdays
        if self.day_restricted and self.weekday_restricted:
            return day or weekday
        return day and weekday

    def matches(self, moment: datetime) -> bool:
        """True when `moment` (to the minute) is a scheduled time."""
        return (
            moment.minute in self.minutes
            and moment.hour in self.hours
            and moment.month in self.months
            and self._day_matches(moment)
        )

    def next_runs(
        self, count: int = 5, *, after: datetime | None = None, tz: tzinfo | None = None
    ) -> list[datetime]:
        """The next `count` scheduled times strictly after `after` (default: now)."""
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("count must be a positive integer")
        zone = tz or timezone.utc
        start = after.astimezone(zone) if after is not None else datetime.now(zone)
        runs: list[datetime] = []
        for moment in self._iterate(start):
            runs.append(moment)
            if len(runs) == count:
                break
        return runs

    def _iterate(self, start: datetime) -> Iterator[datetime]:
        moment = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
        limit = moment + _SEARCH_LIMIT
        while moment < limit:
            if moment.month not in self.months:
                moment = _first_of_next_month(moment)
                continue
            if not self._day_matches(moment):
                moment = (moment + timedelta(days=1)).replace(hour=0, minute=0)
                continue
            if moment.hour not in self.hours:
                moment = (moment + timedelta(hours=1)).replace(minute=0)
                continue
            if moment.minute in self.minutes:
                yield moment
            moment += timedelta(minutes=1)
        # Impossible dates such as "0 0 31 2 *" (February 31st) yield nothing.


def _first_of_next_month(moment: datetime) -> datetime:
    year, month = (moment.year + 1, 1) if moment.month == 12 else (moment.year, moment.month + 1)
    return moment.replace(year=year, month=month, day=1, hour=0, minute=0)


def parse_cron(expression: str) -> CronSchedule:
    """Parse a cron expression, raising ValueError with the offending field."""
    return CronSchedule.parse(expression)
