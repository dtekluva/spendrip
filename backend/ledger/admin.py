import csv

from django.contrib import admin
from django.http import StreamingHttpResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import FundingAccount, Inflow, LedgerAccount, LedgerEntry, LedgerTransaction


def naira(kobo):
    if kobo is None:
        return "—"
    sign = "−" if kobo < 0 else ""
    return f"{sign}₦{abs(kobo) / 100:,.2f}"


class EntryInline(admin.TabularInline):
    model = LedgerEntry
    extra = 0
    can_delete = False
    fields = ("account", "amount", "before", "after")
    readonly_fields = fields

    @admin.display(description="Amount")
    def amount(self, obj):
        return naira(obj.amount_kobo)

    @admin.display(description="Balance before")
    def before(self, obj):
        return naira(obj.balance_before_kobo)

    @admin.display(description="Balance after")
    def after(self, obj):
        return naira(obj.balance_after_kobo)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LedgerTransaction)
class LedgerTransactionAdmin(admin.ModelAdmin):
    """Each posting, with the user's wallet before and after it."""

    list_display = ("created_at", "kind", "memo", "who", "user_account", "wallet_change", "wallet_before", "wallet_after", "idempotency_key")
    list_filter = ("kind", ("created_at", admin.DateFieldListFilter))
    search_fields = ("idempotency_key", "memo", "entries__account__user__email")
    date_hierarchy = "created_at"
    inlines = [EntryInline]

    def _wallet_entry(self, obj):
        if not hasattr(obj, "_wallet"):
            obj._wallet = next((e for e in obj.entries.select_related("account__user").all() if e.account.kind in ("wallet", "held")
                                and e.account.code.startswith("wallet:")), None) or \
                next((e for e in obj.entries.select_related("account__user").all() if e.account.user_id), None)
        return obj._wallet

    @admin.display(description="User")
    def who(self, obj):
        e = self._wallet_entry(obj)
        return (e.account.user.email or e.account.user.username) if e and e.account.user else "—"

    @admin.display(description="Account")
    def user_account(self, obj):
        e = self._wallet_entry(obj)
        if not e:
            return "—"
        return {"wallet": "Balance", "held": "Set aside"}.get(e.account.kind, e.account.code)

    @admin.display(description="Change")
    def wallet_change(self, obj):
        e = self._wallet_entry(obj)
        return naira(e.amount_kobo) if e else "—"

    @admin.display(description="Before")
    def wallet_before(self, obj):
        e = self._wallet_entry(obj)
        return naira(e.balance_before_kobo) if e else "—"

    @admin.display(description="After")
    def wallet_after(self, obj):
        e = self._wallet_entry(obj)
        return naira(e.balance_after_kobo) if e else "—"

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    """A statement: filter by account to see every movement with the running balance."""

    list_display = ("posted", "account", "posting", "memo", "amount", "before", "after")
    list_filter = ("account__kind", "transaction__kind")
    search_fields = ("account__code", "account__user__email", "transaction__idempotency_key", "transaction__memo")
    list_select_related = ("account", "transaction")
    ordering = ("-transaction__created_at", "-id")
    actions = ["export_csv"]

    CSV_HEADER = ["posted_at", "account", "account_kind", "user_email", "posting_key", "posting_kind", "memo", "run_id",
                  "amount_naira", "balance_before_naira", "balance_after_naira"]

    @staticmethod
    def _n(kobo):
        return "" if kobo is None else f"{kobo / 100:.2f}"

    def _csv_response(self, queryset, name):
        class Echo:
            def write(self, value):
                return value
        w = csv.writer(Echo())

        def rows():
            yield w.writerow(self.CSV_HEADER)
            qs = queryset.select_related("account__user", "transaction").order_by("transaction__created_at", "id")
            for e in qs.iterator(chunk_size=2000):
                u = e.account.user
                yield w.writerow([e.transaction.created_at.isoformat(), e.account.code, e.account.kind, (u.email or u.username) if u else "",
                                  e.transaction.idempotency_key, e.transaction.kind, e.transaction.memo, e.transaction.run_id or "",
                                  self._n(e.amount_kobo), self._n(e.balance_before_kobo), self._n(e.balance_after_kobo)])
        resp = StreamingHttpResponse(rows(), content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{name}-{timezone.now():%Y%m%d-%H%M}.csv"'
        return resp

    @admin.action(description="Export selected entries as CSV")
    def export_csv(self, request, queryset):
        return self._csv_response(queryset, "spendrip-ledger")

    def get_urls(self):
        return [path("export/", self.admin_site.admin_view(self.export_view), name="ledger_ledgerentry_export")] + super().get_urls()

    def export_view(self, request):
        """Everything matching the filters and search currently applied to the statement."""
        cl = self.get_changelist_instance(request)
        account = request.GET.get("account__id__exact")
        code = LedgerAccount.objects.filter(pk=account).values_list("code", flat=True).first() if account else None
        return self._csv_response(cl.get_queryset(request), f"statement-{code.replace(':', '-')}" if code else "spendrip-ledger")

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        try:
            n = response.context_data["cl"].result_count
        except (AttributeError, KeyError):
            return response
        url = reverse("admin:ledger_ledgerentry_export") + (f"?{request.GET.urlencode()}" if request.GET else "")
        self.message_user(request, format_html('<a href="{}"><b>Download CSV</b></a> of the {} entries in this view.', url, n))
        return response

    @admin.display(description="Posted", ordering="transaction__created_at")
    def posted(self, obj):
        return obj.transaction.created_at

    @admin.display(description="Posting")
    def posting(self, obj):
        url = reverse("admin:ledger_ledgertransaction_change", args=[obj.transaction_id])
        return format_html('<a href="{}">{}</a>', url, obj.transaction.idempotency_key)

    @admin.display(description="Memo")
    def memo(self, obj):
        return obj.transaction.memo

    @admin.display(description="Amount", ordering="amount_kobo")
    def amount(self, obj):
        return naira(obj.amount_kobo)

    @admin.display(description="Balance before")
    def before(self, obj):
        return naira(obj.balance_before_kobo)

    @admin.display(description="Balance after")
    def after(self, obj):
        return naira(obj.balance_after_kobo)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerAccount)
class LedgerAccountAdmin(admin.ModelAdmin):
    list_display = ("code", "kind", "user", "balance", "statement")
    list_filter = ("kind",)
    search_fields = ("code", "user__email")
    readonly_fields = ("code", "kind", "user", "balance_kobo", "created_at")

    @admin.display(description="Balance", ordering="balance_kobo")
    def balance(self, obj):
        return naira(obj.balance_kobo)

    @admin.display(description="")
    def statement(self, obj):
        url = reverse("admin:ledger_ledgerentry_changelist") + f"?account__id__exact={obj.pk}"
        return format_html('<a href="{}">Statement →</a>', url)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(FundingAccount)
admin.site.register(Inflow)


# ---------------------------------------------------------------- fees

import csv  # noqa: E402

from django.db.models import Count, Sum  # noqa: E402
from django.http import HttpResponse  # noqa: E402

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
