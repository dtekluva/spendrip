import logging

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

log = logging.getLogger(__name__)


class MailgunBackend(BaseEmailBackend):
    """Django email backend that sends through Mailgun's HTTP API (/v3/<domain>/messages)."""

    def send_messages(self, email_messages):
        cfg = settings.MAILGUN
        url = f"{cfg['API_BASE']}/v3/{cfg['DOMAIN']}/messages"
        sent = 0
        for msg in email_messages:
            data = {"from": msg.from_email, "to": msg.to, "subject": msg.subject, "text": msg.body}
            if msg.cc:
                data["cc"] = msg.cc
            if msg.bcc:
                data["bcc"] = msg.bcc
            if msg.reply_to:
                data["h:Reply-To"] = ", ".join(msg.reply_to)
            for content, mimetype in getattr(msg, "alternatives", []):
                if mimetype == "text/html":
                    data["html"] = content
            try:
                r = requests.post(url, auth=("api", cfg["API_KEY"]), data=data, timeout=15)
                r.raise_for_status()
                sent += 1
            except requests.RequestException as e:
                body = getattr(getattr(e, "response", None), "text", "")[:300]
                log.warning("mailgun send to %s failed: %s %s", msg.to, e, body)
                if not self.fail_silently:
                    raise
        return sent
