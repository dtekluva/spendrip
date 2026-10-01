from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from engine import forecast, occurrences
from ledger import services as ledger

from .models import Plan, Run


def fee_kobo() -> int:
    return settings.SPENDRIP["TRANSFER_FEE_KOBO"]


def engine_plans(user) -> list:
    plans = Plan.objects.filter(user=user).exclude(status=Plan.Status.DELETED).select_related("recipient")
    out = [p.to_engine() for p in plans]
    if user.paused_all:
        from dataclasses import replace
        out = [replace(p, status="paused") for p in out]
    return out


def local_day_bounds(at: datetime, tz: str) -> tuple[datetime, datetime]:
    local = at.astimezone(ZoneInfo(tz))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def sent_today_kobo(user, now: datetime) -> int:
    start, end = local_day_bounds(now, user.tz)
    runs = Run.objects.filter(user=user, status__in=Run.COUNTS_TOWARDS_CAP, scheduled_for__gte=start, scheduled_for__lt=end)
    return sum(r.amount_kobo for r in runs)


def user_forecast(user, now: datetime | None = None):
    now = now or timezone.now()
    bal = ledger.balance(user)
    return forecast(
        engine_plans(user), bal.available_kobo, now,
        fee_kobo=fee_kobo(), tz=user.tz, daily_cap_kobo=user.daily_cap_kobo, sent_today_kobo=sent_today_kobo(user, now),
    )


def materialise_runs(now: datetime, *, days: int | None = None, plans=None) -> int:
    """
    Create run rows for every active plan from a little in the past (so a worker restart can
    still catch up within the late window) to `days` ahead. Safe to call repeatedly.
    """
    days = days or settings.SPENDRIP["MATERIALISE_DAYS"]
    start = now - timedelta(hours=settings.SPENDRIP["LATE_SEND_WINDOW_HOURS"])
    end = now + timedelta(days=days)
    plans = plans if plans is not None else Plan.objects.filter(status=Plan.Status.ACTIVE)
    fee = fee_kobo()
    rows = [
        Run(plan=p, user_id=p.user_id, scheduled_for=at, amount_kobo=p.amount_kobo, fee_kobo=fee)
        for p in plans
        for at in occurrences(p.schedule, max(start, p.starts_at), end)
    ]
    if not rows:
        return 0
    before = Run.objects.filter(plan__in={r.plan_id for r in rows}).count()
    Run.objects.bulk_create(rows, ignore_conflicts=True)  # returns every row passed in, so count instead
    return Run.objects.filter(plan__in={r.plan_id for r in rows}).count() - before


def reschedule(plan: Plan, now: datetime | None = None) -> None:
    """After a plan changes, drop its future scheduled runs and create them again from the new settings."""
    now = now or timezone.now()
    Run.objects.filter(plan=plan, status=Run.Status.SCHEDULED, scheduled_for__gt=now).delete()
    if plan.status == Plan.Status.ACTIVE:
        materialise_runs(now, plans=[plan])
