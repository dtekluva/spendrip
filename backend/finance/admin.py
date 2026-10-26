from django.contrib import admin

from .models import Expense, FinanceProfile, SavingsOption


@admin.register(SavingsOption)
class SavingsOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "rate_text", "checked_on", "active", "order")
    list_editable = ("rate_text", "checked_on", "active", "order")


admin.site.register(FinanceProfile)
admin.site.register(Expense)
