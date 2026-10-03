"""Money reminders: the month outlook, the day-ahead warning and the on-the-spot email."""
from datetime import timedelta

import pytest

from conftest import lagos
from drips.reminders import day_ahead, month_outlook, send_reminders
from drips.worker import Worker
from engine import naira
from notifications.models import OutboxMessage
from providers.mock import MockMessenger, MockPaymentProvider


@pytest.fixture(autouse=True)
def mailbox(settings, user):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user.email = "ada@example.com"
    user.save()
    from django.core import mail
    return mail


def test_month_outlook_goes_once_on_the_first_with_the_top_up(user, top_up, recipients, make_plan, mailbox):
    top_up(50_000)
    make_plan("Mum", 30_000, recipients["mum"], priority=1, frequency="monthly", month_day=25)
    make_plan("Fuel", 10_000, recipients["me"], frequency="weekly", weekday=5)
    assert month_outlook(user, lagos("2026-11-01T06:30")) == 0  # too early in the morning
    assert month_outlook(user, lagos("2026-11-01T07:30")) == 1
    assert month_outlook(user, lagos("2026-11-01T09:00")) == 0  # once
    assert month_outlook(user, lagos("2026-11-02T09:00")) == 0
    m = mailbox.outbox[-1]
    assert "November at a glance" in m.subject
    # 1 × ₦30,050 + 4 Fridays × ₦10,050 = ₦70,250 needed, ₦50,000 held → add ₦20,250
    assert "₦70,250 going out" in m.subject and "add ₦20,250" in m.body
    assert "Mum → Mum: 1 × ₦30,000" in m.body and "priority 1" in m.body


def test_month_outlook_says_covered_when_the_balance_is_enough(user, top_up, recipients, make_plan, mailbox):
    top_up(500_000)
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=25)
    month_outlook(user, lagos("2026-11-01T08:00"))
    assert "covers all of it" in mailbox.outbox[-1].body


def test_month_outlook_lists_a_group_as_people(user, top_up, recipients, mailbox):
    from drips.models import Plan
    from drips.services import save_lines
    p = Plan.objects.create(user=user, kind=Plan.Kind.GROUP, label="Staff", emoji="👷", amount_kobo=1, frequency="monthly", month_day=28,
                            time_local="09:00", starts_at=lagos("2026-01-01T00:00"))
    save_lines(p, [{"recipient": recipients["mum"], "amount_kobo": naira(10_000)}, {"recipient": recipients["me"], "amount_kobo": naira(5_000)}])
    assert month_outlook(user, lagos("2026-11-01T08:00")) == 1
    assert "👷 Staff → 2 people: 1 × ₦15,000 = ₦15,100 with fees" in mailbox.outbox[-1].body


def test_month_outlook_is_still_sent_if_the_worker_was_down_on_the_first(user, top_up, recipients, make_plan):
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=25)
    assert month_outlook(user, lagos("2026-11-03T12:00")) == 1
    assert month_outlook(user, lagos("2026-11-04T12:00")) == 0  # but not after the 3rd (next month gets its own)


def test_day_ahead_warns_once_about_a_drip_the_balance_cannot_cover(user, top_up, recipients, make_plan, mailbox):
    top_up(5_000)
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=10, time_local="09:00")
    assert day_ahead(user, lagos("2026-11-08T09:00")) == 0  # more than a day away
    assert day_ahead(user, lagos("2026-11-09T10:00")) == 1
    assert day_ahead(user, lagos("2026-11-09T12:00")) == 0  # once
    m = mailbox.outbox[-1]
    assert "Tomorrow" in m.subject and "Mum" in m.subject
    assert "Add ₦25,050 before then" in m.body
    assert OutboxMessage.objects.filter(template="low_balance_ahead", channel="in_app").count() == 1


def test_day_ahead_stays_quiet_when_the_money_is_there(user, top_up, recipients, make_plan, mailbox):
    top_up(100_000)
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=10, time_local="09:00")
    assert day_ahead(user, lagos("2026-11-09T10:00")) == 0 and not mailbox.outbox


def test_day_ahead_covers_a_group_payout(user, top_up, recipients, mailbox):
    from drips.models import Plan
    from drips.services import save_lines
    top_up(5_000)
    p = Plan.objects.create(user=user, kind=Plan.Kind.GROUP, label="Staff", emoji="👷", amount_kobo=1, frequency="monthly", month_day=10,
                            time_local="09:00", starts_at=lagos("2026-01-01T00:00"))
    save_lines(p, [{"recipient": recipients["mum"], "amount_kobo": naira(10_000)}, {"recipient": recipients["me"], "amount_kobo": naira(5_000)}])
    assert day_ahead(user, lagos("2026-11-09T10:00")) == 1
    assert "2 people" in mailbox.outbox[-1].body and "all or nothing" in mailbox.outbox[-1].body


def test_spot_email_when_a_drip_is_skipped_for_money(user, top_up, recipients, make_plan, mailbox):
    top_up(1_000)
    make_plan("Mum", 10_000, recipients["mum"], frequency="monthly", month_day=2)
    Worker(provider=MockPaymentProvider(), messenger=MockMessenger()).tick(lagos("2026-11-02T09:00"))
    m = [x for x in mailbox.outbox if "didn't go out" in x.subject]
    assert len(m) == 1 and "balance was short" in m[0].subject and "Add ₦9,050 now" in m[0].body


def test_reminders_never_break_the_tick(user, recipients, make_plan, monkeypatch):
    import drips.worker as w
    make_plan("Mum", 10_000, recipients["mum"], frequency="monthly", month_day=2)
    monkeypatch.setattr(w, "send_reminders", lambda now: 1 / 0)
    assert "handled" in Worker(provider=MockPaymentProvider(), messenger=MockMessenger()).tick(lagos("2026-11-01T08:00"))
