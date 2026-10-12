"""
Pays it forward: entries, the draw and the payout.

- Entering is free: any verified person with an active plan can enter once a month (no top-up needed).
- The draw is reproducible: seed = sha256(month | public value | entry ids in order); the winner is seed mod pool size.
- The payout is an Inflow credited from the "promotions" ledger account, so it shows in Activity like any top-up and
  never touches other people's money. Fund the Paystack balance with the prize from company money before paying.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.services import FlowError
from drips.models import Plan
from engine import format_naira as N
from ledger import services as ledger
from ledger.models import Inflow
from notifications.models import OutboxMessage
from notifications.services import notify

from .models import BoostEntry, BoostMonth

PROMOTIONS = "promotions"  # the ledger account prizes are paid from (a marketing cost)
STORY_MAX = 280


def month_key(now: datetime | None = None) -> str:
    return (now or timezone.now()).astimezone(ZoneInfo("Africa/Lagos")).strftime("%Y-%m")


def eligible(user) -> str | None:
    """None if the person can enter, else why not (shown in the app)."""
    if user.is_staff or user.is_superuser:
        return "SpenDrip staff can't enter."
    if not user.is_verified:
        return "Verify your identity to enter."
    if user.locked_at:
        return "Unlock your account to enter."
    if not Plan.objects.filter(user=user, status=Plan.Status.ACTIVE).exists():
        return "Set up a plan to enter. Entering is free; you don't need to top up."
    return None


def enter(user, *, recipient_id, story: str, consent_publish: bool, now: datetime | None = None) -> BoostEntry:
    if not settings.BOOST_ENABLED:
        raise FlowError("Pays it forward isn't open right now.", code="boost_closed", status=403)
    why = eligible(user)
    if why:
        raise FlowError(why, code="not_eligible", status=403)
    story = " ".join(str(story or "").split())
    if len(story) < 20:
        raise FlowError("Tell us a little more: at least a sentence.")
    if len(story) > STORY_MAX:
        raise FlowError(f"Keep it to {STORY_MAX} characters.")
    recipient = user.recipients.filter(pk=recipient_id, is_self=False).first() if recipient_id else None
    if not recipient:
        raise FlowError("Pick the person you look after.")
    month, _ = BoostMonth.objects.get_or_create(month=month_key(now), defaults={"prize_kobo": settings.BOOST_PRIZE_KOBO})
    if month.status != BoostMonth.Status.OPEN:
        raise FlowError("This month's draw has closed. Enter again next month.", code="boost_closed", status=403)
    entry, _ = BoostEntry.objects.update_or_create(month=month, user=user, defaults={
        "recipient": recipient, "story": story, "consent_publish": bool(consent_publish)})
    return entry


def pool(month: BoostMonth) -> list[BoostEntry]:
    """Shortlisted entries whose people are still eligible; every eligible entry if none are shortlisted."""
    entries = list(month.entries.select_related("user", "recipient").order_by("pk"))
    ok = [e for e in entries if eligible(e.user) is None and e.recipient_id]
    picked = [e for e in ok if e.shortlisted]
    return picked or ok


def seed_for(month: str, public_value: str, ids: list[int]) -> str:
    return hashlib.sha256(f"{month}|{public_value.strip()}|{','.join(map(str, ids))}".encode()).hexdigest()


@transaction.atomic
def draw(month_key_: str, public_value: str, *, now: datetime | None = None) -> BoostMonth:
    month = BoostMonth.objects.select_for_update().get(month=month_key_)
    if month.status != BoostMonth.Status.OPEN:
        raise FlowError(f"{month_key_} was already drawn.")
    if month_key_ >= month_key(now):
        raise FlowError(f"{month_key_} hasn't ended yet. Draw it after the month is over.")
    if not public_value.strip():
        raise FlowError("Give the public value published before the draw.")
    entries = pool(month)
    if not entries:
        raise FlowError(f"No eligible entries for {month_key_}.")
    ids = [e.pk for e in entries]
    seed = seed_for(month.month, public_value, ids)
    month.winner = entries[int(seed, 16) % len(entries)]
    month.public_value, month.seed, month.pool_ids, month.pool_size = public_value.strip(), seed, ids, len(ids)
    month.status, month.drawn_at = BoostMonth.Status.DRAWN, now or timezone.now()
    month.save()
    return month


def pay(month_key_: str) -> BoostMonth:
    """Credit the prize to the winner's balance (once) and tell them."""
    if not settings.BOOST_ENABLED:
        raise FlowError("Pays it forward is switched off (BOOST_ENABLED).")
    month = BoostMonth.objects.select_related("winner__user", "winner__recipient").get(month=month_key_)
    if month.status == BoostMonth.Status.PAID:
        return month
    if month.status != BoostMonth.Status.DRAWN or not month.winner:
        raise FlowError(f"Draw {month_key_} first.")
    e = month.winner
    if eligible(e.user) is not None:
        raise FlowError(f"The winner isn't eligible any more ({eligible(e.user)}). Redraw by setting the month back to open.")
    ledger.account(PROMOTIONS)
    who = e.recipient.label if e.recipient else "the people you look after"
    with transaction.atomic():
        inflow, _ = Inflow.objects.get_or_create(provider="boost", reference=month.month, defaults={
            "user": e.user, "amount_kobo": month.prize_kobo, "sender_name": f"SpenDrip Pays it forward · for {who}",
            "raw": {"seed": month.seed, "public_value": month.public_value}})
        ledger.credit_inflow(inflow, source=PROMOTIONS)
        month.inflow, month.status, month.paid_at = inflow, BoostMonth.Status.PAID, timezone.now()
        month.save(update_fields=["inflow", "status", "paid_at"])
    u, prize = e.user, N(month.prize_kobo)
    body = f"🎉 Your story won this month's Pays it forward! We've added {prize} to your SpenDrip balance for {who}."
    key = f"boost:{month.month}:won"
    notify(u, key=f"{key}:in_app", channel=OutboxMessage.Channel.IN_APP, template="boost_won", body=body)
    notify(u, key=f"{key}:push", channel=OutboxMessage.Channel.PUSH, template="boost_won", body=body)
    if u.email:
        notify(u, key=f"{key}:email", channel=OutboxMessage.Channel.EMAIL, template="boost_won", to=u.email, body=body, email={
            "subject": f"🎉 You won {prize} for {who}", "heading": f"{prize} for {who}, on us",
            "paragraphs": [f"Your story won SpenDrip Pays it forward for {datetime.strptime(month.month, '%Y-%m'):%B %Y}.",
                           f"We've added {prize} to your SpenDrip balance. Use it for {who}'s drips, or any plan you like.",
                           "You don't need to do anything to receive it, and we will never ask you to pay a fee or share your PIN "
                           "to claim a prize. Anyone who does isn't SpenDrip."],
            "button": ("Open SpenDrip", settings.SPENDRIP["PUBLIC_APP_URL"])})
    return month


def winners(limit: int = 6) -> list[dict]:
    """Past winners who agreed to be named: first name and who they look after only."""
    out = []
    for m in BoostMonth.objects.filter(status=BoostMonth.Status.PAID, winner__consent_publish=True).select_related(
            "winner__user", "winner__recipient").order_by("-month")[:limit]:
        e = m.winner
        out.append({"month": m.month, "first_name": e.user.first_name.title(), "for": e.recipient.label if e.recipient else "",
                    "story": e.story, "prize_kobo": m.prize_kobo})
    return out
