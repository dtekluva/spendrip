"""Endpoints behind the main screens. All need the app unlocked (the default permission)."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts import services as acc
from accounts.services import FlowError
from drips.models import Plan, Recipient, Run, RunBatch
from drips.services import (engine_plans, fee_schedule, plan_fee_kobo, plan_progress, reschedule, retry_batch, save_lines,
                            sent_today_kobo, user_forecast)
from engine import (
    MAX_PLAN_MONTHS,
    PlanLike,
    Schedule,
    all_occurrences,
    end_after_months,
    end_of_local_day,
    forecast,
    months_later,
    next_occurrences,
    occurrences,
    set_priority,
    start_of_local_day,
    validate_schedule,
)
from ledger import services as ledger
from ledger.models import Inflow
from notifications.models import OutboxMessage
from providers import get_payout_provider, names

from providers.banks import BANKS, BY_NIP

TINTS = {"cobalt", "sun", "hibiscus", "mint"}
MIN_AMOUNT_KOBO, MAX_AMOUNT_KOBO = 10_000, 1_000_000_000  # ₦100 – ₦10m
MIN_GROUP, MAX_GROUP = 2, 50  # people on a group plan


# ------------------------------------------------------------------ helpers

def event_json(e) -> dict:
    return {"plan_id": int(e.plan_id) if str(e.plan_id).isdigit() else e.plan_id, "at": e.at, "amount_kobo": e.amount_kobo,
            "fee_kobo": e.fee_kobo, "rank": e.rank, "status": e.status}


def fees_json() -> dict:
    """The fee rules, so the app can show the lines for any amount."""
    return fee_schedule().describe()


def forecast_json(f) -> dict:
    return {"window_end": f.window_end, "protected_kobo": f.protected_kobo, "free_kobo": f.free_kobo,
            "total_needed_kobo": f.total_needed_kobo, "top_up_kobo": f.top_up_kobo,
            "priority_shortfall_kobo": f.priority_shortfall_kobo, "events": [event_json(e) for e in f.events]}


def recipient_json(r: Recipient) -> dict:
    return {"id": r.id, "label": r.label, "is_self": r.is_self, "bank_name": r.bank_name, "nip_bank_code": r.nip_bank_code,
            "account_last4": r.account_number[-4:], "verified_account_name": r.verified_account_name,
            "whatsapp": r.whatsapp, "notify_whatsapp": r.notify_whatsapp}


def line_json(ln) -> dict:
    return {"id": ln.id, "recipient": recipient_json(ln.recipient), "amount_kobo": ln.amount_kobo,
            "next_amount_kobo": ln.next_amount_kobo, "skip_next": ln.skip_next}


def group_json(p: Plan) -> dict:
    """Group plans: the people, and what the next payout and a regular one cost."""
    if not p.is_group:
        return {"lines": None}
    lines = p.active_lines()
    sched = fee_schedule()
    nxt = [ln.next_amount for ln in lines if not ln.skip_next]
    return {"lines": [line_json(ln) for ln in lines], "people": len(lines),
            "next_payout": {"people": len(nxt), "amount_kobo": sum(nxt), "fee_kobo": sched.group_fee(nxt) if nxt else 0,
                            "changed": any(ln.skip_next or ln.next_amount_kobo is not None for ln in lines)}}


def plan_json(p: Plan, now: datetime) -> dict:
    nxt = next_occurrences(p.schedule, now, 1) if p.status == Plan.Status.ACTIVE else []
    z = ZoneInfo(p.tz)
    return {"id": p.id, "kind": p.kind, "label": p.label, "emoji": p.emoji, "tint": p.tint, "amount_kobo": p.amount_kobo,
            "fee_kobo": plan_fee_kobo(p), **group_json(p),
            "recipient": recipient_json(p.recipient) if p.recipient and not p.is_group else None, "frequency": p.frequency, "weekday": p.weekday, "month_day": p.month_day,
            "month_day_last": p.month_day_last, "time_local": p.time_local, "tz": p.tz, "starts_at": p.starts_at,
            "ends_at": p.ends_at, "status": p.status, "priority_rank": p.priority_rank, "next_at": nxt[0] if nxt else None,
            "start_date": p.starts_at.astimezone(z).date(), "end_mode": p.end_mode, "duration_months": p.duration_months,
            "end_date": p.ends_at.astimezone(z).date() if p.ends_at and p.end_mode == Plan.EndMode.DATE else None,
            "finished_at": p.finished_at, **plan_progress(p, now)}


def user_plans(user):
    return (Plan.objects.filter(user=user).exclude(status=Plan.Status.DELETED).select_related("recipient")
            .prefetch_related("lines__recipient").order_by("created_at"))


def priority_order(user) -> list[str]:
    ranked = Plan.objects.filter(user=user, priority_rank__isnull=False).exclude(status=Plan.Status.DELETED).order_by("priority_rank")
    return [str(p.pk) for p in ranked]


@transaction.atomic
def apply_priority(user, plan: Plan, rank: int) -> list[str]:
    """Set a plan's priority (0 = none). Others shift down; a plan pushed past 3 stops being a priority. Returns dropped labels."""
    if rank not in (0, 1, 2, 3):
        raise FlowError("Priority must be 1, 2, 3 or off.")
    order, dropped = set_priority(priority_order(user), str(plan.pk), rank)
    Plan.objects.filter(user=user).update(priority_rank=None)  # clear first so the unique constraint never trips mid-update
    for i, pid in enumerate(order, start=1):
        Plan.objects.filter(pk=int(pid)).update(priority_rank=i)
    return list(Plan.objects.filter(pk__in=[int(d) for d in dropped]).values_list("label", flat=True))


def parse_plan(data, user, instance: Plan | None = None) -> dict:
    """Validate a plan body. On update, missing fields keep their current value."""
    cur = (lambda k, d=None: getattr(instance, k)) if instance else (lambda k, d=None: d)
    out = {}
    label = str(data.get("label", cur("label", ""))).strip()
    if not 1 <= len(label) <= 40:
        raise FlowError("Give the plan a name (up to 40 characters).")
    out["label"] = label
    out["emoji"] = str(data.get("emoji", cur("emoji", "💸")))[:8] or "💸"
    tint = data.get("tint", cur("tint", "cobalt"))
    out["tint"] = tint if tint in TINTS else "cobalt"
    kind = data.get("kind") or (instance.kind if instance else Plan.Kind.SINGLE)
    if kind not in (Plan.Kind.SINGLE, Plan.Kind.GROUP):
        raise FlowError("A plan is for one person or a group.")
    if instance and instance.is_group and kind != Plan.Kind.GROUP:
        raise FlowError("A group plan can't turn back into a one-person plan. Remove people instead, or make a new plan.")
    out["kind"] = kind
    if kind == Plan.Kind.GROUP:
        if "lines" in data or not instance or not instance.is_group:
            out["lines"] = _lines(data.get("lines"), user)
            out["amount_kobo"] = sum(d["amount_kobo"] for d in out["lines"])
        else:
            out["amount_kobo"] = instance.amount_kobo
        out["recipient"] = None  # a group pays its lines; a one-person plan turned group lets go of its person
    else:
        out["amount_kobo"] = _amount_ok(data.get("amount_kobo", cur("amount_kobo", 0)), user)
        rid = data.get("recipient_id", instance.recipient_id if instance else None)
        recipient = Recipient.objects.filter(pk=rid, user=user).first()
        if not recipient:
            raise FlowError("Choose who gets the money.")
        out["recipient"] = recipient
    out["frequency"] = data.get("frequency", cur("frequency"))
    out["weekday"] = _int(data.get("weekday", cur("weekday"))) if out["frequency"] == "weekly" else None
    md = _int(data.get("month_day", cur("month_day"))) if out["frequency"] == "monthly" else None
    out["month_day_last"] = bool(data.get("month_day_last", cur("month_day_last", False))) if out["frequency"] == "monthly" else False
    out["month_day"] = None if out["month_day_last"] else md
    out["time_local"] = str(data.get("time_local", cur("time_local", "")))
    out["tz"] = user.tz
    out.update(_window(data, user, instance))
    sched = Schedule(frequency=out["frequency"], time_local=out["time_local"], tz=out["tz"], starts_at=out["starts_at"],
                     weekday=out["weekday"], month_day="last" if out["month_day_last"] else out["month_day"], ends_at=out["ends_at"])
    errors = validate_schedule(sched)
    if errors:
        raise FlowError(errors[0][0].upper() + errors[0][1:] + ".")
    if out["ends_at"] and not all_occurrences(sched):
        raise FlowError("This ends before its first drip. Pick a later end.", code="no_drips")
    return out


def _amount_ok(v, user, who: str = "") -> int:
    from engine import format_naira
    try:
        amount = int(v)
    except (TypeError, ValueError):
        raise FlowError(f"Enter an amount{' for ' + who if who else ''}.")
    if not MIN_AMOUNT_KOBO <= amount <= MAX_AMOUNT_KOBO:
        raise FlowError(f"{who}'s amount must be between ₦100 and ₦10,000,000." if who else "Amounts must be between ₦100 and ₦10,000,000.")
    lim = acc.limits(user)
    if lim and amount > lim["max_drip_kobo"]:
        cap = format_naira(lim["max_drip_kobo"])
        raise FlowError(f"Each transfer can be up to {cap} for now, so {who}'s is too high." if who else f"Each drip can be up to {cap} for now.",
                        code="over_limit")
    return amount


def _lines(raw, user) -> list[dict]:
    """People on a group plan: [{recipient_id, amount_kobo, next_amount_kobo?, skip_next?}], in the order to show them."""
    if not isinstance(raw, list) or not MIN_GROUP <= len(raw) <= MAX_GROUP:
        raise FlowError(f"A group needs {MIN_GROUP} to {MAX_GROUP} people.")
    def pk(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    ids = [pk(d.get("recipient_id")) if isinstance(d, dict) else None for d in raw]
    people = {r.pk: r for r in Recipient.objects.filter(user=user, pk__in=[i for i in ids if i])}
    out, seen = [], set()
    for d, rid in zip(raw, ids):
        r = people.get(rid)
        if not r:
            raise FlowError("Someone on the list isn't one of your saved people. Add them first.")
        if r.pk in seen:
            raise FlowError(f"{r.label} is on the list twice.", code="duplicate_person")
        seen.add(r.pk)
        line = {"recipient": r, "amount_kobo": _amount_ok(d.get("amount_kobo"), user, r.label), "skip_next": bool(d.get("skip_next", False))}
        nxt = d.get("next_amount_kobo")
        line["next_amount_kobo"] = _amount_ok(nxt, user, r.label) if nxt not in (None, "") else None
        out.append(line)
    if all(d["skip_next"] for d in out):
        raise FlowError("Everyone is skipped next time. Pause the plan instead.", code="all_skipped")
    return out


def _date(v, what: str):
    from datetime import date
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        raise FlowError(f"Pick a valid {what} date.")


def _window(data, user, instance: Plan | None) -> dict:
    """When a plan starts and ends, from start_date ("today" or YYYY-MM-DD), end_mode, duration_months and end_date."""
    tz, now = user.tz, timezone.now()
    today = now.astimezone(ZoneInfo(tz)).date()
    sent = (Run.objects.filter(plan=instance).exclude(status__in=[Run.Status.SCHEDULED, Run.Status.CANCELLED])
            .order_by("-scheduled_for").first()) if instance else None

    if "start_date" in data and data["start_date"] not in (None, ""):
        raw = str(data["start_date"])
        day = today if raw == "today" else _date(raw, "start")
        current = instance.starts_at.astimezone(ZoneInfo(tz)).date() if instance else None
        if instance and day == current:
            starts = instance.starts_at
        elif sent:
            raise FlowError("This plan has already sent drips, so its start date can't change.", code="started")
        elif day < today:
            raise FlowError("Pick today or a later date to start.")
        elif day > months_later(today, 12):
            raise FlowError("Plans can start up to a year from today.")
        else:
            starts = now if day == today else start_of_local_day(day, tz)
    else:
        starts = instance.starts_at if instance else now

    mode = data.get("end_mode") or (instance.end_mode if instance else Plan.EndMode.ONGOING)
    months = None
    if mode == Plan.EndMode.ONGOING:
        ends = None
    elif mode == Plan.EndMode.MONTHS:
        try:
            months = int(data.get("duration_months") or (instance.duration_months if instance else 0) or 0)
        except (TypeError, ValueError):
            months = 0
        if not 1 <= months <= MAX_PLAN_MONTHS:
            raise FlowError(f"Choose between 1 and {MAX_PLAN_MONTHS} months.")
        ends = end_after_months(starts, months, tz)
    elif mode == Plan.EndMode.DATE:
        raw = data.get("end_date") or (instance.ends_at.astimezone(ZoneInfo(tz)).date().isoformat()
                                        if instance and instance.ends_at else None)
        if not raw:
            raise FlowError("Pick the date the plan ends.")
        day = _date(raw, "end")
        start_day = starts.astimezone(ZoneInfo(tz)).date()
        if day < start_day:
            raise FlowError("The end date is before the start. Pick a later date.")
        if day > months_later(start_day, MAX_PLAN_MONTHS):
            raise FlowError(f"Plans can run for up to {MAX_PLAN_MONTHS} months. Pick an earlier end, or let it keep going.")
        ends = end_of_local_day(day, tz)
    else:
        raise FlowError("End must be: keeps going, a number of months, or a date.")

    if ends and sent and sent.scheduled_for > ends:
        when = sent.scheduled_for.astimezone(ZoneInfo(tz))
        raise FlowError(f"A drip already went out on {when:%-d %b %Y}. Pick an end after that.", code="end_before_sent")
    if ends and ends < now and not sent:
        raise FlowError("That end has already passed. Pick a later end.")
    return {"starts_at": starts, "ends_at": ends, "end_mode": mode, "duration_months": months}


def _int(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        raise FlowError("Day must be a number.")


def _dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        raise FlowError("Dates must look like 2026-11-01T00:00:00+01:00.")


# ------------------------------------------------------------------ summary

class Summary(APIView):
    """What Home needs: balance plus this month's forecast."""

    def get(self, request):
        user = request.user
        bal = ledger.balance(user)
        fa = user.funding_accounts.first()
        return Response({
            "balance": {"available_kobo": bal.available_kobo, "held_kobo": bal.held_kobo, "total_kobo": bal.total_kobo},
            "forecast": forecast_json(user_forecast(user)),
            "fee_kobo": fee_schedule().service_kobo,  # SpenDrip's own fee; see "fees" for the full rules
            "fees": fees_json(),
            "paused_all": user.paused_all,
            "funding_account": {"account_number": fa.account_number, "bank_name": fa.bank_name, "account_name": fa.account_name} if fa else None,
        })


# ------------------------------------------------------------------ banks and recipients

class Banks(APIView):
    def get(self, request):
        return Response([{"name": n, "nip_code": nip} for n, nip, _ in BANKS])


def check_name(code: str, number: str):
    try:
        return names.resolve(code, number)
    except names.NameCheckFailed as e:
        raise FlowError(e.message, code=e.code, status=e.status)


class RecipientLookup(APIView):
    """Check an account before saving it, so money can't go to the wrong person."""

    def post(self, request):
        code, number = str(request.data.get("nip_bank_code", "")), str(request.data.get("account_number", ""))
        if code not in BY_NIP:
            raise FlowError("Choose a bank.")
        if not (len(number) == 10 and number.isdigit()):
            raise FlowError("Account numbers have 10 digits.")
        n = check_name(code, number)
        return Response({"account_name": n.account_name, "bank_name": BY_NIP[code][0], "test_name": n.test_name})


class Recipients(APIView):
    def get(self, request):
        return Response([recipient_json(r) for r in request.user.recipients.order_by("-is_self", "created_at")])

    def post(self, request):
        d = request.data
        label = str(d.get("label", "")).strip()
        code, number = str(d.get("nip_bank_code", "")), str(d.get("account_number", ""))
        if not label:
            raise FlowError("What do you call them? For example, Mum.")
        if code not in BY_NIP or not (len(number) == 10 and number.isdigit()):
            raise FlowError("Choose a bank and enter a 10-digit account number.")
        if request.user.recipients.filter(nip_bank_code=code, account_number=number).exists():
            raise FlowError("You've already saved this account.", code="duplicate", status=409)
        name = check_name(code, number).account_name  # always checked server-side (reuses the lookup's answer)
        r = Recipient.objects.create(
            user=request.user, label=label[:60], is_self=bool(d.get("is_self", False)), bank_name=BY_NIP[code][0], nip_bank_code=code,
            cbn_bank_code=BY_NIP[code][1], account_number=number, verified_account_name=name,
            whatsapp=str(d.get("whatsapp", ""))[:20], notify_whatsapp=bool(d.get("notify_whatsapp", True)), verified_at=timezone.now(),
        )
        return Response(recipient_json(r), status=201)


class RecipientDetail(APIView):
    def delete(self, request, pk):
        r = request.user.recipients.filter(pk=pk).first()
        if not r:
            raise FlowError("That person isn't in your list.", status=404)
        using = list(r.plans.exclude(status=Plan.Status.DELETED).values_list("label", flat=True)) + list(
            r.plan_lines.filter(active=True).exclude(plan__status=Plan.Status.DELETED).values_list("plan__label", flat=True))
        if using:
            raise FlowError(f"{', '.join(using)} still pays this person. Change or delete those plans first.", code="in_use", status=409)
        if r.plans.exists() or r.plan_lines.exists():
            r.plans.update(status=Plan.Status.DELETED)  # keep history; deleted plans keep pointing at it
            r.label = f"{r.label} (removed)"
            r.save(update_fields=["label"])
        else:
            r.delete()
        return Response(status=204)


# ------------------------------------------------------------------ plans

class Plans(APIView):
    def get(self, request):
        now = timezone.now()
        return Response([plan_json(p, now) for p in user_plans(request.user)])

    def post(self, request):
        fields = parse_plan(request.data, request.user)
        lines = fields.pop("lines", None)
        rank = int(request.data.get("priority_rank") or 0)
        with transaction.atomic():
            plan = Plan.objects.create(user=request.user, **fields)
            if lines is not None:
                save_lines(plan, lines)
            dropped = apply_priority(request.user, plan, rank) if rank else []
        plan.refresh_from_db()
        reschedule(plan)
        return Response({"plan": plan_json(plan, timezone.now()), "dropped_priorities": dropped}, status=201)


class PlanDetail(APIView):
    def _get(self, request, pk) -> Plan:
        p = user_plans(request.user).filter(pk=pk).first()
        if not p:
            raise FlowError("That plan doesn't exist.", status=404)
        return p

    def patch(self, request, pk):
        plan = self._get(request, pk)
        d = request.data
        dropped = []
        with transaction.atomic():
            was_finished = plan.status == Plan.Status.FINISHED
            schedule_keys = {"label", "emoji", "tint", "amount_kobo", "recipient_id", "frequency", "weekday", "month_day",
                             "month_day_last", "time_local", "start_date", "end_mode", "duration_months", "end_date", "kind", "lines"}
            lines = None
            if schedule_keys & set(d):
                parsed = parse_plan(d, request.user, instance=plan)
                lines = parsed.pop("lines", None)
                for k, v in parsed.items():
                    setattr(plan, k, v)
            if was_finished and (plan.ends_at is None or plan.ends_at > timezone.now()):
                plan.status, plan.finished_at = Plan.Status.ACTIVE, None  # extended: it runs again
            if "status" in d:
                if d["status"] not in (Plan.Status.ACTIVE, Plan.Status.PAUSED):
                    raise FlowError("Status must be active or paused.")
                if plan.status == Plan.Status.FINISHED:
                    raise FlowError("This plan has finished. Extend its end date to start it again.", code="finished")
                plan.status = d["status"]
            plan.save()
            if lines is not None:
                if RunBatch.objects.filter(plan=plan, status=RunBatch.Status.SENDING).exists():
                    raise FlowError("A payout for this group is going out right now. Try again in a minute.", code="sending", status=409)
                save_lines(plan, lines)
            if "priority_rank" in d:
                dropped = apply_priority(request.user, plan, int(d["priority_rank"] or 0))
        plan.refresh_from_db()
        reschedule(plan)
        return Response({"plan": plan_json(plan, timezone.now()), "dropped_priorities": dropped})

    def delete(self, request, pk):
        plan = self._get(request, pk)
        with transaction.atomic():
            if plan.priority_rank:
                apply_priority(request.user, plan, 0)
            plan.status = Plan.Status.DELETED
            plan.save(update_fields=["status", "updated_at"])
            Run.objects.filter(plan=plan, status=Run.Status.SCHEDULED).update(status=Run.Status.CANCELLED)
            RunBatch.objects.filter(plan=plan, status__in=[RunBatch.Status.SCHEDULED, RunBatch.Status.WAITING]).update(status=RunBatch.Status.CANCELLED)
        return Response(status=204)


def whole_plan(sched: Schedule, amount_kobo: int, fee: int | None = None) -> dict:
    """Totals for a plan with an end, so people see the full commitment before saving."""
    every = all_occurrences(sched)
    first = every[0] if every else (next_occurrences(sched, sched.starts_at, 1) or [None])[0]
    fee = fee_schedule()(amount_kobo) if fee is None else fee
    return {"first_drip_at": first, "last_drip_at": every[-1] if every else None,
            "total_drips": len(every) if sched.ends_at else None,
            "total_amount_kobo": len(every) * amount_kobo if sched.ends_at else None,
            "total_fees_kobo": len(every) * fee if sched.ends_at else None}


class PlanPreview(APIView):
    """What a new or edited plan would do: next dates, this month's cost and the effect on the top-up."""

    def post(self, request):
        user, now = request.user, timezone.now()
        d = request.data
        editing = user_plans(user).filter(pk=d.get("plan_id")).first() if d.get("plan_id") else None
        fields = parse_plan(d, user, instance=editing)
        sched = Schedule(frequency=fields["frequency"], time_local=fields["time_local"], tz=fields["tz"], starts_at=fields["starts_at"],
                         weekday=fields["weekday"], month_day="last" if fields["month_day_last"] else fields["month_day"],
                         ends_at=fields["ends_at"])
        rank = int(d.get("priority_rank") or 0)
        draft_id = str(editing.pk) if editing else "draft"

        before = engine_plans(user)
        others = [p for p in before if p.id != draft_id]
        order, dropped = set_priority([p.id for p in sorted(others, key=lambda p: p.priority_rank or 9) if p.priority_rank], draft_id, rank)
        ranks = {pid: i + 1 for i, pid in enumerate(order)}
        lines = fields.get("lines")
        if lines is None and editing and editing.is_group:
            lines = [{"amount_kobo": ln.amount_kobo, "next_amount_kobo": ln.next_amount_kobo, "skip_next": ln.skip_next}
                     for ln in editing.active_lines()]
        line_amounts = next_amounts = None
        if lines is not None:
            line_amounts = tuple(ln["amount_kobo"] for ln in lines)
            nxt = tuple(ln["next_amount_kobo"] or ln["amount_kobo"] for ln in lines if not ln["skip_next"])
            next_amounts = nxt if nxt != line_amounts else None
        draft = PlanLike(id=draft_id, amount_kobo=fields["amount_kobo"], schedule=sched, priority_rank=ranks.get(draft_id),
                         order=editing.pk if editing else 10**9, line_amounts=line_amounts, next_line_amounts=next_amounts)
        sched_fees = fee_schedule()
        if line_amounts is not None:
            per_line = sched_fees.group_parts(line_amounts)
            fee_lines = [{"kind": k, "label": label, "amount_kobo": total} for k, label, total in (
                ("service", "SpenDrip fee (whole group)", sum(f.service_kobo for f in per_line)),
                ("provider", f"Transfer fees (Paystack, {len(per_line)} transfers)", sum(f.provider_kobo for f in per_line)),
                ("stamp_duty", "Stamp duty", sum(f.stamp_duty_kobo for f in per_line))) if total]
            payout_fee = sum(f.total_kobo for f in per_line)
        else:
            fee_lines = sched_fees.parts(fields["amount_kobo"]).lines()
            payout_fee = sched_fees(fields["amount_kobo"])
        after = [replace(p, priority_rank=ranks.get(p.id)) for p in others] + [draft]

        bal = ledger.balance(user).available_kobo
        kw = dict(fee_kobo=fee_schedule(), tz=user.tz, daily_cap_kobo=user.daily_cap_kobo, sent_today_kobo=sent_today_kobo(user, now))
        f0, f1 = forecast(before, bal, now, **kw), forecast(after, bal, now, **kw)
        mine = [e for e in f1.events if e.plan_id == draft_id]
        labels = {str(p.pk): p.label for p in user_plans(user)}
        return Response({
            "next_dates": next_occurrences(sched, now, 5),
            "runs_this_month": len(mine),
            "month_cost_kobo": sum(e.cost_kobo for e in mine),
            "fee_kobo": payout_fee,
            "fee_lines": fee_lines,
            "top_up_before_kobo": f0.top_up_kobo,
            "top_up_after_kobo": f1.top_up_kobo,
            "draft_waiting": sum(1 for e in mine if e.status in ("wait", "short", "cap")),
            "priorities_short_after_kobo": f1.priority_shortfall_kobo,
            "priority_order": [labels.get(pid, fields["label"]) for pid in order],
            "dropped_priorities": [labels.get(pid, pid) for pid in dropped],
            "daily_cap_kobo": user.daily_cap_kobo,
            "over_daily_cap": bool(user.daily_cap_kobo and fields["amount_kobo"] > user.daily_cap_kobo),
            **whole_plan(sched, fields["amount_kobo"], payout_fee),
        })


# ------------------------------------------------------------------ calendar and activity

RUN_STATUS = {
    Run.Status.SUCCESSFUL: "sent", Run.Status.SKIPPED_PROTECTED: "waited", Run.Status.SKIPPED_INSUFFICIENT: "waited",
    Run.Status.SKIPPED_CAP: "waited", Run.Status.FAILED: "failed", Run.Status.MISSED: "missed",
    Run.Status.SKIPPED_PAUSED: "paused", Run.Status.CANCELLED: "paused",
    Run.Status.PENDING: "sending", Run.Status.RESERVED: "sending", Run.Status.UNKNOWN: "sending",
}


class Calendar(APIView):
    def get(self, request):
        user, now = request.user, timezone.now()
        z = ZoneInfo(user.tz)
        local_now = now.astimezone(z)
        try:
            y, m = (int(x) for x in request.query_params.get("month", local_now.strftime("%Y-%m")).split("-"))
            start = datetime(y, m, 1, tzinfo=z)
        except ValueError:
            raise FlowError("month must look like 2026-10.")
        end = (start + timedelta(days=32)).replace(day=1) - timedelta(microseconds=1)
        months_away = (y - local_now.year) * 12 + (m - local_now.month)
        if not -3 <= months_away <= 2:
            raise FlowError("The calendar shows 3 months back and 2 ahead.")

        events, batches = [], {}
        for r in Run.objects.filter(user=user, scheduled_for__gte=start, scheduled_for__lte=min(end, now)).exclude(status=Run.Status.SCHEDULED):
            if r.batch_id:  # one calendar entry per group payout
                b = batches.setdefault(r.batch_id, {"plan_id": r.plan_id, "at": r.scheduled_for, "amount_kobo": 0, "statuses": []})
                b["amount_kobo"] += r.amount_kobo
                b["statuses"].append(RUN_STATUS.get(r.status, r.status))
                continue
            events.append({"plan_id": r.plan_id, "at": r.scheduled_for, "amount_kobo": r.amount_kobo, "status": RUN_STATUS.get(r.status, r.status)})
        for b in batches.values():
            st = b.pop("statuses")
            b["status"] = "sending" if "sending" in st else ("sent" if "sent" in st else st[0])
            events.append(b)
        if months_away == 0:
            events += [event_json(e) for e in user_forecast(user, now).events]
        elif months_away > 0:
            sched_fees = fee_schedule()
            for p in engine_plans(user):
                if p.status == "active":
                    amount, fee = p.cost_parts(sched_fees)
                    events += [{"plan_id": int(p.id), "at": at, "amount_kobo": amount, "fee_kobo": fee,
                                "rank": p.priority_rank, "status": "scheduled"}
                               for at in occurrences(p.schedule, start, end)]
        events.sort(key=lambda e: e["at"])
        return Response({"month": f"{y:04d}-{m:02d}", "events": events,
                         "total_kobo": sum(e["amount_kobo"] + e.get("fee_kobo", 0) for e in events)})


class Activity(APIView):
    def get(self, request):
        user = request.user
        from django.db.models import Q
        now = timezone.now()
        # Future runs stay out, except a group payout that's due now (e.g. just sent again): it shows as sending straight away.
        runs = (Run.objects.filter(user=user).exclude(status=Run.Status.CANCELLED)
                .exclude(Q(status=Run.Status.SCHEDULED) & (Q(batch__isnull=True) | Q(batch__scheduled_for__gt=now)))
                .select_related("plan", "plan__recipient", "line__recipient", "batch", "batch__retry").order_by("-scheduled_for")[:300])
        runs = list(runs)
        wa = {m.run_id: m for m in OutboxMessage.objects.filter(user=user, channel=OutboxMessage.Channel.WHATSAPP, run_id__in=[r.id for r in runs])}
        items, groups = [], {}
        for r in runs:
            rec = r.recipient
            if r.batch_id:  # a group payout is one row that opens to show each person
                g = groups.get(r.batch_id)
                if not g:
                    b = r.batch
                    g = groups[r.batch_id] = {
                        "kind": "group", "id": str(b.pk), "batch_status": b.status, "at": b.completed_at or b.scheduled_for,
                        "retried": hasattr(b, "retry"), "is_retry": b.retry_of_id is not None,  # retry is the reverse side
                        "amount_kobo": 0, "fee_kobo": 0, "reason": b.reason if b.status in (RunBatch.Status.SKIPPED, RunBatch.Status.WAITING) else "",
                        "plan": {"id": r.plan_id, "label": r.plan.label, "emoji": r.plan.emoji, "tint": r.plan.tint}, "people": []}
                    items.append(g)
                st = "sending" if r.status == Run.Status.SCHEDULED else RUN_STATUS.get(r.status, r.status)
                g["people"].append({"label": rec.label, "bank_name": rec.bank_name, "account_last4": rec.account_number[-4:],
                                    "amount_kobo": r.amount_kobo, "status": st, "position": r.line.position if r.line_id else 0})
                if r.status == Run.Status.SUCCESSFUL or r.status in Run.IN_FLIGHT:
                    g["amount_kobo"] += r.amount_kobo
                    g["fee_kobo"] += r.fee_kobo
                continue
            items.append({
                "kind": "run", "status": RUN_STATUS.get(r.status, r.status), "at": r.completed_at or r.scheduled_for,
                "amount_kobo": r.amount_kobo, "fee_kobo": r.fee_kobo, "fee_lines": r.fee_parts.lines(), "reason": r.last_error if r.status.startswith("skipped") else "",
                "plan": {"id": r.plan_id, "label": r.plan.label, "emoji": r.plan.emoji, "tint": r.plan.tint},
                "recipient": {"label": rec.label, "bank_name": rec.bank_name, "account_last4": rec.account_number[-4:]},
                "whatsapp": {"to": rec.label, "body": wa[r.id].body, "status": wa[r.id].status} if r.id in wa else None,
            })
        for g in groups.values():
            g["people"].sort(key=lambda p: p["position"])
            sts = [p["status"] for p in g["people"]]
            g["paid"] = sts.count("sent")
            g["status"] = ("sending" if "sending" in sts else "sent" if g["paid"] == len(sts) else
                           "partial" if g["paid"] else sts[0])
        for i in Inflow.objects.filter(user=user, status=Inflow.Status.CREDITED).order_by("-created_at")[:50]:
            items.append({"kind": "inflow", "status": "received", "at": i.credited_at or i.created_at, "amount_kobo": i.amount_kobo,
                          "sender": i.sender_name})
        items.sort(key=lambda x: x["at"], reverse=True)
        return Response(items[:100])


class PayoutRetry(APIView):
    """Send a failed or skipped group payout again, to the people who weren't paid. Goes out on the next worker tick."""

    MESSAGES = {
        "still_going": "This payout is still going out. Give it a minute.",
        "already_retried": "This payout has already been sent again. Check the newer one in Activity.",
        "plan_deleted": "That plan has been deleted.",
        "nobody_unpaid": "Everyone on this payout was paid.",
    }

    def post(self, request, pk):
        batch = RunBatch.objects.filter(pk=pk, user=request.user).first()
        if not batch:
            raise FlowError("That payout doesn't exist.", status=404)
        acc.require_verified(request.user)
        try:
            new = retry_batch(batch)
        except ValueError as e:
            raise FlowError(self.MESSAGES.get(str(e), "This payout can't be sent again."), code=str(e), status=409)
        return Response({"id": str(new.pk), "people": new.runs.count(), "amount_kobo": new.amount_kobo, "fee_kobo": new.fee_kobo}, status=201)


# ------------------------------------------------------------------ card top-ups and saved cards

from ledger import cards  # noqa: E402
from ledger.models import CardCharge, SavedCard  # noqa: E402
from providers import get_card_gateway  # noqa: E402


def card_json(c: SavedCard) -> dict:
    return {"id": c.id, "brand": c.brand or "card", "last4": c.last4, "bank": c.bank, "exp": f"{c.exp_month}/{c.exp_year[-2:]}" if c.exp_month else "",
            "last_used_at": c.last_used_at}


def charge_json(c: CardCharge, user) -> dict:
    return {"reference": c.reference, "status": c.status, "message": c.message, "net_kobo": c.net_kobo, "fee_kobo": c.fee_kobo,
            "gross_kobo": c.gross_kobo, "card": card_json(c.card) if c.card_id and c.card.active else None,
            "available_kobo": ledger.balance(user).available_kobo}


def _amount(request) -> int:
    try:
        return int(request.data.get("amount_kobo") if request.method != "GET" else request.query_params.get("amount_kobo"))
    except (TypeError, ValueError):
        raise FlowError("Enter an amount.")


class CardQuote(APIView):
    """What a card top-up of this amount costs, before paying."""

    def get(self, request):
        g = get_card_gateway()
        q = cards.quote(_amount(request))
        return Response({"available": g is not None, "test_mode": bool(g and g.test_mode), "net_kobo": q.net_kobo,
                         "fee_kobo": q.fee_kobo, "gross_kobo": q.gross_kobo, "payer_covers_fee": q.payer_covers_fee})


def check_balance_limit(user, adding_kobo: int) -> None:
    lim = acc.limits(user)
    if not lim:
        return
    room = lim["max_balance_kobo"] - ledger.balance(user).total_kobo
    if adding_kobo > room:
        from engine import format_naira
        raise FlowError(f"Your account can hold up to {format_naira(lim['max_balance_kobo'])} for now. "
                        + (f"You can add up to {format_naira(max(room, 0))}." if room > 0 else "Let some drips go out first."),
                        code="over_limit")


class CardStart(APIView):
    def post(self, request):
        acc.require_verified(request.user)
        check_balance_limit(request.user, _amount(request))
        return Response(cards.start(request.user, _amount(request), save_card=bool(request.data.get("save_card", True))))


class CardVerify(APIView):
    """The app calls this when Paystack sends the person back with ?reference=."""

    def post(self, request):
        ref = str(request.data.get("reference", ""))
        charge = CardCharge.objects.filter(reference=ref, user=request.user).first()
        if not charge:
            raise FlowError("We couldn't find that payment.", status=404)
        if charge.status == CardCharge.Status.STARTED:
            charge = cards.complete(ref)
        return Response(charge_json(charge, request.user))


class SavedCardTopUp(APIView):
    """One-tap top-up with a saved card."""

    def post(self, request):
        acc.require_verified(request.user)
        check_balance_limit(request.user, _amount(request))
        card = request.user.cards.filter(pk=request.data.get("card_id"), active=True).first()
        if not card:
            raise FlowError("That card isn't saved any more.", status=404)
        charge = cards.charge_saved_card(request.user, card, _amount(request))
        return Response(charge_json(charge, request.user))


class Cards(APIView):
    def get(self, request):
        return Response([card_json(c) for c in request.user.cards.filter(active=True).order_by("-last_used_at", "-created_at")])


class CardDetail(APIView):
    def delete(self, request, pk):
        card = request.user.cards.filter(pk=pk, active=True).first()
        if not card:
            raise FlowError("That card isn't saved any more.", status=404)
        cards.remove_card(card)
        return Response(status=204)
