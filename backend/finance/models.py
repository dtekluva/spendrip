from django.conf import settings
from django.db import models


class FinanceProfile(models.Model):
    """What the person tells us for their Finance report."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="finance")
    salary_kobo = models.BigIntegerField(null=True, blank=True)  # monthly take-home pay, optional
    dismissed = models.JSONField(default=list, blank=True)  # report cards the person said "not for me" to, e.g. ["missing:housing"]
    updated_at = models.DateTimeField(auto_now=True)


class Expense(models.Model):
    """A regular cost paid outside SpenDrip (rent to the landlord once a year, market by hand), so the report sees it."""

    class Every(models.TextChoices):
        WEEK = "week"
        MONTH = "month"
        YEAR = "year"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expenses")
    label = models.CharField(max_length=40)
    category = models.CharField(max_length=16)
    amount_kobo = models.BigIntegerField()
    every = models.CharField(max_length=5, choices=Every.choices, default=Every.MONTH)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def monthly_kobo(self) -> int:
        return {"week": round(self.amount_kobo * 52 / 12), "month": self.amount_kobo, "year": round(self.amount_kobo / 12)}[self.every]


class FinanceSnapshot(models.Model):
    """AI-written summary, suggestions and category guesses, cached per person until their numbers change."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="finance_snapshots")
    month = models.CharField(max_length=7)
    facts_hash = models.CharField(max_length=64)
    ai = models.JSONField(default=dict)  # {"summary": str, "suggestions": [...], "categories": {plan_id: key}}
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "-created_at"])]


class SavingsOption(models.Model):
    """General information about ways to save in Nigeria, kept up to date by SpenDrip. Not advice; never ranked."""

    name = models.CharField(max_length=60)
    kind = models.CharField(max_length=40, help_text="e.g. Government security, Money market fund, Savings account")
    summary = models.CharField(max_length=240)
    rate_text = models.CharField(max_length=60, blank=True, help_text="e.g. '17.5% a year'. Leave blank until checked.")
    checked_on = models.DateField(null=True, blank=True, help_text="When the rate was last checked against the source.")
    source_name = models.CharField(max_length=60, blank=True)
    source_url = models.URLField(blank=True)
    risk = models.CharField(max_length=60, blank=True, help_text="e.g. 'Low: backed by the Federal Government'")
    access = models.CharField(max_length=80, blank=True, help_text="e.g. 'Locked for 91 days' or 'Withdraw any time'")
    order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name
