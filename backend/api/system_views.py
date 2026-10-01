import hmac
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
