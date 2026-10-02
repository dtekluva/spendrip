"""Sign-up, OTP and unlock rules. Views stay thin; the rules live here so they're testable."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from ledger import services as ledger
from ledger.models import FundingAccount
from notifications.models import OutboxMessage
from notifications.services import notify
from providers import get_payment_provider

from .models import OneTimeCode, User


class FlowError(Exception):
    """A user-facing problem. `message` is shown as-is."""

    def __init__(self, message: str, code: str = "invalid", status: int = 400):
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


def normalise_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("234") and len(digits) == 13:
        digits = "0" + digits[3:]
    if not (len(digits) == 11 and digits.startswith("0")):
        raise FlowError("Enter an 11-digit Nigerian phone number, like 0803 123 4567.")
    return digits


def normalise_email(raw: str) -> str:
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email
    email = raw.strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        raise FlowError("That email doesn't look right. Check it and try again.")
    return email


def mask_email(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:2]}{'•' * max(1, min(len(name) - 2, 5))}@{domain}" if domain else email


def mask_phone(phone: str) -> str:
    return f"{phone[:4]} ••• {phone[-4:]}" if len(phone) >= 8 else phone


def nin_fingerprint(nin: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), nin.encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------- OTP

def send_otp(target: str, purpose: str, *, user: User | None = None) -> str:
    """Send a 6-digit code by email (or SMS for a phone). Returns the code only so dev tools can show it;
    callers must not expose it otherwise."""
    cfg = settings.SPENDRIP
    last = OneTimeCode.objects.filter(target=target, purpose=purpose).order_by("-created_at").first()
    if last and (timezone.now() - last.created_at).total_seconds() < cfg["OTP_RESEND_SECONDS"]:
        wait = int(cfg["OTP_RESEND_SECONDS"] - (timezone.now() - last.created_at).total_seconds()) + 1
        raise FlowError(f"Wait {wait} seconds before asking for another code.", code="otp_wait", status=429)
    code = f"{secrets.randbelow(1_000_000):06d}"
    OneTimeCode.objects.create(target=target, purpose=purpose, code_hash=make_password(code),
                               expires_at=timezone.now() + timedelta(seconds=cfg["OTP_TTL_SECONDS"]))
    if "@" in target:
        from notifications.emails import sign_in_code
        if not sign_in_code(target, code, purpose) and not cfg["DEV_TOOLS"]:
            raise FlowError("We couldn't send the email just now. Try again in a minute.", code="email_failed", status=503)
    elif user:
        notify(user, key=f"otp:{target}:{secrets.token_hex(6)}", channel=OutboxMessage.Channel.SMS, template="otp", to=target,
               body=f"Your SpenDrip code is {code}. It expires in 10 minutes. Never share it.")
    return code


def check_otp(target: str, purpose: str, code: str) -> None:
    cfg = settings.SPENDRIP
    otp = OneTimeCode.objects.filter(target=target, purpose=purpose, consumed_at__isnull=True).order_by("-created_at").first()
    if not otp or otp.expires_at < timezone.now():
        raise FlowError("That code has expired. Ask for a new one.", code="otp_expired")
    if otp.attempts >= cfg["OTP_MAX_ATTEMPTS"]:
        raise FlowError("Too many tries. Ask for a new code.", code="otp_locked")
    if not check_password(code, otp.code_hash):
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        raise FlowError("That code didn't work. Check the email and try again.", code="otp_wrong")
    otp.consumed_at = timezone.now()
    otp.save(update_fields=["consumed_at"])


# ---------------------------------------------------------------- after verification

def kyc_mode() -> str:
    return "live" if settings.SPENDRIP.get("KYC_PROVIDER") == "live" else "mock"


def limits(user: User) -> dict | None:
    """Tier-1 limits for live-verified accounts (BVN + ID, no face match yet). None = no extra limits."""
    if kyc_mode() != "live":
        return None
    c = settings.SPENDRIP
    return {"max_balance_kobo": c["TIER1_MAX_BALANCE_KOBO"], "max_drip_kobo": c["TIER1_MAX_DRIP_KOBO"]}


def bvn_result(data: dict, ok: bool) -> bool:
    """Paystack's answer to a BVN check (customeridentification.success / .failed). Returns True if it changed a user."""
    from drips.models import Recipient
    from providers.banks import BY_NIP
    from .models import KycCheck
    code = (data.get("customer_code") or "").strip()
    email = (data.get("email") or "").strip().lower()
    user = (User.objects.filter(paystack_customer_code=code).first() if code else None) or \
        (User.objects.filter(email=email).first() if email else None)
    if not user or user.kyc_status != User.Kyc.BVN_PENDING:
        return False
    pending = KycCheck.objects.filter(user=user, step=KycCheck.Step.NIN, provider="paystack", raw__pending=True).order_by("-created_at").first()
    with transaction.atomic():
        if ok:
            user.kyc_status, user.kyc_message = User.Kyc.NIN_VERIFIED, ""
            if pending and not user.recipients.filter(nip_bank_code=pending.raw["nip_bank_code"], account_number=pending.raw["account_number"]).exists():
                bank = BY_NIP.get(pending.raw["nip_bank_code"], ("Bank", ""))
                Recipient.objects.create(user=user, label="Me", is_self=not user.recipients.filter(is_self=True).exists(),
                                         bank_name=bank[0], nip_bank_code=pending.raw["nip_bank_code"], cbn_bank_code=bank[1],
                                         account_number=pending.raw["account_number"], verified_account_name=pending.raw["account_name"],
                                         verified_at=timezone.now())
        else:
            reason = (data.get("reason") or "").strip()
            user.kyc_status = User.Kyc.NOT_STARTED
            user.nin_hash, user.nin_last4 = "", ""
            user.kyc_message = ("Paystack couldn't match your BVN with that bank account and name"
                                + (f": {reason}" if reason else ".") + " Check the details and try again.")[:240]
        user.save()
        KycCheck.objects.create(user=user, step=KycCheck.Step.NIN, passed=ok, provider="paystack", provider_ref=code,
                                raw={"id_type": "bvn", "result": "success" if ok else "failed", "reason": data.get("reason", "")})
        if pending:
            pending.raw = {**pending.raw, "pending": False}
            pending.save(update_fields=["raw"])
    return True


def require_verified(user: User) -> None:
    """Money only moves for people who've verified their identity."""
    if not user.is_verified:
        raise FlowError("Verify your identity first. It takes about two minutes.", code="kyc_required", status=403)


@transaction.atomic
def finish_verification(user: User) -> FundingAccount:
    """NIN/BVN, ID and selfie all passed: verify the user and give them their account number."""
    user.kyc_status, user.kyc_message = User.Kyc.VERIFIED, ""
    user.kyc_tier = max(user.kyc_tier, 1)
    user.save(update_fields=["kyc_status", "kyc_message", "kyc_tier"])
    ledger.ensure_user_accounts(user)
    existing = user.funding_accounts.first()
    if existing or not settings.SPENDRIP.get("BANK_TRANSFER_FUNDING", True):
        return existing  # no account number without real bank-transfer funding
    provider = get_payment_provider()
    va = provider.create_virtual_account(first_name=user.first_name.title(), last_name=user.last_name.title(),
                                         email=user.email or f"u{user.pk}@users.spendrip.com", phone=user.phone or "")
    return FundingAccount.objects.create(user=user, provider=provider.name, account_number=va.account_number,
                                         bank_name=va.bank_name, bank_code=va.bank_code, account_name=va.account_name)


# ---------------------------------------------------------------- app lock

UNLOCKED_AT = "unlocked_at"
LAST_SEEN = "last_seen"


def mark_unlocked(request) -> None:
    now = timezone.now().timestamp()
    request.session[UNLOCKED_AT] = now
    request.session[LAST_SEEN] = now


def is_unlocked(request) -> bool:
    last = request.session.get(LAST_SEEN)
    if not request.session.get(UNLOCKED_AT) or last is None:
        return False
    return timezone.now().timestamp() - last < settings.SPENDRIP["IDLE_LOCK_SECONDS"]


def touch(request) -> None:
    request.session[LAST_SEEN] = timezone.now().timestamp()


def lock(request) -> None:
    request.session.pop(UNLOCKED_AT, None)
