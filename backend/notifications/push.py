"""
Web push: notifications on the phones and computers where someone turned them on in the app.

The browser gives us a subscription (an address at Google's, Apple's or Mozilla's push service, plus keys); we encrypt a
small JSON message for it and sign the request with our VAPID key. The app's service worker (frontend/public/push-sw.js)
shows it and opens the right screen when it's tapped. On iPhone this only works once SpenDrip is on the home screen.
"""
import json
import logging

from django.conf import settings
from django.utils import timezone

from .models import PushDevice

log = logging.getLogger(__name__)

# Title and the screen a tap opens, per message template. The message itself is the notification's text.
SCREENS = {
    "self_paid": ("Money sent", "/activity"),
    "self_skipped": ("A drip is waiting", "/fund"),
    "self_missed": ("A drip was missed", "/activity"),
    "self_failed": ("A payment didn't go through", "/activity"),
    "self_slow": ("Still checking with the bank", "/activity"),
    "self_topped_up": ("Money added", "/"),
    "group_done": ("Group payout done", "/activity"),
    "group_waiting": ("A group payout is waiting", "/fund"),
    "group_skipped": ("A group payout didn't go out", "/activity"),
    "low_balance_ahead": ("Top up before tomorrow", "/fund"),
    "boost_won": ("You won Pays it forward", "/"),
    "daily_summary": ("Tomorrow's drips", "/calendar"),
    "daily_summary_short": ("Tomorrow's drips", "/fund"),
    "daily_summary_cap": ("Tomorrow's drips", "/settings"),
    "push_test": ("Notifications are on", "/settings"),
}
AUTOFILL = ("Auto-fill", "/autofill")
DROP_AFTER = 3   # failed sends in a row before we forget a device (a gone subscription is dropped at once)
TTL = 12 * 3600  # a message the phone can't take within 12 hours is no longer news


def configured() -> bool:
    return bool(settings.WEB_PUSH["PUBLIC_KEY"] and settings.WEB_PUSH["PRIVATE_KEY"])


def payload(template: str, body: str, tag: str = "") -> dict:
    title, url = SCREENS.get(template) or (AUTOFILL if template.startswith("autofill") else ("SpenDrip", "/"))
    return {"title": title, "body": body, "url": url, "tag": tag or template}


def send(user, *, template: str, body: str, tag: str = "") -> int:
    """Send to every device the person turned on. Returns how many took it."""
    if not configured():
        return 0
    from pywebpush import WebPushException, webpush

    data = json.dumps(payload(template, body, tag))
    ok = 0
    for d in list(user.push_devices.all()):
        try:
            webpush({"endpoint": d.endpoint, "keys": {"p256dh": d.p256dh, "auth": d.auth}}, data=data,
                    vapid_private_key=settings.WEB_PUSH["PRIVATE_KEY"], vapid_claims={"sub": settings.WEB_PUSH["SUBJECT"]},
                    ttl=TTL, headers={"Urgency": "high"}, timeout=8)
        except WebPushException as e:
            code = getattr(e.response, "status_code", None)
            if code in (404, 410):  # unsubscribed, or the app was removed: this address is gone for good
                d.delete()
                continue
            log.warning("push to %s failed: %s", d, code or e)
            d.failures += 1
            if d.failures >= DROP_AFTER:
                d.delete()
            else:
                d.save(update_fields=["failures"])
            continue
        except Exception as e:  # network trouble: try again next message
            log.warning("push to %s failed: %s", d, e)
            continue
        d.failures, d.last_sent_at = 0, timezone.now()
        d.save(update_fields=["failures", "last_sent_at"])
        ok += 1
    return ok
