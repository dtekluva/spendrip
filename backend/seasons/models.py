from datetime import date

from django.db import models
from django.db.models import Q
from django.utils import timezone


class Season(models.Model):
    """
    When Kobo wears an outfit in the app. Add a row with dates and every Kobo puts it on for those days
    (Lagos time), then takes it off. No app release needed: the app asks which outfit is on.
    """

    class Outfit(models.TextChoices):
        # Nigeria
        XMAS = "xmas", "Christmas: Santa hat"
        NEWYEAR = "newyear", "New Year: party hat"
        LOVE = "love", "Valentine's: heart boppers"
        MAMA = "mama", "Mothering Sunday: gele"
        SALLAH = "sallah", "Sallah (Eid): kufi cap"
        EASTER = "easter", "Easter: bunny ears"
        NAIJA = "naija", "Independence Day: flag and rosette"
        # United States
        HALLOWEEN = "halloween", "Halloween (US): witch hat"
        THANKSGIVING = "thanksgiving", "Thanksgiving (US): knitted beanie"
        STPATRICK = "stpatrick", "St Patrick's Day (US): green top hat"
        USMOM = "usmom", "Mother's Day (US): flower crown"
        JUNETEENTH = "juneteenth", "Juneteenth (US): Juneteenth flag"
        JULY4 = "july4", "Fourth of July (US): stars-and-stripes hat"

    outfit = models.CharField(max_length=20, choices=Outfit.choices)
    name = models.CharField(max_length=60, blank=True, help_text="Optional, e.g. “Christmas 2026”. Shown only here.")
    starts_on = models.DateField(help_text="First day Kobo wears it (Lagos time).")
    ends_on = models.DateField(help_text="Last day Kobo wears it, inclusive.")
    active = models.BooleanField(default=True, help_text="Untick to switch it off without deleting it.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_on"]
        constraints = [models.CheckConstraint(condition=Q(ends_on__gte=models.F("starts_on")), name="season_ends_after_start")]

    def __str__(self):
        return self.name or f"{self.get_outfit_display()} ({self.starts_on:%-d %b} – {self.ends_on:%-d %b %Y})"

    @property
    def is_live(self) -> bool:
        today = timezone.localdate()
        return self.active and self.starts_on <= today <= self.ends_on

    @classmethod
    def current(cls, on: date | None = None) -> "Season | None":
        """The outfit on today. If two overlap, the one that started most recently wins (it's the more specific one)."""
        on = on or timezone.localdate()
        return cls.objects.filter(active=True, starts_on__lte=on, ends_on__gte=on).order_by("-starts_on", "-created_at").first()
