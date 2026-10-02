from datetime import timezone

from engine import Schedule, end_of_month, next_occurrences, occurrences, validate_schedule

from .helpers import TZ, at

BASE = {"tz": TZ, "starts_at": at("2026-01-01T00:00")}


def utc(dts):
    return [d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M") for d in dts]


def test_weekly_friday_2pm_every_friday_in_october_2026():
    s = Schedule(frequency="weekly", weekday=5, time_local="14:00", **BASE)
    got = occurrences(s, at("2026-10-01T00:00"), end_of_month(at("2026-10-01T00:00"), TZ))
    assert utc(got) == ["2026-10-02T13:00", "2026-10-09T13:00", "2026-10-16T13:00", "2026-10-23T13:00", "2026-10-30T13:00"]


def test_daily_6am_uses_lagos_time_and_counts_every_day():
    s = Schedule(frequency="daily", time_local="06:00", **BASE)
    got = occurrences(s, at("2026-10-01T00:00"), end_of_month(at("2026-10-01T00:00"), TZ))
    assert len(got) == 31
    assert utc(got)[0] == "2026-10-01T05:00"


def test_monthly_31st_falls_back_to_last_day():
    s = Schedule(frequency="monthly", month_day=31, time_local="10:00", **BASE)
    got = occurrences(s, at("2027-01-01T00:00"), at("2027-04-30T23:59"))
    assert [d.date().isoformat() for d in got] == ["2027-01-31", "2027-02-28", "2027-03-31", "2027-04-30"]
    leap = Schedule(frequency="monthly", month_day="last", time_local="10:00", **BASE)
    assert occurrences(leap, at("2028-02-01T00:00"), at("2028-02-29T23:59"))[0].date().isoformat() == "2028-02-29"


def test_respects_start_and_end_dates():
    s = Schedule(frequency="daily", time_local="06:00", tz=TZ, starts_at=at("2026-11-15T00:00"), ends_at=at("2026-11-20T23:59"))
    assert len(occurrences(s, at("2026-11-01T00:00"), at("2026-11-30T23:59"))) == 6


def test_skips_a_time_that_already_passed_today():
    s = Schedule(frequency="daily", time_local="06:00", **BASE)
    assert utc(next_occurrences(s, at("2026-10-01T18:00"), 1)) == ["2026-10-02T05:00"]


def test_validation_messages_are_plain():
    assert validate_schedule(Schedule(frequency="weekly", time_local="25:00", **BASE)) == [
        "time must be HH:MM (24h)", "weekly plans need a weekday 1–7 (Mon–Sun)",
    ]
    assert len(validate_schedule(Schedule(frequency="monthly", month_day=32, time_local="10:00", **BASE))) == 1
    assert validate_schedule(Schedule(frequency="daily", time_local="06:00", **BASE)) == []


def test_months_later_clamps_to_month_end():
    from datetime import date
    from engine import months_later
    assert months_later(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert months_later(date(2028, 1, 31), 1) == date(2028, 2, 29)  # leap year
    assert months_later(date(2026, 11, 15), 3) == date(2027, 2, 15)
    assert months_later(date(2026, 12, 1), 12) == date(2027, 12, 1)


def test_for_three_months_monthly_gives_three_drips():
    from engine import all_occurrences, end_after_months
    start = at("2026-11-01T00:00")
    s = Schedule(frequency="monthly", time_local="10:00", tz=TZ, starts_at=start, month_day=1, ends_at=end_after_months(start, 3, TZ))
    assert [d.date().isoformat() for d in all_occurrences(s)] == ["2026-11-01", "2026-12-01", "2027-01-01"]


def test_for_three_months_weekly_stops_before_the_same_date():
    from engine import all_occurrences, end_after_months
    start = at("2026-10-02T00:00")  # a Friday
    s = Schedule(frequency="weekly", time_local="14:00", tz=TZ, starts_at=start, weekday=5, ends_at=end_after_months(start, 3, TZ))
    days = [d.date().isoformat() for d in all_occurrences(s)]
    assert days[0] == "2026-10-02" and days[-1] == "2027-01-01" and len(days) == 14  # up to, not including, 2 Jan


def test_until_a_date_is_inclusive():
    from datetime import date
    from engine import all_occurrences, end_of_local_day
    s = Schedule(frequency="daily", time_local="06:00", tz=TZ, starts_at=at("2026-11-01T00:00"), ends_at=end_of_local_day(date(2026, 11, 3), TZ))
    assert len(all_occurrences(s)) == 3
