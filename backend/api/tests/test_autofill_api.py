"""Auto-fill through the API: turning it on needs the PIN, turning it off doesn't, skip and fill now."""
import pytest

from api.tests.test_api import demo, dev, unlocked_client  # noqa: F401  (fixtures)
from drips.models import AutoFill
from ledger import cards
from ledger.models import SavedCard
from notifications.models import OutboxMessage
from providers.mock import MockCardGateway


@pytest.fixture
def card(demo, monkeypatch, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    gw = MockCardGateway("http://app.test")
    monkeypatch.setattr(cards, "gateway", lambda: gw)
    cards.complete(cards.start(demo, 10_000, save_card=True)["reference"])
    c = SavedCard.objects.get(user=demo)
    c.exp_month, c.exp_year = "12", "2030"
    c.save()
    return c


def body(card, **kw):
    return {"card_id": card.id, "payday_end": True, "payday_start": False, "just_in_time": True,
            "max_per_charge_kobo": 25_000_000, "max_per_month_kobo": 40_000_000, "pin": "2580", **kw}


def test_turning_on_needs_the_pin_and_emails_the_consent(demo, dev, card):
    c = unlocked_client(demo)
    off = c.get("/api/autofill").json()
    assert off["active"] is False and off["suggested"]["max_per_charge_kobo"] > 0
    r = c.put("/api/autofill", body(card, pin="0000"), format="json")
    assert r.status_code == 400 and r.json()["code"] == "pin_wrong"
    r = c.put("/api/autofill", body(card), format="json")
    assert r.status_code == 200, r.json()
    on = r.json()
    assert on["active"] and on["card"]["last4"] == card.last4 and "up to ₦250,000 per charge" in on["consent_text"]
    assert OutboxMessage.objects.filter(user=demo, template="autofill_on", channel="email").exists()


def test_bad_settings_are_refused(demo, dev, card):
    c = unlocked_client(demo)
    assert c.put("/api/autofill", body(card, payday_end=False, just_in_time=False), format="json").status_code == 400
    assert c.put("/api/autofill", body(card, max_per_month_kobo=1_000_000), format="json").status_code == 400
    assert c.put("/api/autofill", body(card, card_id=999), format="json").json()["code"] == "no_card"


def test_off_needs_no_pin_and_skip_toggles(demo, dev, card):
    c = unlocked_client(demo)
    c.put("/api/autofill", body(card), format="json")
    skipped = c.post("/api/autofill/skip", {}, format="json").json()
    assert skipped["skip_window"]
    assert c.post("/api/autofill/skip", {"undo": True}, format="json").json()["skip_window"] == ""
    assert c.post("/api/autofill/off", {}, format="json").json()["active"] is False
    assert AutoFill.objects.get(user=demo).active is False


def test_fill_now(demo, dev, card):
    c = unlocked_client(demo)
    c.put("/api/autofill", body(card), format="json")
    r = c.post("/api/autofill/fill-now", {}, format="json")
    assert r.status_code in (200, 400)  # depends on whether the demo's balance already covers its drips
    if r.status_code == 200:
        assert r.json()["status"] == "success" and r.json()["autofill"]["history"][0]["status"] == "success"
    else:
        assert r.json()["code"] in ("nothing_needed", "over_limit")
