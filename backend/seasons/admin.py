from django.contrib import admin
from django.utils import timezone

from .models import Season


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ("__str__", "outfit", "starts_on", "ends_on", "active", "live_now")
    list_filter = ("active", "outfit")
    list_editable = ("active",)
    date_hierarchy = "starts_on"

    @admin.display(boolean=True, description="Live now")
    def live_now(self, obj):
        return obj.is_live

    def changelist_view(self, request, extra_context=None):
        live = Season.current()
        extra_context = {**(extra_context or {}), "title": f"Seasons · on today ({timezone.localdate():%-d %b}): "
                         + (live.get_outfit_display() if live else "no outfit, plain Kobo")}
        return super().changelist_view(request, extra_context)
