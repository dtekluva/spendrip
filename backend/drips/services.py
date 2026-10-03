from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from engine import FeeSchedule, forecast, occurrences
from ledger import services as ledger

from .models import Plan, PlanLine, Run, RunBatch


def fee_schedule() -> FeeSchedule:
    c = settings.SPENDRIP
    tiers = FeeSchedule().provider_tiers if c.get("PASS_THROUGH_TRANSFER_FEES", True) else ((None, 0),)
    return FeeSchedule(service_kobo=c["TRANSFER_FEE_KOBO"], group_service_kobo=c.get("GROUP_FEE_KOBO", 10_000), stamp_duty_kobo=c.get("STAMP_DUTY_KOBO", 0),
                       stamp_duty_from_kobo=c.get("STAMP_DUTY_FROM_KOBO", 1_000_000), provider_tiers=tiers)


def fee_kobo(amount_kobo: int) -> int:
    """Total fee for one drip of this amount."""
    return fee_schedule()(amount_kobo)


def plan_fee_kobo(plan: Plan) -> int:
    """What one regular payout of this plan costs in fees (group plans: the flat fee plus each transfer's charges)."""
    s = fee_schedule()
    return s.group_fee([ln.amount_kobo for ln in plan.active_lines()]) if plan.is_group else s(plan.amount_kobo)


def engine_plans(user) -> list:
    plans = Plan.objects.filter(user=user).exclude(status=Plan.Status.DELETED).select_related("recipient").prefetch_related("lines")
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
    f = forecast(
        engine_plans(user), bal.available_kobo, now,
        fee_kobo=fee_schedule(), tz=user.tz, daily_cap_kobo=user.daily_cap_kobo, sent_today_kobo=sent_today_kobo(user, now),
    )
    # A group payout that's already due but waiting for money isn't in the forecast (its time has passed), yet it
    # needs that money now. Count it, so "top up" covers it.
    waiting = RunBatch.objects.filter(user=user, status__in=[RunBatch.Status.SCHEDULED, RunBatch.Status.WAITING], scheduled_for__lte=now)
    owed = sum(b.cost_kobo for b in waiting)
    if owed:
        f.total_needed_kobo += owed
        f.top_up_kobo = max(0, f.total_needed_kobo - bal.available_kobo)
    return f


def materialise_runs(now: datetime, *, days: int | None = None, plans=None) -> int:
    """
    Create run rows for every active plan from a little in the past (so a worker restart can
    still catch up within the late window) to `days` ahead. Safe to call repeatedly.
    """
    days = days or settings.SPENDRIP["MATERIALISE_DAYS"]
    start = now - timedelta(hours=settings.SPENDRIP["LATE_SEND_WINDOW_HOURS"])
    end = now + timedelta(days=days)
    plans = plans if plans is not None else Plan.objects.filter(status=Plan.Status.ACTIVE).prefetch_related("lines")
    sched = fee_schedule()

    def run(p, at):
        f = sched.parts(p.amount_kobo)
        return Run(plan=p, user_id=p.user_id, scheduled_for=at, amount_kobo=p.amount_kobo, fee_kobo=f.total_kobo,
                   service_fee_kobo=f.service_kobo, provider_fee_kobo=f.provider_kobo, stamp_duty_kobo=f.stamp_duty_kobo)

    singles = [p for p in plans if not p.is_group]
    rows = [run(p, at) for p in singles for at in occurrences(p.schedule, max(start, p.starts_at), end)]
    created = 0
    if rows:
        before = Run.objects.filter(plan__in={r.plan_id for r in rows}).count()
        Run.objects.bulk_create(rows, ignore_conflicts=True)  # returns every row passed in, so count instead
        created = Run.objects.filter(plan__in={r.plan_id for r in rows}).count() - before
    for p in plans:
        if p.is_group:
            created += _materialise_group(p, sched, start, end)
    return created


def _materialise_group(plan: Plan, sched, start: datetime, end: datetime) -> int:
    """One batch per payout, with one run per person. One-off changes (a bonus, someone skipped) go into the
    plan's next scheduled batch only; later batches use everyone's regular amount."""
    from django.db import IntegrityError, transaction
    # Lock the plan row: the worker and an edit in the app can both build batches for the same plan at the same moment.
    with transaction.atomic():
        Plan.objects.select_for_update().filter(pk=plan.pk).exists()
        return _build_group_batches(plan, sched, start, end, IntegrityError, transaction)


def _build_group_batches(plan: Plan, sched, start: datetime, end: datetime, IntegrityError, transaction) -> int:
    existing = set(RunBatch.objects.filter(plan=plan).values_list("scheduled_for", flat=True))
    has_pending = RunBatch.objects.filter(plan=plan, status__in=[RunBatch.Status.SCHEDULED, RunBatch.Status.WAITING]).exists()
    lines = plan.active_lines()
    created = 0
    for at in occurrences(plan.schedule, max(start, plan.starts_at), end):
        if at in existing:
            continue
        use_next = not has_pending
        has_pending = True
        paying = [(ln, ln.next_amount if use_next else ln.amount_kobo) for ln in lines if not (use_next and ln.skip_next)]
        if not paying:
            continue
        parts = sched.group_parts([a for _, a in paying])
        try:
            with transaction.atomic():
                batch = RunBatch.objects.create(plan=plan, user_id=plan.user_id, scheduled_for=at, amount_kobo=sum(a for _, a in paying),
                                                fee_kobo=sum(f.total_kobo for f in parts))
                Run.objects.bulk_create([
                    Run(plan=plan, line=ln, batch=batch, user_id=plan.user_id, scheduled_for=at, amount_kobo=a, fee_kobo=f.total_kobo,
                        service_fee_kobo=f.service_kobo, provider_fee_kobo=f.provider_kobo, stamp_duty_kobo=f.stamp_duty_kobo)
                    for (ln, a), f in zip(paying, parts)])
        except IntegrityError:
            continue  # someone else built this payout a moment ago; theirs stands
        created += len(paying)
    return created


def reschedule(plan: Plan, now: datetime | None = None) -> None:
    """After a plan changes, drop its future scheduled runs and create them again from the new settings."""
    from django.db import transaction
    now = now or timezone.now()
    with transaction.atomic():
        Plan.objects.select_for_update().filter(pk=plan.pk).exists()  # one rebuild at a time per plan (a double tap sends two)
        if plan.is_group:
            # Nothing in a scheduled or waiting batch has moved money yet, so rebuild them all (a waiting one keeps its time).
            RunBatch.objects.filter(plan=plan, status__in=[RunBatch.Status.SCHEDULED, RunBatch.Status.WAITING]).delete()
            # A one-person plan that just became a group: its own scheduled drips must not go out as well.
            Run.objects.filter(plan=plan, batch__isnull=True, status=Run.Status.SCHEDULED).delete()
        else:
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
    if plan.is_group:
        done = RunBatch.objects.filter(plan=plan, status__in=[RunBatch.Status.SENDING, RunBatch.Status.DONE, RunBatch.Status.SKIPPED]).count()
    else:
        done = Run.objects.filter(plan=plan, status__in=DONE_STATUSES + Run.IN_FLIGHT).count()
    if plan.status == Plan.Status.FINISHED:
        state = "finished"
    elif plan.status == Plan.Status.PAUSED:
        state = "paused"
    elif plan.starts_at > now and done == 0:
        state = "scheduled"  # its start date is still ahead
    else:
        state = "active"
    fee = plan_fee_kobo(plan)
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
        if Run.objects.filter(plan=plan, status__in=(Run.Status.SCHEDULED, *Run.IN_FLIGHT)).exists() or \
                RunBatch.objects.filter(plan=plan, status__in=[RunBatch.Status.WAITING, RunBatch.Status.SENDING]).exists():
            continue  # its last drip is still being handled
        with transaction.atomic():
            release_priority(plan)
            Plan.objects.filter(pk=plan.pk).update(status=Plan.Status.FINISHED, finished_at=now, priority_rank=None)
        finished += 1
    return finished


# ---------------------------------------------------------------- group plans

def save_lines(plan: Plan, lines: list[dict]) -> None:
    """Replace a group plan's people with `lines` ([{recipient, amount_kobo, next_amount_kobo?, skip_next?}], in order).
    People who drop off are kept as inactive lines so past payouts still point at them. Keeps plan.amount_kobo in step."""
    current = {ln.recipient_id: ln for ln in plan.lines.filter(active=True)}
    keep = set()
    for i, d in enumerate(lines):
        r = d["recipient"]
        ln = current.get(r.pk) or PlanLine(plan=plan, recipient=r)
        ln.amount_kobo, ln.position = d["amount_kobo"], i
        ln.next_amount_kobo = d.get("next_amount_kobo")
        ln.skip_next = bool(d.get("skip_next", False))
        ln.active = True
        ln.save()
        keep.add(r.pk)
    plan.lines.filter(active=True).exclude(recipient_id__in=keep).update(active=False)
    plan.amount_kobo = sum(d["amount_kobo"] for d in lines)
    plan.save(update_fields=["amount_kobo", "updated_at"])


def clear_one_offs(plan: Plan) -> None:
    """A payout has gone out: one-off amounts and skips were for that payout only."""
    plan.lines.filter(active=True).update(next_amount_kobo=None, skip_next=False)


def retry_batch(batch: RunBatch, now: datetime | None = None) -> RunBatch:
    """
    "Send again": a new payout, due now, for everyone on a finished batch who wasn't paid. Each person keeps the amount
    they were due. Money rules are the usual ones (all or nothing, daily cap, priorities), so it waits like any payout
    if the balance can't cover it. A batch can be sent again once; the retry can itself be retried.
    """
    from django.db import transaction
    now = now or timezone.now()
    with transaction.atomic():
        batch = RunBatch.objects.select_for_update().select_related("plan").get(pk=batch.pk)
        if batch.status not in (RunBatch.Status.DONE, RunBatch.Status.SKIPPED):
            raise ValueError("still_going")
        if hasattr(batch, "retry"):
            raise ValueError("already_retried")
        if batch.plan.status == Plan.Status.DELETED:
            raise ValueError("plan_deleted")
        unpaid = [r for r in batch.runs.select_related("line").order_by("line__position", "id") if r.status != Run.Status.SUCCESSFUL and r.line and r.line.active]
        if not unpaid:
            raise ValueError("nobody_unpaid")
        parts = fee_schedule().group_parts([r.amount_kobo for r in unpaid])
        new = RunBatch.objects.create(plan=batch.plan, user_id=batch.user_id, scheduled_for=now, retry_of=batch,
                                      amount_kobo=sum(r.amount_kobo for r in unpaid), fee_kobo=sum(f.total_kobo for f in parts))
        Run.objects.bulk_create([
            Run(plan=batch.plan, line=r.line, batch=new, user_id=batch.user_id, scheduled_for=now, amount_kobo=r.amount_kobo,
                fee_kobo=f.total_kobo, service_fee_kobo=f.service_kobo, provider_fee_kobo=f.provider_kobo, stamp_duty_kobo=f.stamp_duty_kobo)
            for r, f in zip(unpaid, parts)])
    return new
