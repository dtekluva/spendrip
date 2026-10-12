"""
SpenDrip Pays It Forward: each month, people share who they look after; one story wins ₦50,000 for that person's drips.
See docs/plans/monthly-boost.md. Off unless settings.BOOST_ENABLED.
"""
from django.conf import settings
from django.db import models


class BoostMonth(models.Model):
    class Status(models.TextChoices):
        OPEN = "open"
        DRAWN = "drawn"
        PAID = "paid"

    month = models.CharField(max_length=7, unique=True)  # the month entries are for, e.g. 2026-11
    prize_kobo = models.BigIntegerField(default=5_000_000)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    public_value = models.CharField(max_length=120, blank=True, help_text="A value published before the draw (e.g. that day's "
                                    "closing NGX All-Share index), so anyone can check the draw wasn't chosen.")
    seed = models.CharField(max_length=64, blank=True)
    pool_size = models.PositiveIntegerField(default=0)
    pool_ids = models.JSONField(default=list, blank=True)  # the entries in the draw, in order, for the audit
    winner = models.ForeignKey("BoostEntry", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    drawn_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    inflow = models.OneToOneField("ledger.Inflow", null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    def __str__(self):
        return f"Pays it forward {self.month}"


class BoostEntry(models.Model):
    month = models.ForeignKey(BoostMonth, on_delete=models.CASCADE, related_name="entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="boost_entries")
    recipient = models.ForeignKey("drips.Recipient", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    story = models.TextField(max_length=500)
    consent_publish = models.BooleanField(default=False)  # may we share their first name and story (never account details)
    shortlisted = models.BooleanField(default=False, help_text="Tick the best stories. The draw picks from these "
                                      "(or from every entry if none are ticked).")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["month", "user"], name="boost_one_entry_per_month")]
        verbose_name_plural = "boost entries"

    def __str__(self):
        return f"{self.user.first_name.title()} → {self.recipient.label if self.recipient else '?'} ({self.month.month})"
