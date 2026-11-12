from django.contrib import admin

from .models import OutboxMessage, PushDevice


@admin.register(OutboxMessage)
class OutboxAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "channel", "template", "status", "to")
    list_filter = ("channel", "status", "template")


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "last_sent_at", "failures", "user_agent")
    readonly_fields = ("endpoint", "p256dh", "auth")
