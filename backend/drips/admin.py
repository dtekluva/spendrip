from django.contrib import admin

from .models import Plan, Recipient, Run


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "amount_kobo", "frequency", "time_local", "priority_rank", "status")
    list_filter = ("status", "frequency")


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ("id", "plan", "scheduled_for", "amount_kobo", "status", "needs_review")
    list_filter = ("status", "needs_review")


admin.site.register(Recipient)
