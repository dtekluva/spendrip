import hmac
import json
import logging
import uuid

from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.services import FlowError
from drips.worker import Worker
from engine import naira
from ledger import services as ledger
from ledger.models import FundingAccount, Inflow
from notifications.models import OutboxMessage
from notifications.services import notify
from providers import get_payment_provider
from providers import messages as copy

log = logging.getLogger("spendrip.api")


def dev_tools() -> bool:
    return settings.SPENDRIP["DEV_TOOLS"]


class Health(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"ok": True, "time": timezone.now(), "payment_provider": settings.SPENDRIP["PAYMENT_PROVIDER"]})


class CronTick(APIView):
    """Scheduled tick for serverless hosting (Vercel Cron or any pinger). Needs Authorization: Bearer <CRON_SECRET>."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        secret = settings.SPENDRIP["CRON_SECRET"]
        if not secret:
            return Response({"error": "CRON_SECRET is not set", "code": "not_configured"}, status=503)
        if not hmac.compare_digest(request.headers.get("Authorization", ""), f"Bearer {secret}"):
            return Response({"error": "Not allowed", "code": "forbidden"}, status=403)
        return Response(Worker().tick())

    post = get


class LibertyWebhook(APIView):
    """
    Liberty calls this when money lands in a virtual account. We never trust the payload: we take
    the session id, ask Liberty to confirm it, and credit the matching user once.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        secret = settings.SPENDRIP["WEBHOOK_SECRET"]
        if secret and not hmac.compare_digest(request.headers.get("X-SpenDrip-Secret", ""), secret):
            return Response({"error": "Not allowed"}, status=403)
        d = request.data if isinstance(request.data, dict) else {}
        session_id = str(d.get("session_id") or d.get("sessionid") or d.get("sessionId") or "")
        if not session_id:
            return Response({"error": "session_id missing"}, status=400)
        event = get_payment_provider().verify_inflow(session_id)
        if not event or not event.successful:
            log.warning("webhook %s could not be verified", session_id)
            return Response({"ok": True, "credited": False}, status=202)
        fa = FundingAccount.objects.filter(account_number=event.account_number).select_related("user").first()
        inflow, _ = Inflow.objects.get_or_create(
            provider=event.provider, reference=event.reference,
            defaults={"user": fa.user if fa else None, "funding_account": fa, "amount_kobo": event.amount_kobo,
                      "sender_name": event.sender_name[:120], "raw": event.raw},
        )
        if not fa:
            inflow.status, inflow.reject_reason = Inflow.Status.REJECTED, "no matching funding account"
            inflow.save(update_fields=["status", "reject_reason"])
            return Response({"ok": True, "credited": False}, status=202)
        credited = ledger.credit_inflow(inflow)
        if credited:
            notify(fa.user, key=f"inflow:{inflow.pk}:in_app", channel=OutboxMessage.Channel.IN_APP, template="self_topped_up",
                   body=copy.self_topped_up(amount_kobo=inflow.amount_kobo))
        return Response({"ok": True, "credited": credited})


class DevTopUp(APIView):
    """Dev only: pretend a bank transfer landed in your SpenDrip account."""

    def post(self, request):
        if not dev_tools():
            return Response(status=404)
        try:
            amount = naira(request.data.get("amount_naira"))
        except Exception:
            raise FlowError("amount_naira must be a number.")
        if amount <= 0:
            raise FlowError("amount_naira must be more than 0.")
        inflow = Inflow.objects.create(provider="mock", reference=f"dev-{uuid.uuid4()}", user=request.user, amount_kobo=amount,
                                       sender_name="DEV TOP-UP", raw={"dev": True})
        ledger.credit_inflow(inflow)
        notify(request.user, key=f"inflow:{inflow.pk}:in_app", channel=OutboxMessage.Channel.IN_APP, template="self_topped_up",
               body=copy.self_topped_up(amount_kobo=amount))
        return Response({"credited_kobo": amount, "available_kobo": ledger.balance(request.user).available_kobo}, status=201)


class DevTick(APIView):
    def post(self, request):
        if not dev_tools():
            return Response(status=404)
        return Response(Worker().tick())


# ------------------------------------------------------------------ Paystack webhook

from django.http import HttpResponse, JsonResponse  # noqa: E402
from django.views.decorators.csrf import csrf_exempt  # noqa: E402
from django.views.decorators.http import require_POST  # noqa: E402

from drips.models import Run  # noqa: E402
from ledger import cards  # noqa: E402
from ledger.models import CardCharge  # noqa: E402
from providers.paystack import verify_webhook  # noqa: E402


@csrf_exempt
@require_POST
def paystack_webhook(request):
    """
    Paystack events. Only accepted with a valid signature, and never trusted on their own: card
    payments are re-checked with Paystack, and transfers are handed to the worker's status check.
    """
    secret = settings.PAYSTACK["SECRET_KEY"]
    if not secret or not verify_webhook(secret, request.body, request.headers.get("X-Paystack-Signature", "")):
        return HttpResponse(status=401)
    try:
        event = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)
    kind, data = event.get("event", ""), event.get("data") or {}
    ref = str(data.get("reference", ""))
    if kind == "charge.success" and CardCharge.objects.filter(reference=ref).exists():
        cards.complete(ref)  # verifies with Paystack before crediting, once
    elif kind.startswith("transfer.") and ref:
        # Ask the worker to check this transfer with Paystack on its next tick.
        Run.objects.filter(pk=ref if _is_uuid(ref) else None, status__in=Run.IN_FLIGHT).update(next_check_at=timezone.now())
    return JsonResponse({"ok": True})


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except ValueError:
        return False


# ------------------------------------------------------------------ waitlist (landing page)

import re  # noqa: E402

from django.core.cache import cache  # noqa: E402
from django.core.validators import validate_email  # noqa: E402
from django.core.exceptions import ValidationError  # noqa: E402

from notifications import emails  # noqa: E402
from accounts.models import WaitlistEntry  # noqa: E402
from accounts.services import normalise_phone  # noqa: E402

WAITLIST_PER_IP_PER_HOUR = 10


class Waitlist(APIView):
    """Public: join the waitlist with a phone number or an email. No sign-in, no cookies."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        ip = (request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "?"))
        key = f"waitlist:{ip}"
        hits = cache.get(key, 0)
        if hits >= WAITLIST_PER_IP_PER_HOUR:
            raise FlowError("That's a lot of sign-ups from one place. Try again in an hour.", code="rate_limited", status=429)
        cache.set(key, hits + 1, 3600)

        raw = str(request.data.get("contact", "")).strip()
        name = str(request.data.get("name", "")).strip()[:80]
        if "@" in raw:
            contact, kind = raw.lower(), "email"
            try:
                validate_email(contact)
            except ValidationError:
                raise FlowError("That email doesn't look right.")
        else:
            try:
                contact, kind = normalise_phone(raw), "phone"
            except FlowError:
                raise FlowError("Enter a Nigerian phone number (like 0803 123 4567) or an email.")
        entry, created = WaitlistEntry.objects.get_or_create(contact=contact, defaults={"kind": kind, "name": name,
                                                                                        "source": str(request.data.get("source", "landing"))[:40]})
        if created and kind == "email":
            emails.waitlist_joined(entry)  # never fails the request; problems are logged
        return Response({"ok": True, "already": not created,
                         "message": "You're already on the list. We'll be in touch." if not created else "You're on the list! We'll invite you soon."},
                        status=200 if not created else 201)
