import uuid

from django.conf import settings
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from drips.models import Plan, Run
from drips.services import user_forecast
from drips.worker import Worker
from engine import naira
from ledger import services as ledger
from ledger.models import Inflow
from notifications.models import OutboxMessage
from notifications.services import notify
from providers import messages as copy

from .serializers import PlanSerializer, RunSerializer


def dev_tools() -> bool:
    return settings.SPENDRIP["DEV_TOOLS"]


class SignedInOrDemo(permissions.BasePermission):
    """Real sign-in comes in Phase 2. Until then, dev builds act as the seeded demo user."""

    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            return True
        if dev_tools():
            request.user = User.objects.filter(username="demo").first() or request.user
            return request.user.is_authenticated
        return False


class Health(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"ok": True, "time": timezone.now(), "payment_provider": settings.SPENDRIP["PAYMENT_PROVIDER"]})


def event_json(e):
    return {"plan_id": int(e.plan_id), "at": e.at, "amount_kobo": e.amount_kobo, "fee_kobo": e.fee_kobo, "rank": e.rank, "status": e.status}


class Summary(APIView):
    """Balance plus this month's forecast: what the Home screen needs."""

    permission_classes = [SignedInOrDemo]

    def get(self, request):
        user = request.user
        bal = ledger.balance(user)
        f = user_forecast(user)
        return Response({
            "balance": {"available_kobo": bal.available_kobo, "held_kobo": bal.held_kobo, "total_kobo": bal.total_kobo},
            "forecast": {
                "window_end": f.window_end,
                "protected_kobo": f.protected_kobo,
                "free_kobo": f.free_kobo,
                "total_needed_kobo": f.total_needed_kobo,
                "top_up_kobo": f.top_up_kobo,
                "priority_shortfall_kobo": f.priority_shortfall_kobo,
                "events": [event_json(e) for e in f.events],
            },
            "paused_all": user.paused_all,
            "funding_account": next(({"account_number": a.account_number, "bank_name": a.bank_name, "account_name": a.account_name}
                                     for a in user.funding_accounts.all()), None),
        })


class Plans(APIView):
    permission_classes = [SignedInOrDemo]

    def get(self, request):
        plans = Plan.objects.filter(user=request.user).exclude(status=Plan.Status.DELETED).select_related("recipient").order_by("created_at")
        return Response(PlanSerializer(plans, many=True).data)


class Activity(APIView):
    permission_classes = [SignedInOrDemo]

    def get(self, request):
        runs = Run.objects.filter(user=request.user).exclude(status=Run.Status.SCHEDULED).select_related("plan").order_by("-scheduled_for")[:100]
        msgs = OutboxMessage.objects.filter(user=request.user).exclude(channel=OutboxMessage.Channel.PUSH)[:100]
        return Response({
            "runs": RunSerializer(runs, many=True).data,
            "messages": [{"id": m.id, "channel": m.channel, "to": m.to, "body": m.body, "status": m.status, "created_at": m.created_at} for m in msgs],
        })


class DevTopUp(APIView):
    """Dev only: pretend a bank transfer landed in the user's SpenDrip account."""

    permission_classes = [SignedInOrDemo]

    def post(self, request):
        if not dev_tools():
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            amount = naira(request.data.get("amount_naira"))
        except Exception:
            return Response({"error": "amount_naira must be a number"}, status=400)
        if amount <= 0:
            return Response({"error": "amount_naira must be more than 0"}, status=400)
        inflow = Inflow.objects.create(provider="mock", reference=f"dev-{uuid.uuid4()}", user=request.user, amount_kobo=amount,
                                       sender_name="DEV TOP-UP", raw={"dev": True})
        ledger.credit_inflow(inflow)
        notify(request.user, key=f"inflow:{inflow.pk}:in_app", channel=OutboxMessage.Channel.IN_APP, template="self_topped_up",
               body=copy.self_topped_up(amount_kobo=amount))
        return Response({"credited_kobo": amount, "available_kobo": ledger.balance(request.user).available_kobo}, status=201)


class DevTick(APIView):
    """Dev only: run one worker tick now."""

    permission_classes = [SignedInOrDemo]

    def post(self, request):
        if not dev_tools():
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(Worker().tick())
