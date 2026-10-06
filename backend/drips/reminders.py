"""
Money reminders, sent by the worker:

1. Month outlook (1st of the month, morning): everything due this month, what's in the balance, what to add.
2. A day ahead: a drip (or group payout) due in the next 24 hours that the balance can't cover as things stand.
3. On the spot: a drip that just couldn't go out for lack of money (sent from the worker when it happens).

Each one is sent at most once per person per subject (OutboxMessage dedupe keys), so a worker restart never repeats them.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Q

from accounts.models import User
from engine import format_naira as N
from ledger import services as ledger
from notifications.models import OutboxMessage
from notifications.services import notify

from .autofill import declined_note
from .models import Plan
from .services import user_forecast

OUTLOOK_FROM_HOUR = 7  # local time on the 1st; if the worker was down, it still goes out within the first 3 days
LOOKAHEAD = timedelta(hours=24)
WAITING = ("wait", "short", "cap")


def _app(path: str = "") -> str:
    return settings.SPENDRIP["PUBLIC_APP_URL"].rstrip("/") + path


def _when(dt: datetime, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%a %-d %b, %-I:%M %p").replace("AM", "am").replace("PM", "pm")


def _people() -> list[User]:
    """Verified people with at least one active plan."""
    return list(User.objects.filter(kyc_status=User.Kyc.VERIFIED, plans__status=Plan.Status.ACTIVE).distinct())


def send_reminders(now: datetime) -> dict:
    sent = {"outlook": 0, "ahead": 0}
    for user in _people():
        sent["outlook"] += month_outlook(user, now)
        sent["ahead"] += day_ahead(user, now)
    return sent


# ---------------------------------------------------------------- 1. month outlook

def month_outlook(user: User, now: datetime) -> int:
    if not user.email or not user.notify_email:
        return 0
    tz = ZoneInfo(user.tz or "Africa/Lagos")
    local = now.astimezone(tz)
    if local.day > 3 or (local.day == 1 and local.hour < OUTLOOK_FROM_HOUR):
        return 0
    key = f"outlook:{user.pk}:{local:%Y-%m}"
    if OutboxMessage.objects.filter(dedupe_key=key).exists():
        return 0
    f = user_forecast(user, now)
    if not f.events:
        return 0
    bal = ledger.balance(user).available_kobo
    plans = {str(p.pk): p for p in Plan.objects.filter(user=user, status=Plan.Status.ACTIVE)}
    by_plan: dict[str, list] = {}
    for e in f.events:
        by_plan.setdefault(e.plan_id, []).append(e)
    lines = []
    for pid, evs in sorted(by_plan.items(), key=lambda kv: (plans.get(kv[0]).priority_rank or 9 if plans.get(kv[0]) else 9, kv[0])):
        p = plans.get(pid)
        if not p:
            continue
        cost = sum(e.cost_kobo for e in evs)
        who = f"{len(p.active_lines())} people" if p.is_group else (p.recipient.label if p.recipient else "")
        tag = f" · priority {p.priority_rank}" if p.priority_rank else ""
        lines.append(f"{p.emoji} {p.label} → {who}: {len(evs)} × {N(evs[0].amount_kobo)} = {N(cost)} with fees{tag}")
    month = local.strftime("%B")
    heading = f"Your {month} at a glance: {N(f.total_needed_kobo)} going out"
    if f.top_up_kobo > 0:
        verdict = (f"You have {N(bal)} in your balance, so you need to add {N(f.top_up_kobo)} this month for everything to go out on time."
                   + (f" Your priorities alone need {N(f.priority_shortfall_kobo)} more." if f.priority_shortfall_kobo > 0 else ""))
        button = (f"Add {N(f.top_up_kobo)}", _app("/fund"))
    else:
        verdict = f"You have {N(bal)} in your balance, which covers all of it. Nothing to do."
        button = ("Open SpenDrip", _app())
    paragraphs = [f"Hi {user.first_name.title() or 'there'}, here's what SpenDrip will send for you in {month}:", *lines, verdict,
                  "Fees are counted in. Drips that wait for money don't send later, so topping up early keeps everyone paid on the day."]
    body = f"{month}: {N(f.total_needed_kobo)} going out" + (f", add {N(f.top_up_kobo)}" if f.top_up_kobo > 0 else ", fully covered")
    notify(user, key=key, channel=OutboxMessage.Channel.EMAIL, template="month_outlook", to=user.email, body=body,
           email={"subject": f"📅 {heading}", "heading": heading, "paragraphs": paragraphs, "button": button})
    notify(user, key=f"{key}:in_app", channel=OutboxMessage.Channel.IN_APP, template="month_outlook", body=body)
    return 1


# ---------------------------------------------------------------- 2. a day ahead

def day_ahead(user: User, now: datetime) -> int:
    """For each drip due in the next 24 hours that the balance can't cover as things stand: one email and one in-app note."""
    if not user.notify_low_balance:
        return 0
    f = user_forecast(user, now)
    soon = [e for e in f.events if e.status in WAITING and now <= e.at <= now + LOOKAHEAD]
    if not soon:
        return 0
    tz = ZoneInfo(user.tz or "Africa/Lagos")
    plans = {str(p.pk): p for p in Plan.objects.filter(user=user)}
    sent = 0
    for e in soon:
        p = plans.get(e.plan_id)
        if not p:
            continue
        key = f"ahead:{p.pk}:{e.at.isoformat()}"
        if OutboxMessage.objects.filter(dedupe_key__startswith=key).exists():
            continue
        who = f"{len(p.active_lines())} people" if p.is_group else (p.recipient.label if p.recipient else "")
        why = {"wait": "your balance can't cover it as things stand", "short": "your balance can't cover it as things stand",
               "cap": "it would go over your daily sending limit"}[e.status]
        need = max(0, e.cost_kobo - max(0, f.free_kobo if not p.priority_rank else ledger.balance(user).available_kobo))
        fix = (f"Add {N(need or e.cost_kobo)} before then and it goes out on time." if e.status != "cap"
               else "Raise your daily limit in Profile before then, or it will wait.")
        heading = f"Tomorrow: {p.emoji} {p.label} ({N(e.amount_kobo)}) may not go out"
        declined = declined_note(user, e.plan_id, e.at) if e.status != "cap" else None
        paragraphs = [f"{p.emoji} {p.label} → {who} is due {_when(e.at, tz)}: {N(e.amount_kobo)} plus {N(e.fee_kobo)} fees.",
                      f"Right now {why}.", *([declined] if declined else []), fix,
                      ("Group payouts are all or nothing: if the balance can't cover everyone, nobody on it is paid." if p.is_group else
                       "Drips that wait for money don't send later, so this is the moment to top up.")]
        body = f"{p.emoji} {p.label} is due {_when(e.at, tz)} and may not go out: {fix}"
        if user.email:
            notify(user, key=f"{key}:email", channel=OutboxMessage.Channel.EMAIL, template="low_balance_ahead", to=user.email, body=body,
                   email={"subject": f"⏰ {heading}", "heading": heading, "paragraphs": paragraphs,
                          "button": ("Add money", _app("/fund")) if e.status != "cap" else ("Open Profile", _app("/profile"))})
        for ch in (OutboxMessage.Channel.IN_APP, OutboxMessage.Channel.PUSH):
            notify(user, key=f"{key}:{ch}", channel=ch, template="low_balance_ahead", body=body)
        sent += 1
    return sent


# ---------------------------------------------------------------- 3. on the spot

def spot_email(user: User, *, key: str, emoji: str, label: str, who: str, amount_kobo: int, cost_kobo: int, reason: str,
               short_by_kobo: int, at: datetime, is_group: bool = False, people: int = 0) -> None:
    """A drip (or group payout) was due and couldn't go out for lack of money. Email, once, with the exact top-up."""
    if not (user.email and user.notify_low_balance):
        return
    tz = ZoneInfo(user.tz or "Africa/Lagos")
    why = {"insufficient_funds": "your balance was short", "protected_for_priorities": "the money is set aside for your priorities",
           "daily_cap": "it would have gone over your daily sending limit"}.get(reason, "your balance was short")
    what = f"{emoji} {label} → {who}" + (f" ({people} people)" if is_group else "")
    heading = f"{emoji} {label} didn't go out: {why}"
    if is_group:
        follow = (f"Add {N(short_by_kobo)} in the next few hours and everyone on it is paid together." if short_by_kobo
                  else "Raise your daily limit in Profile and it goes out on the next check.")
    else:
        follow = (f"Add {N(short_by_kobo)} now so the next one goes out, or send this one again from Activity." if short_by_kobo
                  else "Raise your daily limit in Profile so the next one goes out.")
    paragraphs = [f"{what} was due {_when(at, tz)}: {N(amount_kobo)} plus fees, {N(cost_kobo)} in all.",
                  f"It didn't go out because {why}" + (f", by {N(short_by_kobo)}." if short_by_kobo else "."), follow]
    notify(user, key=key, channel=OutboxMessage.Channel.EMAIL, template="low_balance_now", to=user.email, body=heading,
           email={"subject": f"⚠️ {heading}", "heading": heading, "paragraphs": paragraphs,
                  "button": ("Add money", _app("/fund")) if reason != "daily_cap" else ("Open Profile", _app("/profile"))})
