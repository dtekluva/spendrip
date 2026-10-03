from django.contrib import admin

from .models import Plan, PlanLine, Recipient, Run, RunBatch


class PlanLineInline(admin.TabularInline):
    model = PlanLine
    extra = 0
    fields = ("position", "recipient", "amount_kobo", "next_amount_kobo", "skip_next", "active")
    raw_id_fields = ("recipient",)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "kind", "amount_kobo", "frequency", "time_local", "priority_rank", "status")
    list_filter = ("status", "kind", "frequency")
    inlines = [PlanLineInline]


class BatchRunInline(admin.TabularInline):
    model = Run
    fk_name = "batch"
    extra = 0
    fields = ("line", "amount_kobo", "fee_kobo", "status", "provider_ref", "last_error")
    readonly_fields = fields
    can_delete = False


@admin.register(RunBatch)
class RunBatchAdmin(admin.ModelAdmin):
    """Group payouts: one row per payout, with each person's transfer inside."""
    list_display = ("plan", "user", "scheduled_for", "status", "amount_kobo", "fee_kobo", "reason", "short_by_kobo")
    list_filter = ("status",)
    inlines = [BatchRunInline]


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ("id", "plan", "line", "scheduled_for", "amount_kobo", "status", "needs_review")
    list_filter = ("status", "needs_review")


admin.site.register(Recipient)
