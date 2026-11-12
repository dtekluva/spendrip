from django.conf import settings
from django.db import models


class OutboxMessage(models.Model):
    """Every message we send or would send. With the mock messenger, WhatsApp messages land here and show in the app."""

    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp"
        PUSH = "push"
        IN_APP = "in_app"
        SMS = "sms"
        EMAIL = "email"

    class Status(models.TextChoices):
        QUEUED = "queued"
        SENT = "sent"
        MOCKED = "mocked"
        FAILED = "failed"
        SKIPPED = "skipped"  # nowhere to send it: push is off, or no phone or computer has it turned on

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="messages")
    channel = models.CharField(max_length=10, choices=Channel.choices)
    to = models.CharField(max_length=40, blank=True)
    template = models.CharField(max_length=40)
    body = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    dedupe_key = models.CharField(max_length=160, unique=True)
    run = models.ForeignKey("drips.Run", null=True, blank=True, on_delete=models.SET_NULL, related_name="messages")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class PushDevice(models.Model):
    """A phone or computer that turned on notifications (a browser push subscription). One person can have several."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_devices")
    endpoint = models.URLField(max_length=1000, unique=True)  # the push service's address for this device (Google, Apple, Mozilla…)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    failures = models.PositiveSmallIntegerField(default=0)  # in a row; the device is dropped after a few

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} · {self.endpoint.split('/')[2]}"
