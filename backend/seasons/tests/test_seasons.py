from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from seasons.models import Season


@pytest.mark.django_db
def test_no_season_means_plain_kobo():
    r = APIClient().get("/api/season")
    assert r.status_code == 200 and r.json() == {"outfit": None, "until": None}


@pytest.mark.django_db
def test_a_live_season_is_returned_with_its_last_day():
    today = timezone.localdate()
    Season.objects.create(outfit="xmas", starts_on=today - timedelta(days=1), ends_on=today + timedelta(days=2))
    r = APIClient().get("/api/season").json()
    assert r == {"outfit": "xmas", "until": (today + timedelta(days=2)).isoformat()}


@pytest.mark.django_db
def test_switched_off_past_and_future_seasons_are_ignored():
    today = timezone.localdate()
    Season.objects.create(outfit="xmas", starts_on=today, ends_on=today, active=False)
    Season.objects.create(outfit="easter", starts_on=today - timedelta(days=9), ends_on=today - timedelta(days=1))
    Season.objects.create(outfit="naija", starts_on=today + timedelta(days=1), ends_on=today + timedelta(days=3))
    assert Season.current() is None


@pytest.mark.django_db
def test_the_more_recent_start_wins_when_two_overlap():
    Season.objects.create(outfit="xmas", starts_on=date(2026, 12, 1), ends_on=date(2026, 12, 31))
    Season.objects.create(outfit="newyear", starts_on=date(2026, 12, 30), ends_on=date(2027, 1, 2))
    assert Season.current(date(2026, 12, 25)).outfit == "xmas"
    assert Season.current(date(2026, 12, 31)).outfit == "newyear"
    assert Season.current(date(2027, 1, 2)).outfit == "newyear"
    assert Season.current(date(2027, 1, 3)) is None


@pytest.mark.django_db
def test_end_before_start_is_refused():
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        Season.objects.create(outfit="xmas", starts_on=date(2026, 12, 26), ends_on=date(2026, 12, 20))


@pytest.mark.django_db
def test_seed_adds_the_calendar_switched_off_and_is_safe_to_rerun():
    from django.core.management import call_command
    call_command("seed_seasons")
    n = Season.objects.count()
    call_command("seed_seasons")
    assert Season.objects.count() == n >= 14
    assert not Season.objects.filter(active=True).exists()
    assert Season.current(date(2026, 12, 25)) is None  # nothing is on until it's ticked
