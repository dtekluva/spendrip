from django.contrib import admin, messages
from django.utils import timezone
from django.contrib.auth.admin import UserAdmin

from .models import KycCheck, User, WaitlistEntry


@admin.register(User)
class SpenDripUserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "kyc_status", "signup_source", "signup_landing", "date_joined")
    list_filter = ("kyc_status", "signup_source")
    fieldsets = UserAdmin.fieldsets + (
        ("SpenDrip", {"fields": ("phone", "kyc_status", "nin_last4", "tz", "daily_cap_kobo", "paused_all", "look")}),
        ("Where they came from", {"fields": ("signup_source", "signup_landing")}),
    )


admin.site.register(KycCheck)


@admin.register(WaitlistEntry)
class WaitlistAdmin(admin.ModelAdmin):
    list_display = ("created_at", "name", "contact", "kind", "source", "invited_at")
    list_filter = ("kind", "source")
    search_fields = ("contact", "name")
    actions = ["send_invites"]

    @admin.action(description="Email an invite to the selected people")
    def send_invites(self, request, queryset):
        from notifications.emails import waitlist_invite
        sent = skipped = failed = 0
        for entry in queryset:
            if entry.kind != "email":
                skipped += 1
            elif waitlist_invite(entry):
                entry.invited_at = timezone.now()
                entry.save(update_fields=["invited_at"])
                sent += 1
            else:
                failed += 1
        self.message_user(request, f"Invites sent: {sent}. Phone numbers skipped: {skipped}. Failed: {failed}.",
                          messages.WARNING if failed else messages.SUCCESS)
