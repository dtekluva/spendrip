from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FREQUENCIES = ("daily", "weekly", "monthly")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


@dataclass(frozen=True)
class Schedule:
    frequency: str  # daily | weekly | monthly
    time_local: str  # "HH:MM", 24h, in `tz`
    tz: str  # IANA zone, e.g. Africa/Lagos
    starts_at: datetime
    weekday: int | None = None  # ISO weekday for weekly plans: 1 = Monday … 7 = Sunday
    month_day: int | str | None = None  # 1–31 or "last"; 29–31 fall back to the month's last day
    ends_at: datetime | None = None


def validate_schedule(s: Schedule) -> list[str]:
    errors = []
    if s.frequency not in FREQUENCIES:
        errors.append("frequency must be daily, weekly or monthly")
    if not _TIME_RE.match(s.time_local or ""):
        errors.append("time must be HH:MM (24h)")
    try:
        ZoneInfo(s.tz)
    except (ZoneInfoNotFoundError, ValueError):
        errors.append(f"unknown time zone {s.tz}")
    if s.frequency == "weekly" and not (isinstance(s.weekday, int) and 1 <= s.weekday <= 7):
        errors.append("weekly plans need a weekday 1–7 (Mon–Sun)")
    if s.frequency == "monthly" and not (s.month_day == "last" or (isinstance(s.month_day, int) and 1 <= s.month_day <= 31)):
        errors.append("monthly plans need a day 1–31 or 'last'")
    if s.ends_at and s.ends_at < s.starts_at:
        errors.append("end date is before start date")
    return errors


def _matches(s: Schedule, d: date) -> bool:
    if s.frequency == "daily":
        return True
    if s.frequency == "weekly":
        return d.isoweekday() == s.weekday
    dim = calendar.monthrange(d.year, d.month)[1]
    target = dim if s.month_day == "last" or int(s.month_day) > dim else int(s.month_day)
    return d.day == target


def occurrences(s: Schedule, start: datetime, end: datetime) -> list[datetime]:
    """Every occurrence with start <= at <= end, in time order, as aware datetimes in the plan's zone."""
    if end < start:
        return []
    z = ZoneInfo(s.tz)
    hour, minute = (int(x) for x in s.time_local.split(":"))
    day = start.astimezone(z).date()
    last = end.astimezone(z).date()
    out = []
    while day <= last:
        at = datetime.combine(day, time(hour, minute), tzinfo=z)
        if start <= at <= end and at >= s.starts_at and (s.ends_at is None or at <= s.ends_at) and _matches(s, day):
            out.append(at)
        day += timedelta(days=1)
    return out


def next_occurrences(s: Schedule, start: datetime, count: int, horizon_days: int = 400) -> list[datetime]:
    return occurrences(s, start, start + timedelta(days=horizon_days))[:count]


def end_of_month(at: datetime, tz: str) -> datetime:
    local = at.astimezone(ZoneInfo(tz))
    dim = calendar.monthrange(local.year, local.month)[1]
    return local.replace(day=dim, hour=23, minute=59, second=59, microsecond=999_999)


def start_of_month(at: datetime, tz: str) -> datetime:
    return at.astimezone(ZoneInfo(tz)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def day_key(at: datetime, tz: str) -> date:
    """Local calendar day, used for daily caps."""
    return at.astimezone(ZoneInfo(tz)).date()
