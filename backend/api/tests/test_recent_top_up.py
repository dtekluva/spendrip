"""A second card top-up within 10 minutes needs a yes first, so a missed confirmation doesn't become a double charge."""
from datetime import timedelta

import pytest
from django.utils import timezone

from api.tests.test_api import demo, dev, unlocked_client  # noqa: F401  (fixtures)
from ledger import cards
from ledger.models import CardCharge, SavedCard
from providers.mock import MockCardGateway


@pytest.fixture
def card(demo, monkeypatch):
    gw = MockCardGateway("http://app.test")
    monkeypatch.setattr(cards, "gateway", lambda: gw)
    cards.complete(cards.start(demo, 10_000, save_card=True)["reference"])  # a ₦100 top-up that saves the card
    return SavedCard.objects.get(user=demo)


def test_second_top_up_within_ten_minutes_asks_first(demo, dev, card):
    c = unlocked_client(demo)
    r = c.post("/api/funding/card/charge", {"card_id": card.id, "amount_kobo": 2_000_000}, format="json")
    assert r.status_code == 409 and r.json()["code"] == "recent_top_up" and "You added ₦100 a minute ago" in r.json()["error"]
    assert c.post("/api/funding/card/start", {"amount_kobo": 2_000_000}, format="json").json()["code"] == "recent_top_up"
    r = c.post("/api/funding/card/charge", {"card_id": card.id, "amount_kobo": 2_000_000, "confirm_again": True}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "success"


def test_older_or_failed_top_ups_dont_ask(demo, dev, card):
    CardCharge.objects.filter(user=demo).update(completed_at=timezone.now() - timedelta(minutes=11))
    CardCharge.objects.create(user=demo, reference="sdc_failed", net_kobo=1, fee_kobo=0, gross_kobo=1, status="failed", completed_at=timezone.now())
    r = unlocked_client(demo).post("/api/funding/card/charge", {"card_id": card.id, "amount_kobo": 2_000_000}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "success"


def test_sign_up_records_the_terms_version(dev, db, settings):
    from rest_framework.test import APIClient
    from accounts.models import User
    c = APIClient()
    r = c.post("/api/signup/start", {"email": "terms@example.com"}, format="json").json()
    c.post("/api/signup/otp/verify", {"code": r["dev_code"]}, format="json")
    u = User.objects.get(email="terms@example.com")
    assert u.terms_version == settings.TERMS_VERSION and u.terms_accepted_at
