"""Turning notifications on for this phone or computer (see notifications/push.py)."""
from django.db import transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.services import FlowError
from notifications import push
from notifications.models import PushDevice

from .permissions import SignedIn


def _sub(data) -> tuple[str, str, str]:
    endpoint, keys = str(data.get("endpoint") or ""), data.get("keys") or {}
    p256dh, auth = str(keys.get("p256dh") or ""), str(keys.get("auth") or "")
    if not endpoint.startswith("https://") or len(endpoint) > 1000 or not p256dh or not auth or len(p256dh) > 200 or len(auth) > 100:
        raise FlowError("That notification setup didn't look right. Try again.", code="push_bad")
    return endpoint, p256dh, auth


class PushDevices(APIView):
    """POST a browser PushSubscription (as JSON) to start sending here; DELETE it (just the endpoint) to stop."""

    def get_permissions(self):
        # Signing out from the lock screen removes this device first, so DELETE only needs a signed-in session.
        return [SignedIn()] if self.request.method == "DELETE" else super().get_permissions()

    def post(self, request):
        endpoint, p256dh, auth = _sub(request.data)
        u = request.user
        with transaction.atomic():
            # One device, one person: if someone else used to be signed in here, it moves to whoever is now.
            PushDevice.objects.update_or_create(endpoint=endpoint, defaults={
                "user": u, "p256dh": p256dh, "auth": auth, "failures": 0,
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300]})
        if not u.notify_push:
            u.notify_push = True
            u.save(update_fields=["notify_push"])
        return Response({"ok": True, "devices": u.push_devices.count()}, status=201)

    def delete(self, request):
        endpoint = str(request.data.get("endpoint") or "")
        PushDevice.objects.filter(user=request.user, endpoint=endpoint).delete()
        return Response({"ok": True, "devices": request.user.push_devices.count()})


class PushTest(APIView):
    """Send a test notification to every device this person turned on."""

    def post(self, request):
        if not push.configured():
            raise FlowError("Notifications aren't set up on this server yet.", code="push_off", status=503)
        sent = push.send(request.user, template="push_test", tag="push_test",
                         body="You'll get a notification like this when money is sent or added.")
        if not sent:
            raise FlowError("We couldn't reach this phone. Turn notifications off and on again.", code="push_failed")
        return Response({"ok": True, "sent": sent})
