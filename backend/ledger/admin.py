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
