"""
Card top-ups through Paystack, with saved cards.

Flow: quote → start (Paystack checkout) → the app comes back with the reference → complete().
Paystack's webhook also calls complete(); whichever arrives first credits the wallet, exactly once.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.services import FlowError
from notifications.models import OutboxMessage
from notifications.services import notify
from providers import get_card_gateway
from providers import messages as copy
from providers.paystack import card_fee_kobo, gross_for_net

from . import services as ledger
from .crypto import decrypt, encrypt
from .models import CardCharge, Inflow, SavedCard

MIN_TOPUP_KOBO = 10_000  # ₦100
MAX_TOPUP_KOBO = 1_000_000_000  # ₦10m


@dataclass(frozen=True)
class Quote:
    net_kobo: int  # lands in the wallet
    fee_kobo: int  # Paystack's card fee
    gross_kobo: int  # charged to the card
    payer_covers_fee: bool


def gateway():
    g = get_card_gateway()
    if g is None:
        raise FlowError("Card payments aren't set up yet. Use a bank transfer for now.", code="cards_unavailable", status=503)
    return g


def quote(net_kobo: int) -> Quote:
    if not MIN_TOPUP_KOBO <= net_kobo <= MAX_TOPUP_KOBO:
        raise FlowError("Card top-ups must be between ₦100 and ₦10,000,000.")
    if settings.PAYSTACK["PASS_CARD_FEES"]:
        gross = gross_for_net(net_kobo)
        return Quote(net_kobo, gross - net_kobo, gross, True)
    return Quote(net_kobo, card_fee_kobo(net_kobo), net_kobo, False)


def customer_email(user) -> str:
    """Paystack needs a real-looking email. We don't ask for one at sign-up, so fall back to a SpenDrip address."""
    email = (user.email or "").strip().lower()
    domain = email.rsplit("@", 1)[-1] if "@" in email else ""
    if domain and "." in domain and not domain.endswith((".local", ".test", ".localhost", ".invalid")):
        return email
    return f"{user.phone or user.pk}@users.spendrip.com"


def _new_charge(user, q: Quote, *, save_card: bool, card: SavedCard | None = None) -> CardCharge:
    return CardCharge.objects.create(user=user, reference=f"sdc_{uuid.uuid4().hex}", net_kobo=q.net_kobo, fee_kobo=q.fee_kobo,
                                     gross_kobo=q.gross_kobo, save_card=save_card, card=card)


def start(user, net_kobo: int, *, save_card: bool) -> dict:
    """Start a checkout. Returns the Paystack page to send the person to."""
    q = quote(net_kobo)
    charge = _new_charge(user, q, save_card=save_card)
    page = gateway().initialize(email=customer_email(user), amount_kobo=q.gross_kobo, reference=charge.reference,
                                callback_url=settings.SPENDRIP["PUBLIC_APP_URL"].rstrip("/") + "/fund/card",
                                metadata={"spendrip_charge": charge.reference, "net_kobo": q.net_kobo, "save_card": save_card})
    return {"reference": charge.reference, "authorization_url": page["authorization_url"], "test_mode": gateway().test_mode}


def complete(reference: str, result: dict | None = None) -> CardCharge:
    """
    Settle a top-up from Paystack's answer (asking Paystack if `result` isn't given). Idempotent:
    a charge is credited once, however many times this runs.
    """
    result = result or gateway().verify(reference)
    with transaction.atomic():
        charge = CardCharge.objects.select_for_update().select_related("user").get(reference=reference)
        if charge.status != CardCharge.Status.STARTED:
            return charge
        ok = result["status"] == "success" and result["currency"] == "NGN" and result["amount_kobo"] == charge.gross_kobo
        if not ok:
            if result["status"] in ("failed", "abandoned", "reversed") or (result["status"] == "success" and result["amount_kobo"] != charge.gross_kobo):
                charge.status = CardCharge.Status.FAILED
                charge.message = (result.get("message") or "The payment didn't go through.")[:200]
                charge.completed_at = timezone.now()
                charge.save(update_fields=["status", "message", "completed_at"])
            return charge  # still pending: leave it for the webhook or the next check

        inflow, _ = Inflow.objects.get_or_create(
            provider="paystack", reference=reference,
            defaults={"user": charge.user, "amount_kobo": charge.net_kobo, "sender_name": "Card top-up", "raw": {"gross_kobo": charge.gross_kobo}},
        )
        ledger.credit_inflow(inflow, source=ledger.PAYSTACK)
        auth = result.get("authorization")
        if charge.save_card and auth and auth.get("reusable") and auth.get("authorization_code") and not charge.card_id:
            card, _ = SavedCard.objects.update_or_create(
                user=charge.user, signature=auth.get("signature") or auth["authorization_code"],
                defaults={"authorization_code_enc": encrypt(auth["authorization_code"]), "brand": auth.get("brand", ""),
                          "last4": auth.get("last4", ""), "bank": auth.get("bank", ""), "exp_month": auth.get("exp_month", ""),
                          "exp_year": auth.get("exp_year", ""), "email": customer_email(charge.user), "active": True},
            )
            charge.card = card
        if charge.card_id:
            SavedCard.objects.filter(pk=charge.card_id).update(last_used_at=timezone.now())
        charge.status, charge.inflow, charge.completed_at, charge.message = CardCharge.Status.SUCCESS, inflow, timezone.now(), ""
        charge.save(update_fields=["status", "inflow", "card", "completed_at", "message"])
    notify(charge.user, key=f"card:{reference}:in_app", channel=OutboxMessage.Channel.IN_APP, template="self_topped_up",
           body=copy.self_topped_up(amount_kobo=charge.net_kobo))
    return charge


def charge_saved_card(user, card: SavedCard, net_kobo: int) -> CardCharge:
    """One-tap top-up with a saved card."""
    if not card.active or card.user_id != user.pk:
        raise FlowError("That card isn't saved any more.", status=404)
    q = quote(net_kobo)
    charge = _new_charge(user, q, save_card=False, card=card)
    result = gateway().charge_authorization(email=card.email, amount_kobo=q.gross_kobo, authorization_code=decrypt(card.authorization_code_enc),
                                            reference=charge.reference, metadata={"spendrip_charge": charge.reference, "net_kobo": q.net_kobo})
    if result["status"] in ("pending", "ongoing"):
        result = gateway().verify(charge.reference)  # still working: ask Paystack for the final answer
    elif result["status"] not in ("success", "failed", "abandoned"):
        # e.g. send_otp / send_pin / open_url: the bank wants the cardholder present, which one-tap can't do.
        result = {**result, "status": "failed", "message": "Your bank asked for extra confirmation. Use “Pay with card” instead."}
    return complete(charge.reference, result)


def remove_card(card: SavedCard) -> None:
    try:
        gateway().deactivate(decrypt(card.authorization_code_enc))
    except Exception:
        pass  # we stop using it either way
    card.active = False
    card.save(update_fields=["active"])
