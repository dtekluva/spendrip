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
from drips.models import Plan, Recipient, Run
from drips.services import engine_plans, fee_kobo, reschedule, sent_today_kobo, user_forecast
from engine import PlanLike, Schedule, forecast, next_occurrences, occurrences, set_priority, validate_schedule
from ledger import services as ledger
from ledger.models import Inflow
from notifications.models import OutboxMessage
from providers import get_payout_provider

from providers.banks import BANKS, BY_NIP

TINTS = {"cobalt", "sun", "hibiscus", "mint"}
MIN_AMOUNT_KOBO, MAX_AMOUNT_KOBO = 10_000, 1_000_000_000  # ₦100 – ₦10m


# ------------------------------------------------------------------ helpers

def event_json(e) -> dict:
    return {"plan_id": int(e.plan_id) if str(e.plan_id).isdigit() else e.plan_id, "at": e.at, "amount_kobo": e.amount_kobo,
            "fee_kobo": e.fee_kobo, "rank": e.rank, "status": e.status}


def forecast_json(f) -> dict:
    return {"window_end": f.window_end, "protected_kobo": f.protected_kobo, "free_kobo": f.free_kobo,
            "total_needed_kobo": f.total_needed_kobo, "top_up_kobo": f.top_up_kobo,
            "priority_shortfall_kobo": f.priority_shortfall_kobo, "events": [event_json(e) for e in f.events]}


def recipient_json(r: Recipient) -> dict:
    return {"id": r.id, "label": r.label, "is_self": r.is_self, "bank_name": r.bank_name, "nip_bank_code": r.nip_bank_code,
            "account_last4": r.account_number[-4:], "verified_account_name": r.verified_account_name,
            "whatsapp": r.whatsapp, "notify_whatsapp": r.notify_whatsapp}


def plan_json(p: Plan, now: datetime) -> dict:
    nxt = next_occurrences(p.schedule, now, 1) if p.status == Plan.Status.ACTIVE else []
    return {"id": p.id, "label": p.label, "emoji": p.emoji, "tint": p.tint, "amount_kobo": p.amount_kobo,
            "recipient": recipient_json(p.recipient), "frequency": p.frequency, "weekday": p.weekday, "month_day": p.month_day,
            "month_day_last": p.month_day_last, "time_local": p.time_local, "tz": p.tz, "starts_at": p.starts_at,
            "ends_at": p.ends_at, "status": p.status, "priority_rank": p.priority_rank, "next_at": nxt[0] if nxt else None}


def user_plans(user):
    return Plan.objects.filter(user=user).exclude(status=Plan.Status.DELETED).select_related("recipient").order_by("created_at")


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
    try:
        amount = int(data.get("amount_kobo", cur("amount_kobo", 0)))
    except (TypeError, ValueError):
        raise FlowError("Enter an amount.")
    if not MIN_AMOUNT_KOBO <= amount <= MAX_AMOUNT_KOBO:
        raise FlowError("Amounts must be between ₦100 and ₦10,000,000.")
    out["amount_kobo"] = amount
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
    out["starts_at"] = _dt(data.get("starts_at")) or cur("starts_at") or timezone.now()
    out["ends_at"] = _dt(data.get("ends_at")) if "ends_at" in data else cur("ends_at")
    sched = Schedule(frequency=out["frequency"], time_local=out["time_local"], tz=out["tz"], starts_at=out["starts_at"],
                     weekday=out["weekday"], month_day="last" if out["month_day_last"] else out["month_day"], ends_at=out["ends_at"])
    errors = validate_schedule(sched)
    if errors:
        raise FlowError(errors[0][0].upper() + errors[0][1:] + ".")
    return out


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
            "fee_kobo": fee_kobo(),
            "paused_all": user.paused_all,
            "funding_account": {"account_number": fa.account_number, "bank_name": fa.bank_name, "account_name": fa.account_name} if fa else None,
        })


# ------------------------------------------------------------------ banks and recipients

class Banks(APIView):
    def get(self, request):
        return Response([{"name": n, "nip_code": nip} for n, nip, _ in BANKS])


class RecipientLookup(APIView):
    """Check an account before saving it, so money can't go to the wrong person."""

    def post(self, request):
        code, number = str(request.data.get("nip_bank_code", "")), str(request.data.get("account_number", ""))
        if code not in BY_NIP:
            raise FlowError("Choose a bank.")
        if not (len(number) == 10 and number.isdigit()):
            raise FlowError("Account numbers have 10 digits.")
        try:
            r = get_payout_provider().name_enquiry(code, number)
        except ValueError as e:
            raise FlowError(str(e), code="lookup_failed")
        return Response({"account_name": r.account_name, "bank_name": BY_NIP[code][0]})


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
        name = get_payout_provider().name_enquiry(code, number).account_name  # always check server-side
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
        using = list(r.plans.exclude(status=Plan.Status.DELETED).values_list("label", flat=True))
        if using:
            raise FlowError(f"{', '.join(using)} still pays this person. Change or delete those plans first.", code="in_use", status=409)
        if r.plans.exists():
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
        rank = int(request.data.get("priority_rank") or 0)
        with transaction.atomic():
            plan = Plan.objects.create(user=request.user, **fields)
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
            if "status" in d:
                if d["status"] not in (Plan.Status.ACTIVE, Plan.Status.PAUSED):
                    raise FlowError("Status must be active or paused.")
                plan.status = d["status"]
            schedule_keys = {"label", "emoji", "tint", "amount_kobo", "recipient_id", "frequency", "weekday", "month_day",
                             "month_day_last", "time_local", "starts_at", "ends_at"}
            if schedule_keys & set(d):
                for k, v in parse_plan(d, request.user, instance=plan).items():
                    setattr(plan, k, v)
            plan.save()
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
        return Response(status=204)


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
        draft = PlanLike(id=draft_id, amount_kobo=fields["amount_kobo"], schedule=sched, priority_rank=ranks.get(draft_id),
                         order=editing.pk if editing else 10**9)
        after = [replace(p, priority_rank=ranks.get(p.id)) for p in others] + [draft]

        bal = ledger.balance(user).available_kobo
        kw = dict(fee_kobo=fee_kobo(), tz=user.tz, daily_cap_kobo=user.daily_cap_kobo, sent_today_kobo=sent_today_kobo(user, now))
        f0, f1 = forecast(before, bal, now, **kw), forecast(after, bal, now, **kw)
        mine = [e for e in f1.events if e.plan_id == draft_id]
        labels = {str(p.pk): p.label for p in user_plans(user)}
        return Response({
            "next_dates": next_occurrences(sched, now, 5),
            "runs_this_month": len(mine),
            "month_cost_kobo": sum(e.cost_kobo for e in mine),
            "fee_kobo": fee_kobo(),
            "top_up_before_kobo": f0.top_up_kobo,
            "top_up_after_kobo": f1.top_up_kobo,
            "draft_waiting": sum(1 for e in mine if e.status in ("wait", "short", "cap")),
            "priorities_short_after_kobo": f1.priority_shortfall_kobo,
            "priority_order": [labels.get(pid, fields["label"]) for pid in order],
            "dropped_priorities": [labels.get(pid, pid) for pid in dropped],
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

        events = []
        for r in Run.objects.filter(user=user, scheduled_for__gte=start, scheduled_for__lte=min(end, now)).exclude(status=Run.Status.SCHEDULED):
            events.append({"plan_id": r.plan_id, "at": r.scheduled_for, "amount_kobo": r.amount_kobo, "status": RUN_STATUS.get(r.status, r.status)})
        if months_away == 0:
            events += [event_json(e) for e in user_forecast(user, now).events]
        elif months_away > 0:
            for p in engine_plans(user):
                if p.status == "active":
                    events += [{"plan_id": int(p.id), "at": at, "amount_kobo": p.amount_kobo, "rank": p.priority_rank, "status": "scheduled"}
                               for at in occurrences(p.schedule, start, end)]
        events.sort(key=lambda e: e["at"])
        return Response({"month": f"{y:04d}-{m:02d}", "events": events,
                         "total_kobo": sum(e["amount_kobo"] for e in events) + fee_kobo() * len(events)})


class Activity(APIView):
    def get(self, request):
        user = request.user
        runs = (Run.objects.filter(user=user).exclude(status__in=[Run.Status.SCHEDULED, Run.Status.CANCELLED])
                .select_related("plan", "plan__recipient").order_by("-scheduled_for")[:100])
        runs = list(runs)
        wa = {m.run_id: m for m in OutboxMessage.objects.filter(user=user, channel=OutboxMessage.Channel.WHATSAPP, run_id__in=[r.id for r in runs])}
        items = []
        for r in runs:
            rec = r.plan.recipient
            items.append({
                "kind": "run", "status": RUN_STATUS.get(r.status, r.status), "at": r.completed_at or r.scheduled_for,
                "amount_kobo": r.amount_kobo, "fee_kobo": r.fee_kobo, "reason": r.last_error if r.status.startswith("skipped") else "",
                "plan": {"id": r.plan_id, "label": r.plan.label, "emoji": r.plan.emoji, "tint": r.plan.tint},
                "recipient": {"label": rec.label, "bank_name": rec.bank_name, "account_last4": rec.account_number[-4:]},
                "whatsapp": {"to": rec.label, "body": wa[r.id].body, "status": wa[r.id].status} if r.id in wa else None,
            })
        for i in Inflow.objects.filter(user=user, status=Inflow.Status.CREDITED).order_by("-created_at")[:50]:
            items.append({"kind": "inflow", "status": "received", "at": i.credited_at or i.created_at, "amount_kobo": i.amount_kobo,
                          "sender": i.sender_name})
        items.sort(key=lambda x: x["at"], reverse=True)
        return Response(items[:100])


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


class CardStart(APIView):
    def post(self, request):
        acc.require_verified(request.user)
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
