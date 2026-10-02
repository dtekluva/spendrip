from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from engine import FeeSchedule, forecast, occurrences
from ledger import services as ledger

from .models import Plan, Run


def fee_schedule() -> FeeSchedule:
    c = settings.SPENDRIP
    tiers = FeeSchedule().provider_tiers if c.get("PASS_THROUGH_TRANSFER_FEES", True) else ((None, 0),)
    return FeeSchedule(service_kobo=c["TRANSFER_FEE_KOBO"], stamp_duty_kobo=c.get("STAMP_DUTY_KOBO", 0),
                       stamp_duty_from_kobo=c.get("STAMP_DUTY_FROM_KOBO", 1_000_000), provider_tiers=tiers)


def fee_kobo(amount_kobo: int) -> int:
    """Total fee for one drip of this amount."""
    return fee_schedule()(amount_kobo)


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
        fee_kobo=fee_schedule(), tz=user.tz, daily_cap_kobo=user.daily_cap_kobo, sent_today_kobo=sent_today_kobo(user, now),
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
    sched = fee_schedule()

    def run(p, at):
        f = sched.parts(p.amount_kobo)
        return Run(plan=p, user_id=p.user_id, scheduled_for=at, amount_kobo=p.amount_kobo, fee_kobo=f.total_kobo,
                   service_fee_kobo=f.service_kobo, provider_fee_kobo=f.provider_kobo, stamp_duty_kobo=f.stamp_duty_kobo)

    rows = [run(p, at) for p in plans for at in occurrences(p.schedule, max(start, p.starts_at), end)]
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


# ---------------------------------------------------------------- start, end and progress

DONE_STATUSES = (Run.Status.SUCCESSFUL, Run.Status.FAILED, Run.Status.SKIPPED_PROTECTED, Run.Status.SKIPPED_INSUFFICIENT,
                 Run.Status.SKIPPED_CAP, Run.Status.SKIPPED_PAUSED, Run.Status.MISSED)


def plan_progress(plan: Plan, now: datetime) -> dict:
    """Where a plan is in its life. Drips that waited or were skipped still use up their slot."""
    from engine import all_occurrences, next_occurrences
    s = plan.schedule
    bounded = plan.ends_at is not None
    every = all_occurrences(s) if bounded else []
    first = every[0] if every else (next_occurrences(s, plan.starts_at, 1) or [None])[0]
    done = Run.objects.filter(plan=plan, status__in=DONE_STATUSES + Run.IN_FLIGHT).count()
    if plan.status == Plan.Status.FINISHED:
        state = "finished"
    elif plan.status == Plan.Status.PAUSED:
        state = "paused"
    elif plan.starts_at > now and done == 0:
        state = "scheduled"  # its start date is still ahead
    else:
        state = "active"
    fee = fee_schedule()(plan.amount_kobo)
    return {
        "state": state,
        "first_drip_at": first,
        "last_drip_at": every[-1] if every else None,
        "total_drips": len(every) if bounded else None,
        "drips_done": done,
        "total_cost_kobo": len(every) * (plan.amount_kobo + fee) if bounded else None,
    }


def release_priority(plan: Plan) -> None:
    """Take a plan out of the priority list; the ones below move up a place."""
    if not plan.priority_rank:
        return
    ranked = list(Plan.objects.filter(user_id=plan.user_id, priority_rank__isnull=False).exclude(pk=plan.pk).order_by("priority_rank"))
    Plan.objects.filter(user_id=plan.user_id).update(priority_rank=None)  # clear first so the unique constraint never trips
    for i, p in enumerate(ranked, start=1):
        Plan.objects.filter(pk=p.pk).update(priority_rank=i)
    plan.priority_rank = None


def finish_plans(now: datetime) -> int:
    """Plans past their end with nothing left to send become Finished and give up their priority."""
    from django.db import transaction
    finished = 0
    for plan in Plan.objects.filter(status__in=[Plan.Status.ACTIVE, Plan.Status.PAUSED], ends_at__lt=now):
        if Run.objects.filter(plan=plan, status__in=(Run.Status.SCHEDULED, *Run.IN_FLIGHT)).exists():
            continue  # its last drip is still being handled
        with transaction.atomic():
            release_priority(plan)
            Plan.objects.filter(pk=plan.pk).update(status=Plan.Status.FINISHED, finished_at=now, priority_rank=None)
        finished += 1
    return finished
