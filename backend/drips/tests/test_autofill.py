"""Auto-fill: payday fills, the just-in-time safety net, limits, pausing, and the API."""
from datetime import date

import pytest

from conftest import lagos
from drips import autofill
from drips.models import AutoFill, AutoFillAttempt
from drips.reminders import day_ahead
from engine import naira
from ledger import cards
from ledger import services as ledger
from ledger.models import SavedCard
from notifications.models import OutboxMessage
from providers.mock import MockCardGateway


@pytest.fixture(autouse=True)
def gateway(monkeypatch, settings, user):
    settings.PAYSTACK = {**settings.PAYSTACK, "PASS_CARD_FEES": True}
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user.email = "ada@example.com"
    user.save()
    gw = MockCardGateway("http://app.test")
    monkeypatch.setattr(cards, "gateway", lambda: gw)
    return gw


@pytest.fixture
def card(user):
    cards.complete(cards.start(user, 10_000, save_card=True)["reference"])  # a ₦100 top-up that saves the card
    c = SavedCard.objects.get(user=user)
    c.exp_month, c.exp_year = "12", "2030"
    c.save()
    return c


@pytest.fixture
def af(user, card):
    return AutoFill.objects.create(user=user, card=card, active=True, payday_end=True, just_in_time=False,  # one part at a time
                                   max_per_charge_kobo=naira(500_000), max_per_month_kobo=naira(1_000_000))


def decline(gw, monkeypatch, message="Insufficient Funds"):
    monkeypatch.setattr(gw, "charge_authorization", lambda **kw: {"status": "failed", "amount_kobo": kw["amount_kobo"], "currency": "NGN",
                                                                  "reference": kw["reference"], "message": message, "authorization": None})


def bal(user):
    return ledger.balance(user).available_kobo


# ---------------------------------------------------------------- windows

def test_windows_are_the_last_five_days_and_the_first_five():
    a = AutoFill(payday_end=True, payday_start=False)
    assert autofill.window_key(date(2026, 10, 26), a) is None
    assert autofill.window_key(date(2026, 10, 27), a) == "2026-10-end"
    assert autofill.window_key(date(2027, 2, 24), a) == "2027-02-end"  # February: 24th to 28th
    assert autofill.window_key(date(2026, 11, 3), a) is None
    b = AutoFill(payday_end=True, payday_start=True)
    assert autofill.window_key(date(2026, 11, 3), b) == "2026-11-start"
    assert autofill.next_window_start(lagos("2026-10-27T10:00"), a) == lagos("2026-11-26T10:00")
    assert autofill.next_window_start(lagos("2026-10-27T10:00"), b) == lagos("2026-11-01T10:00")
    assert autofill.next_window_start(lagos("2026-11-02T10:00"), b) == lagos("2026-11-26T10:00")


# ---------------------------------------------------------------- payday fill

def test_payday_fill_warns_first_then_charges_what_the_month_needs(user, af, recipients, make_plan):
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=28)
    make_plan("Fuel", 12_000, recipients["me"], frequency="weekly", weekday=5)
    start = bal(user)
    assert autofill.run(lagos("2026-10-26T12:00")) == {"payday": 0, "jit": 0}  # not a window day
    autofill.run(lagos("2026-10-27T07:05"))
    assert OutboxMessage.objects.filter(template="autofill_heads_up", channel="email").count() == 1
    assert autofill.run(lagos("2026-10-27T08:00"))["payday"] == 0  # not before 10 AM
    assert autofill.run(lagos("2026-10-27T10:00"))["payday"] == 1
    # Until 26 Nov 10 AM: Mum on 28 Oct, Fridays 30 Oct, 6, 13, 20 Nov = ₦30,050 + 4 × ₦12,050 = ₦78,250, less the ₦100 held → ₦78,500
    assert bal(user) - start == naira(78_500)
    assert autofill.run(lagos("2026-10-28T10:00"))["payday"] == 0  # once per window
    assert OutboxMessage.objects.filter(template="autofill_done", channel="email").count() == 1


def test_mid_window_switch_on_charges_two_hours_after_the_heads_up(user, af, recipients, make_plan):
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=28)
    autofill.run(lagos("2026-10-27T15:00"))
    assert autofill.run(lagos("2026-10-27T16:00"))["payday"] == 0
    assert autofill.run(lagos("2026-10-27T17:00"))["payday"] == 1


def test_nothing_is_charged_when_the_balance_covers_it(user, af, top_up, recipients, make_plan):
    top_up(100_000)
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=28)
    autofill.run(lagos("2026-10-27T07:05"))
    autofill.run(lagos("2026-10-27T10:00"))
    assert not OutboxMessage.objects.filter(template="autofill_heads_up").exists()
    assert AutoFillAttempt.objects.get(user=user).status == "not_needed"


def test_declined_payday_tries_once_a_day_three_times_then_pauses_after_two_windows(user, af, gateway, monkeypatch, recipients, make_plan):
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=30)  # still ahead on every try
    decline(gateway, monkeypatch)
    for day in (27, 28, 29):
        autofill.run(lagos(f"2026-10-{day}T07:00"))
        autofill.run(lagos(f"2026-10-{day}T10:00"))
        autofill.run(lagos(f"2026-10-{day}T12:00"))  # never twice a day
    assert AutoFillAttempt.objects.filter(user=user, key="2026-10-end").count() == 3
    autofill.run(lagos("2026-10-30T10:00"))
    assert AutoFillAttempt.objects.filter(user=user, key="2026-10-end").count() == 3  # no fourth try
    assert OutboxMessage.objects.filter(template="autofill_window_failed", channel="email").count() == 1
    af.refresh_from_db()
    assert af.failed_windows == 1 and af.paused_reason == ""
    for day in (26, 27, 28):  # November's window fails too
        autofill.run(lagos(f"2026-11-{day}T07:00"))
        autofill.run(lagos(f"2026-11-{day}T10:00"))
    af.refresh_from_db()
    assert af.paused_reason == "declines"
    assert OutboxMessage.objects.filter(template="autofill_paused", channel="email").count() == 1


def test_a_success_resets_the_failed_windows(user, af, recipients, make_plan):
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=28)
    af.failed_windows = 1
    af.save()
    autofill.run(lagos("2026-10-27T07:00"))
    autofill.run(lagos("2026-10-27T10:00"))
    af.refresh_from_db()
    assert af.failed_windows == 0


def test_a_card_that_needs_a_code_pauses_auto_fill(user, af, gateway, monkeypatch, recipients, make_plan):
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=28)
    monkeypatch.setattr(gateway, "charge_authorization", lambda **kw: {"status": "send_otp", "amount_kobo": kw["amount_kobo"],
                                                                       "currency": "NGN", "reference": kw["reference"], "message": ""})
    monkeypatch.setattr(gateway, "verify", lambda ref: {"status": "send_otp"})
    autofill.run(lagos("2026-10-27T07:00"))
    autofill.run(lagos("2026-10-27T10:00"))
    af.refresh_from_db()
    assert af.paused_reason == "card_needs_otp"


def test_skipping_a_window(user, af, recipients, make_plan):
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=28)
    af.skip_window = "2026-10-end"
    af.save()
    autofill.run(lagos("2026-10-27T07:00"))
    autofill.run(lagos("2026-10-27T10:00"))
    assert not AutoFillAttempt.objects.filter(user=user).exists()


def test_limits_cap_the_charge(user, af, recipients, make_plan):
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=28)
    af.max_per_charge_kobo = naira(20_000)
    af.save()
    start = bal(user)
    autofill.run(lagos("2026-10-27T07:00"))
    autofill.run(lagos("2026-10-27T10:00"))
    assert bal(user) - start == naira(20_000)
    af.max_per_month_kobo = naira(25_000)
    af.save()
    assert autofill.clamp(af, naira(30_000), lagos("2026-10-31T10:00")) == (naira(5_000), "per_month")


def test_kill_switch_and_removed_card(user, af, card, settings, recipients, make_plan):
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=28)
    settings.AUTOFILL_ENABLED = False
    autofill.run(lagos("2026-10-27T07:00"))
    assert not OutboxMessage.objects.filter(template="autofill_heads_up").exists()
    settings.AUTOFILL_ENABLED = True
    cards.remove_card(card)
    af.refresh_from_db()
    assert af.paused_reason == "card_removed"


def test_expired_card_pauses(user, af, card, recipients, make_plan):
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=28)
    card.exp_month, card.exp_year = "09", "2026"
    card.save()
    autofill.run(lagos("2026-10-27T07:00"))
    af.refresh_from_db()
    assert af.paused_reason == "card_expired"


# ---------------------------------------------------------------- just in time

def test_just_in_time_covers_tomorrows_drip_once(user, af, recipients, make_plan):
    af.payday_end, af.just_in_time = False, True
    af.save()
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=12, time_local="09:00")
    start = bal(user)
    assert autofill.run(lagos("2026-11-10T09:00"))["jit"] == 0  # more than a day away
    assert autofill.run(lagos("2026-11-11T09:30"))["jit"] == 1
    # ₦30,050 needed, ₦100 held → ₦29,950 short → ₦30,000 (rounded up to ₦500)
    assert bal(user) - start == naira(30_000)
    assert autofill.run(lagos("2026-11-11T10:00"))["jit"] == 0
    assert OutboxMessage.objects.filter(template="autofill_jit").count() == 1


def test_just_in_time_charges_at_least_1000(user, af, top_up, recipients, make_plan):
    af.payday_end, af.just_in_time = False, True
    af.save()
    top_up(29_900)
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=12, time_local="09:00")
    start = bal(user)
    autofill.run(lagos("2026-11-11T09:30"))
    assert bal(user) - start == naira(1_000)


def test_declined_just_in_time_has_one_try_then_the_reminder_says_so(user, af, gateway, monkeypatch, recipients, make_plan, settings):
    af.payday_end, af.just_in_time = False, True
    af.save()
    decline(gateway, monkeypatch)
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=12, time_local="09:00")
    from drips.worker import Worker
    Worker().remind(lagos("2026-11-11T09:30"))
    Worker().remind(lagos("2026-11-11T12:30"))
    assert AutoFillAttempt.objects.filter(user=user, kind="jit").count() == 1
    from django.core import mail
    m = [x for x in mail.outbox if "Tomorrow" in x.subject][-1]
    assert "Auto-fill tried to top up" in m.body and "Insufficient Funds" in m.body


def test_just_in_time_skips_drips_held_by_the_daily_cap(user, af, recipients, make_plan):
    af.payday_end, af.just_in_time = False, True
    af.save()
    user.daily_cap_kobo = naira(10_000)
    user.save()
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=12, time_local="09:00")
    assert autofill.run(lagos("2026-11-11T09:30"))["jit"] == 0


def test_consent_text():
    a = AutoFill(payday_end=True, payday_start=False, just_in_time=True, max_per_charge_kobo=naira(250_000), max_per_month_kobo=naira(400_000),
                 card=SavedCard(brand="visa", last4="4081"))
    assert autofill.consent_text(a) == ("I allow SpenDrip to charge Visa ••4081 up to ₦250,000 per charge and ₦400,000 per month, in the last 5 days "
                                        "of each month and up to a day before a drip my balance can't cover, to top up my SpenDrip balance, "
                                        "until I turn Auto-fill off.")


def test_just_in_time_catches_what_a_capped_payday_fill_left(user, af, recipients, make_plan):
    af.just_in_time, af.max_per_charge_kobo = True, naira(20_000)
    af.save()
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=28)
    start = bal(user)
    autofill.run(lagos("2026-10-27T07:00"))
    autofill.run(lagos("2026-10-27T10:00"))  # payday: ₦20,000 (the cap), then just in time: the ₦10,000 still short for tomorrow
    assert bal(user) - start == naira(30_000)
