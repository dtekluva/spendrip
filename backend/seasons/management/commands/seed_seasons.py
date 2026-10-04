"""
Fill the Seasons calendar for the coming year, every row switched OFF. Tick "active" in the admin to use one.
Safe to run again: an outfit already entered with the same start date is left alone.

    python manage.py seed_seasons
"""
from datetime import date

from django.core.management.base import BaseCommand

from seasons.models import Season

CALENDAR = [
    # (outfit, name, first day, last day)
    ("halloween", "Halloween 2026 (US)", date(2026, 10, 29), date(2026, 10, 31)),
    ("thanksgiving", "Thanksgiving 2026 (US)", date(2026, 11, 24), date(2026, 11, 27)),
    ("xmas", "Christmas 2026", date(2026, 12, 20), date(2026, 12, 26)),
    ("newyear", "New Year 2027", date(2026, 12, 31), date(2027, 1, 2)),
    ("love", "Valentine's 2027", date(2027, 2, 12), date(2027, 2, 14)),
    ("mama", "Mothering Sunday 2027", date(2027, 3, 5), date(2027, 3, 7)),
    ("sallah", "Eid al-Fitr 2027 (move to the moon-sighted date)", date(2027, 3, 9), date(2027, 3, 12)),
    ("stpatrick", "St Patrick's Day 2027 (US)", date(2027, 3, 15), date(2027, 3, 17)),
    ("easter", "Easter 2027", date(2027, 3, 26), date(2027, 3, 29)),
    ("usmom", "Mother's Day 2027 (US)", date(2027, 5, 7), date(2027, 5, 9)),
    ("sallah", "Eid al-Adha 2027 (move to the moon-sighted date)", date(2027, 5, 15), date(2027, 5, 18)),
    ("juneteenth", "Juneteenth 2027 (US)", date(2027, 6, 18), date(2027, 6, 19)),
    ("july4", "Fourth of July 2027 (US)", date(2027, 7, 2), date(2027, 7, 4)),
    ("naija", "Independence Day 2027", date(2027, 9, 29), date(2027, 10, 1)),
]


class Command(BaseCommand):
    help = "Add the coming year's seasons, switched off."

    def handle(self, *args, **opts):
        added = 0
        for outfit, name, start, end in CALENDAR:
            _, created = Season.objects.get_or_create(outfit=outfit, starts_on=start,
                                                      defaults={"name": name, "ends_on": end, "active": False})
            added += created
        self.stdout.write(f"{added} added, {len(CALENDAR) - added} already there. All new rows are switched off.")
