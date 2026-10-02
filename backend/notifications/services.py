from django.db import IntegrityError, transaction

from providers import get_messenger

from .models import OutboxMessage


def notify(user, *, key: str, channel: str, template: str, body: str, to: str = "", run=None, messenger=None,
           email: dict | None = None) -> OutboxMessage | None:
    """Record and send one message, at most once per dedupe key. Returns None if it was already sent."""
    try:
        with transaction.atomic():
            msg = OutboxMessage.objects.create(user=user, channel=channel, template=template, body=body, to=to, run=run, dedupe_key=key)
    except IntegrityError:
        return None
    if channel in (OutboxMessage.Channel.WHATSAPP, OutboxMessage.Channel.SMS):
        status = (messenger or get_messenger()).send(channel=channel, to=to, body=body)
    elif channel == OutboxMessage.Channel.EMAIL:
        from .emails import send, send_raw
        e = email or {}
        ok = (send_raw(to, e["subject"], e.get("text", body), e["html"]) if e.get("html") else
              send(to, e.get("subject", body[:80]), e.get("heading", body[:80]), e.get("paragraphs", [body]), e.get("button")))
        status = OutboxMessage.Status.SENT if ok else OutboxMessage.Status.FAILED
    elif channel == OutboxMessage.Channel.PUSH:
        status = OutboxMessage.Status.MOCKED  # web push arrives with the PWA (Phase 2)
    else:
        status = OutboxMessage.Status.SENT  # in-app: the row itself is the message
    msg.status = status
    msg.save(update_fields=["status"])
    return msg
