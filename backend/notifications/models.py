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
