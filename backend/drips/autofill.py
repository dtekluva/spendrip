"""
Auto-fill: top up the person's balance from their saved card, so drips don't wait for money.

1. Payday fill. On a chosen window (the last 5 days of the month and/or the 1st to the 5th), one charge for what the
   drips need until the next window. A heads-up goes out first (from 7 AM); the charge follows at least two hours
   later and not before 10 AM. A declined card is tried again the next day, at most 3 times per window.
2. Just-in-time fill. A drip due within 24 hours that the balance can't cover: one charge for the shortfall. If it's
   declined, there's no second try; the day-ahead reminder goes out and says the card was declined.

Called from the worker's reminder loop, before the reminders, so a fill that works stops the low-balance email.
Every charge goes through ledger.cards.charge_saved_card(), so fees, the ledger and receipts work as for one-tap top-ups.
See docs/plans/auto-fill.md.
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import ceil
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from accounts import services as acc
from engine import format_naira as N
from engine.protection import SHORT, WAIT, _events, forecast
from ledger import cards
from ledger import services as ledger
from ledger.models import CardCharge, SavedCard
from notifications.models import OutboxMessage
from notifications.services import notify

from .models import AutoFill, AutoFillAttempt, Plan, RunBatch
from .services import engine_plans, fee_schedule, sent_today_kobo

log = logging.getLogger(__name__)

WINDOW_DAYS = 5
HEADS_UP_HOUR = 7
CHARGE_HOUR = 10
LAST_HOUR = 20  # no charges or heads-ups from 8 PM
HEADS_UP_LEAD = timedelta(hours=2)
MAX_PAYDAY_TRIES = 3
MAX_FAILED_WINDOWS = 2
MAX_JIT_FAILS_A_MONTH = 3
LOOKAHEAD = timedelta(hours=24)
ROUND_KOBO = 50_000  # fills are rounded up to ₦500
JIT_MIN_KOBO = 100_000  # ₦1,000
MIN_CHARGE_KOBO = 10_000  # ₦100, the smallest card top-up
DEFAULT_MAX_CHARGE_KOBO = 50_000_000  # ₦500,000

PAUSE_REASONS = {
    "card_removed": "the card was removed",
    "card_expired": "the card has expired",
    "card_needs_otp": "your bank asks for a code on every charge, so this card can't be charged automatically",
    "declines": "your card was declined several times in a row",
}


# ---------------------------------------------------------------- windows

def _tz(user) -> ZoneInfo:
    return ZoneInfo(user.tz or "Africa/Lagos")


def window_key(d: date, af: AutoFill) -> str | None:
    """The payday window `d` falls in, if that window is switched on: "2026-10-end" or "2026-11-start"."""
    last = calendar.monthrange(d.year, d.month)[1]
    if af.payday_end and d.day > last - WINDOW_DAYS:
        return f"{d:%Y-%m}-end"
    if af.payday_start and d.day <= WINDOW_DAYS:
        return f"{d:%Y-%m}-start"
    return None


def next_window_start(local: datetime, af: AutoFill, *, after_current: bool = True) -> datetime | None:
    """10 AM on the first day of the next payday window (after the one `local` is in, if `after_current`)."""
    current = window_key(local.date(), af) if after_current else None
    d = local.date() if not after_current else local.date() + timedelta(days=1)
    for _ in range(70):
        k = window_key(d, af)
        if k and k != current:
            return datetime(d.year, d.month, d.day, CHARGE_HOUR, tzinfo=local.tzinfo)
        d += timedelta(days=1)
    return None


# ---------------------------------------------------------------- amounts

def _owed(user, now: datetime) -> int:
    """Group payouts already due and waiting for money."""
    waiting = RunBatch.objects.filter(user=user, status__in=[RunBatch.Status.SCHEDULED, RunBatch.Status.WAITING], scheduled_for__lte=now)
    return sum(b.cost_kobo for b in waiting)


def payday_need(user, now: datetime, until: datetime) -> int:
    """What the drips need from now until `until`, fees included, minus what's in the balance."""
    cost = sum(e.cost_kobo for e in _events(engine_plans(user), now, until, fee_schedule()))
    return max(0, cost + _owed(user, now) - ledger.balance(user).available_kobo)


@dataclass
class Shortfall:
    amount_kobo: int
    keys: list[str]  # the drips (plan id + time) and waiting group payouts it covers


def jit_shortfall(user, now: datetime) -> Shortfall:
    """The smallest top-up that lets every drip due in the next 24 hours go out (the daily cap aside)."""
    plans, fees, avail, owed = engine_plans(user), fee_schedule(), ledger.balance(user).available_kobo, _owed(user, now)
    horizon = now + LOOKAHEAD

    def blocked(extra: int) -> list:
        f = forecast(plans, avail - owed + extra, now, fee_kobo=fees, tz=user.tz, daily_cap_kobo=user.daily_cap_kobo,
                     sent_today_kobo=sent_today_kobo(user, now))
        return [e for e in f.events if e.status in (WAIT, SHORT) and e.at <= horizon]

    first = blocked(0)
    keys = [f"{e.plan_id}:{e.at.isoformat()}" for e in first]
    keys += [f"batch:{b.pk}" for b in RunBatch.objects.filter(user=user, status__in=[RunBatch.Status.SCHEDULED, RunBatch.Status.WAITING],
                                                               scheduled_for__lte=now)] if owed > avail else []
    lo, hi = 0, 0
    if first:
        hi = sum(e.cost_kobo for e in _events(plans, now, horizon + timedelta(days=31), fees)) + owed + 100
        while lo < hi:  # smallest extra that unblocks everything in the next 24 hours
            mid = (lo + hi) // 2
            if blocked(mid):
                lo = mid + 1
            else:
                hi = mid
    return Shortfall(max(lo, owed - avail, 0), keys)


def _round_up(kobo: int) -> int:
    return ceil(kobo / ROUND_KOBO) * ROUND_KOBO


def month_used(user, now: datetime) -> int:
    local = now.astimezone(_tz(user))
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return AutoFillAttempt.objects.filter(user=user, status=AutoFillAttempt.Status.SUCCESS, at__gte=start).exclude(charge=None) \
        .values("charge").distinct().aggregate(s=Sum("charge__net_kobo"))["s"] or 0


def clamp(af: AutoFill, want: int, now: datetime) -> tuple[int, str]:
    """(amount, why it was cut) within the person's limits and the balance limit."""
    amount, why = want, ""
    if amount > af.max_per_charge_kobo:
        amount, why = af.max_per_charge_kobo, "per_charge"
    room = af.max_per_month_kobo - month_used(af.user, now)
    if amount > room:
        amount, why = room, "per_month"
    lim = acc.limits(af.user)
    if lim:
        room = lim["max_balance_kobo"] - ledger.balance(af.user).total_kobo
        if amount > room:
            amount, why = room, "balance_limit"
    return max(amount, 0), why


# ---------------------------------------------------------------- the run

def run(now: datetime | None = None) -> dict:
    now = now or timezone.now()
    done = {"payday": 0, "jit": 0}
    if not settings.AUTOFILL_ENABLED:
        return done
    for af in AutoFill.objects.filter(active=True, paused_reason="").select_related("user", "card"):
        try:
            if not _ready(af, now):
                continue
            done["payday"] += payday(af, now)
            done["jit"] += just_in_time(af, now)
        except Exception:  # one person's problem must never stop the others
            log.exception("auto-fill failed for user %s", af.user_id)
    return done


def _ready(af: AutoFill, now: datetime) -> bool:
    u = af.user
    if not u.is_verified or u.paused_all:
        return False
    if not af.card or not af.card.active:
        pause(af, "card_removed")
        return False
    if card_expired(af.card, now.astimezone(_tz(u)).date()):
        pause(af, "card_expired")
        return False
    return Plan.objects.filter(user=u, status=Plan.Status.ACTIVE).exists()


def card_expired(card: SavedCard, today: date) -> bool:
    try:
        y, m = int(card.exp_year), int(card.exp_month)
    except (TypeError, ValueError):
        return False
    return (y, m) < (today.year, today.month)


def _charge(af: AutoFill, amount: int) -> CardCharge:
    return cards.charge_saved_card(af.user, af.card, amount, source="autofill")


def _card(af: AutoFill) -> str:
    return f"{(af.card.brand or 'card').title()} ••{af.card.last4}"


def _app(path: str = "") -> str:
    return settings.SPENDRIP["PUBLIC_APP_URL"].rstrip("/") + path


def _day(dt: datetime) -> str:
    return f"{dt:%a} {dt.day} {dt:%b}"


# ---------------------------------------------------------------- 1. payday fill

def payday(af: AutoFill, now: datetime) -> int:
    u, local = af.user, now.astimezone(_tz(af.user))
    key = window_key(local.date(), af)
    if not key or af.skip_window == key or not HEADS_UP_HOUR <= local.hour < LAST_HOUR:
        return 0
    tries = list(AutoFillAttempt.objects.filter(user=u, kind=AutoFillAttempt.Kind.PAYDAY, key=key))
    if any(t.status != AutoFillAttempt.Status.FAILED for t in tries) or len(tries) >= MAX_PAYDAY_TRIES:
        return 0
    if any(t.at.astimezone(local.tzinfo).date() == local.date() for t in tries):
        return 0  # one try a day
    until = next_window_start(local, af)
    need = _round_up(payday_need(u, now, until))
    heads_up = af.heads_up_at if af.heads_up_window == key else None

    if need < MIN_CHARGE_KOBO:
        if not tries:
            AutoFillAttempt.objects.create(user=u, kind=AutoFillAttempt.Kind.PAYDAY, key=key, status=AutoFillAttempt.Status.NOT_NEEDED, at=now)
        return 0
    amount, why = clamp(af, need, now)
    if not heads_up:
        if amount >= MIN_CHARGE_KOBO:
            _heads_up(af, key, amount, until, local)
            af.heads_up_window, af.heads_up_at = key, now
            af.save(update_fields=["heads_up_window", "heads_up_at", "updated_at"])
        return 0
    if local.hour < CHARGE_HOUR or now < heads_up + HEADS_UP_LEAD:
        return 0
    if amount < MIN_CHARGE_KOBO:
        _record(af, now, AutoFillAttempt.Kind.PAYDAY, [key], len(tries) + 1, 0, None, AutoFillAttempt.Status.FAILED, f"limit:{why}")
        _limit_reached(af, key, why)
        return 0

    charge = _charge(af, amount)
    ok = charge.status == CardCharge.Status.SUCCESS
    _record(af, now, AutoFillAttempt.Kind.PAYDAY, [key], len(tries) + 1, amount, charge,
            AutoFillAttempt.Status.SUCCESS if ok else AutoFillAttempt.Status.FAILED, charge.message)
    if ok:
        if af.failed_windows:
            af.failed_windows = 0
            af.save(update_fields=["failed_windows", "updated_at"])
        _payday_done(af, key, charge, until, partial=why)
        return 1
    if charge.message == cards.NEEDS_CARDHOLDER:
        pause(af, "card_needs_otp")
        return 0
    last_try = len(tries) + 1 >= MAX_PAYDAY_TRIES or window_key(local.date() + timedelta(days=1), af) != key
    _payday_declined(af, key, charge, last_try)
    if last_try:
        af.failed_windows += 1
        af.save(update_fields=["failed_windows", "updated_at"])
        if af.failed_windows >= MAX_FAILED_WINDOWS:
            pause(af, "declines")
    return 0


def _record(af, now, kind, keys, attempt, amount, charge, status, reason=""):
    for k in keys:
        AutoFillAttempt.objects.get_or_create(user=af.user, kind=kind, key=k[:80], attempt=attempt,
                                              defaults={"amount_kobo": amount, "charge": charge, "status": status, "reason": reason[:200], "at": now})


def _send(af: AutoFill, key: str, template: str, body: str, *, email: dict | None = None, push: bool = True) -> None:
    u = af.user
    notify(u, key=f"{key}:in_app", channel=OutboxMessage.Channel.IN_APP, template=template, body=body)
    if push:
        notify(u, key=f"{key}:push", channel=OutboxMessage.Channel.PUSH, template=template, body=body)
    if email and u.email and u.notify_email:
        notify(u, key=f"{key}:email", channel=OutboxMessage.Channel.EMAIL, template=template, to=u.email, body=body, email=email)


def _heads_up(af: AutoFill, key: str, amount: int, until: datetime, local: datetime) -> None:
    fee = cards.quote(amount).fee_kobo
    at = max(local + HEADS_UP_LEAD, local.replace(hour=CHARGE_HOUR, minute=0, second=0, microsecond=0))
    when = f"at {at:%-I:%M %p}".replace("AM", "am").replace("PM", "pm")
    body = f"Auto-fill will add {N(amount)} {when} from {_card(af)}, for your drips until {_day(until)}. Card fee {N(fee)}."
    _send(af, f"autofill:{af.user.pk}:{key}:heads_up", "autofill_heads_up", body, email={
        "subject": f"⛽ Auto-fill will add {N(amount)} today", "heading": f"Auto-fill will add {N(amount)} today",
        "paragraphs": [f"{when.capitalize()} we'll charge {_card(af)} {N(amount)} plus the {N(fee)} card fee.",
                       f"That covers everything your drips need until {_day(until)}, the next payday window.",
                       "Not a good day? Skip this payday in the app and top up when you're ready."],
        "button": ("Skip or change", _app("/autofill"))})


def _payday_done(af, key, charge, until, partial: str) -> None:
    extra = {"per_charge": " Your limit per charge stopped it covering everything, so some drips may still need a top-up.",
             "per_month": " It reached your monthly Auto-fill limit, so some drips may still need a top-up.",
             "balance_limit": " Your balance limit stopped it covering everything."}.get(partial, "")
    body = f"Auto-fill added {N(charge.net_kobo)} from {_card(af)}." + (f" Everything until {_day(until)} is covered." if not partial else extra)
    _send(af, f"autofill:{af.user.pk}:{key}:done", "autofill_done", body, email={
        "subject": f"✅ Auto-fill added {N(charge.net_kobo)}", "heading": f"{N(charge.net_kobo)} added to your balance",
        "paragraphs": [f"We charged {_card(af)} {N(charge.gross_kobo)}: {N(charge.net_kobo)} for your drips and {N(charge.fee_kobo)} card fee.",
                       (f"Everything due until {_day(until)} is covered." if not partial else extra.strip())],
        "button": ("Open SpenDrip", _app())})


def _payday_declined(af, key, charge, last_try: bool) -> None:
    reason = charge.message or "declined"
    if last_try:
        body = f"Auto-fill couldn't add money this payday: {_card(af)} was declined ({reason}). Top up by hand so your drips go out."
        _send(af, f"autofill:{af.user.pk}:{key}:failed", "autofill_window_failed", body, email={
            "subject": "⚠️ Auto-fill couldn't top up this payday", "heading": "Auto-fill couldn't top up this payday",
            "paragraphs": [f"{_card(af)} was declined ({reason}), and this payday window is over.",
                           "Top up by hand, or use another card, so your drips go out on time."],
            "button": ("Add money", _app("/fund"))})
    else:
        tries = AutoFillAttempt.objects.filter(user=af.user, kind=AutoFillAttempt.Kind.PAYDAY, key=key).count()
        body = f"{_card(af)} was declined ({reason}). Auto-fill will try again tomorrow at 10 am, or tap Fill now once you've been paid."
        _send(af, f"autofill:{af.user.pk}:{key}:declined:{tries}", "autofill_declined", body)


def _limit_reached(af, key, why) -> None:
    what = {"per_month": "your monthly Auto-fill limit", "per_charge": "your limit per charge",
            "balance_limit": "your balance limit"}.get(why, "a limit")
    _send(af, f"autofill:{af.user.pk}:{key}:limit", "autofill_limit",
          f"Auto-fill didn't top up this payday because it reached {what}. Raise it in Auto-fill, or top up by hand.")


# ---------------------------------------------------------------- 2. just in time

def just_in_time(af: AutoFill, now: datetime) -> int:
    if not af.just_in_time:
        return 0
    u, local = af.user, now.astimezone(_tz(af.user))
    if not HEADS_UP_HOUR <= local.hour < LAST_HOUR:
        return 0
    s = jit_shortfall(u, now)
    tried = set(AutoFillAttempt.objects.filter(user=u, kind=AutoFillAttempt.Kind.JUST_IN_TIME, key__in=[k[:80] for k in s.keys])
                .values_list("key", flat=True))
    fresh = [k for k in s.keys if k[:80] not in tried]
    if not s.amount_kobo or not fresh:
        return 0  # nothing short, or Auto-fill already had its one try for these drips
    amount, why = clamp(af, max(_round_up(s.amount_kobo), JIT_MIN_KOBO), now)
    if amount < MIN_CHARGE_KOBO:
        _record(af, now, AutoFillAttempt.Kind.JUST_IN_TIME, fresh, 1, 0, None, AutoFillAttempt.Status.FAILED, f"limit:{why}")
        return 0
    charge = _charge(af, amount)
    ok = charge.status == CardCharge.Status.SUCCESS
    _record(af, now, AutoFillAttempt.Kind.JUST_IN_TIME, fresh, 1, amount, charge,
            AutoFillAttempt.Status.SUCCESS if ok else AutoFillAttempt.Status.FAILED, charge.message)
    if ok:
        notify(u, key=f"autofill:{u.pk}:jit:{charge.reference}:in_app", channel=OutboxMessage.Channel.IN_APP, template="autofill_jit",
               body=f"Auto-fill added {N(charge.net_kobo)} from {_card(af)} so your next drip goes out on time.")
        return 1
    if charge.message == cards.NEEDS_CARDHOLDER:
        pause(af, "card_needs_otp")
    elif _jit_fails_this_month(af, now) >= MAX_JIT_FAILS_A_MONTH:
        pause(af, "declines")
    return 0  # the day-ahead reminder tells them, with declined_note()


def _jit_fails_this_month(af, now) -> int:
    local = now.astimezone(_tz(af.user))
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (AutoFillAttempt.objects.filter(user=af.user, kind=AutoFillAttempt.Kind.JUST_IN_TIME, status=AutoFillAttempt.Status.FAILED,
                                           at__gte=start).exclude(charge=None).values("charge").distinct().count())


def declined_note(user, plan_id: str, at: datetime) -> str | None:
    """For the day-ahead reminder: Auto-fill tried the card for this drip and it was declined."""
    a = (AutoFillAttempt.objects.filter(user=user, kind=AutoFillAttempt.Kind.JUST_IN_TIME, key=f"{plan_id}:{at.isoformat()}"[:80],
                                        status=AutoFillAttempt.Status.FAILED).exclude(charge=None).select_related("charge__card").first())
    if not a:
        return None
    card = a.charge.card
    return f"Auto-fill tried to top up from {(card.brand or 'card').title()} ••{card.last4} but it was declined ({a.reason or 'declined'})." if card else None


# ---------------------------------------------------------------- pausing

def pause(af: AutoFill, reason: str) -> None:
    if af.paused_reason == reason:
        return
    af.paused_reason = reason
    af.save(update_fields=["paused_reason", "updated_at"])
    why = PAUSE_REASONS.get(reason, reason)
    _send(af, f"autofill:{af.user.pk}:paused:{reason}:{timezone.now():%Y%m%d}", "autofill_paused",
          f"Auto-fill is paused: {why}. Choose a card in Auto-fill to turn it back on.", email={
              "subject": "⏸️ Auto-fill is paused", "heading": "Auto-fill is paused",
              "paragraphs": [f"We've stopped automatic top-ups because {why}.",
                             "Nothing else changes: your drips still go out from your balance. Pick a card in Auto-fill to turn it back on."],
              "button": ("Open Auto-fill", _app("/autofill"))})


def card_gone(card: SavedCard, reason: str) -> None:
    for af in AutoFill.objects.filter(card=card, active=True).select_related("user", "card"):
        pause(af, reason)


# ---------------------------------------------------------------- for the app

def suggested_limits(user, now: datetime | None = None) -> dict:
    now = now or timezone.now()
    local = now.astimezone(_tz(user))
    probe = AutoFill(payday_end=True)
    until = next_window_start(local, probe) or now + timedelta(days=31)
    month = sum(e.cost_kobo for e in _events(engine_plans(user), now, until, fee_schedule()))
    per_charge = min(max(_round_up(month), 5_000_000), DEFAULT_MAX_CHARGE_KOBO)
    return {"month_need_kobo": month, "max_per_charge_kobo": per_charge, "max_per_month_kobo": _round_up(int(month * 1.5)) or per_charge}


def next_fill(af: AutoFill, now: datetime | None = None) -> dict | None:
    """When the next payday fill happens and roughly how much, for the Auto-fill screen."""
    now = now or timezone.now()
    if not af.active or af.paused_reason or not (af.payday_end or af.payday_start):
        return None
    local = now.astimezone(_tz(af.user))
    key = window_key(local.date(), af)
    done = key and (af.skip_window == key or AutoFillAttempt.objects.filter(
        user=af.user, kind=AutoFillAttempt.Kind.PAYDAY, key=key).exclude(status=AutoFillAttempt.Status.FAILED).exists())
    if key and not done and local.hour < LAST_HOUR:
        at = max(local.replace(hour=CHARGE_HOUR, minute=0, second=0, microsecond=0), local + HEADS_UP_LEAD)
    else:
        at = next_window_start(local, af, after_current=bool(key))
    if not at:
        return None
    probe_local = at
    until = next_window_start(probe_local, af)
    need = _round_up(payday_need(af.user, at, until)) if until else 0
    amount, why = clamp(af, need, now)
    return {"at": at, "window": window_key(at.date(), af), "covers_until": until, "amount_kobo": amount,
            "fee_kobo": cards.quote(amount).fee_kobo if amount >= MIN_CHARGE_KOBO else 0, "limited_by": why}


def consent_text(af: AutoFill) -> str:
    when = []
    if af.payday_end:
        when.append("in the last 5 days of each month")
    if af.payday_start:
        when.append("on the 1st to the 5th of each month")
    if af.just_in_time:
        when.append("and up to a day before a drip my balance can't cover")
    days = ", ".join(when).replace(", and", " and").removeprefix("and ")
    return (f"I allow SpenDrip to charge {_card(af)} up to {N(af.max_per_charge_kobo)} per charge and {N(af.max_per_month_kobo)} per month, "
            f"{days}, to top up my SpenDrip balance, until I turn Auto-fill off.")
