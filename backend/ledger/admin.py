from django.contrib import admin

from .models import FundingAccount, Inflow, LedgerAccount, LedgerEntry, LedgerTransaction


class EntryInline(admin.TabularInline):
    model = LedgerEntry
    extra = 0
    can_delete = False
    readonly_fields = ("account", "amount_kobo")


@admin.register(LedgerTransaction)
class LedgerTransactionAdmin(admin.ModelAdmin):
    list_display = ("idempotency_key", "kind", "created_at")
    inlines = [EntryInline]

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(LedgerAccount)
admin.site.register(FundingAccount)
admin.site.register(Inflow)


# ---------------------------------------------------------------- fees

import csv  # noqa: E402

from django.db.models import Count, Sum  # noqa: E402
from django.http import HttpResponse  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.utils.html import format_html  # noqa: E402

from .models import CardCharge, FeeLine  # noqa: E402


def _naira(kobo):
    return f"₦{(kobo or 0) / 100:,.2f}"


@admin.register(FeeLine)
class FeeLineAdmin(admin.ModelAdmin):
    """Every fee, where it came from and where it was posted. Read-only: fees are written by the ledger."""

    list_display = ("created_at", "kind", "amount", "paid_to", "user", "origin", "posting", "reference")
    list_filter = ("kind", "paid_to", "provider", ("created_at", admin.DateFieldListFilter))
    date_hierarchy = "created_at"
    search_fields = ("reference", "user__email", "user__first_name", "user__last_name", "run__plan__label")
    list_select_related = ("user", "run__plan", "card_charge", "ledger_transaction")
    actions = ["export_csv"]

    @admin.display(description="Amount", ordering="amount_kobo")
    def amount(self, obj):
        return _naira(obj.amount_kobo)

    @admin.display(description="From")
    def origin(self, obj):
        if obj.run_id:
            url = reverse("admin:drips_run_change", args=[obj.run_id])
            return format_html('<a href="{}">Drip: {} {}</a>', url, obj.run.plan.label, _naira(obj.run.amount_kobo))
        if obj.card_charge_id:
            return f"Card top-up {_naira(obj.card_charge.net_kobo)}"
        return "—"

    @admin.display(description="Ledger posting")
    def posting(self, obj):
        if not obj.ledger_transaction_id:
            return "—"
        url = reverse("admin:ledger_ledgertransaction_change", args=[obj.ledger_transaction_id])
        return format_html('<a href="{}">{}</a>', url, obj.ledger_transaction.idempotency_key)

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        try:
            qs = response.context_data["cl"].queryset
        except (AttributeError, KeyError):
            return response
        rows = qs.values("kind").annotate(total=Sum("amount_kobo"), n=Count("id")).order_by("kind")
        labels = dict(FeeLine.Kind.choices)
        summary = " · ".join(f"{labels.get(r['kind'], r['kind'])}: {_naira(r['total'])} ({r['n']})" for r in rows)
        if summary:
            self.message_user(request, f"Totals for this view — {summary}")
        return response

    @admin.action(description="Export selected fees as CSV")
    def export_csv(self, request, queryset):
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="spendrip-fees.csv"'
        w = csv.writer(resp)
        w.writerow(["created_at", "kind", "amount_naira", "paid_to", "user_email", "run_id", "plan", "card_charge", "ledger_key", "account", "reference"])
        for f in queryset.select_related("user", "run__plan", "card_charge", "ledger_transaction"):
            w.writerow([f.created_at.isoformat(), f.kind, f"{f.amount_kobo / 100:.2f}", f.paid_to, f.user.email or "",
                        f.run_id or "", f.run.plan.label if f.run_id else "", f.card_charge.reference if f.card_charge_id else "",
                        f.ledger_transaction.idempotency_key if f.ledger_transaction_id else "", f.account_code, f.reference])
        return resp

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CardCharge)
class CardChargeAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "status", "net_kobo", "fee_kobo", "gross_kobo", "reference")
    list_filter = ("status",)
    search_fields = ("reference", "user__email")
    readonly_fields = [f.name for f in CardCharge._meta.fields]

    def has_add_permission(self, request):
        return False
