from django.contrib import admin

from .models import BoostEntry, BoostMonth


@admin.register(BoostMonth)
class BoostMonthAdmin(admin.ModelAdmin):
    list_display = ("month", "status", "prize_kobo", "pool_size", "winner", "drawn_at", "paid_at")
    readonly_fields = ("seed", "pool_ids", "pool_size", "winner", "drawn_at", "paid_at", "inflow")


@admin.register(BoostEntry)
class BoostEntryAdmin(admin.ModelAdmin):
    list_display = ("__str__", "story", "consent_publish", "shortlisted", "created_at")
    list_editable = ("shortlisted",)
    list_filter = ("month", "shortlisted", "consent_publish")
    search_fields = ("story", "user__email", "user__first_name")
    readonly_fields = ("month", "user", "recipient", "story", "consent_publish", "created_at", "updated_at")
