from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import KycCheck, User, WaitlistEntry


@admin.register(User)
class SpenDripUserAdmin(UserAdmin):
    list_display = ("username", "phone", "first_name", "last_name", "kyc_status", "paused_all")
    fieldsets = UserAdmin.fieldsets + (
        ("SpenDrip", {"fields": ("phone", "kyc_status", "nin_last4", "tz", "daily_cap_kobo", "paused_all", "look")}),
    )


admin.site.register(KycCheck)


@admin.register(WaitlistEntry)
class WaitlistAdmin(admin.ModelAdmin):
    list_display = ("created_at", "name", "contact", "kind", "source", "invited_at")
    list_filter = ("kind", "source")
    search_fields = ("contact", "name")
