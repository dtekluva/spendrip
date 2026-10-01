from django.contrib import admin

from .models import OutboxMessage


@admin.register(OutboxMessage)
class OutboxAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "channel", "template", "status", "to")
    list_filter = ("channel", "status", "template")
