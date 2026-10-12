"""Pays it forward: free entry, eligibility, a reproducible draw, a once-only payout from the promotions account."""
import pytest

from accounts.services import FlowError
from conftest import lagos
from ledger import services as ledger
from notifications.models import OutboxMessage
from promos import services as boost
from promos.models import BoostEntry, BoostMonth


@pytest.fixture(autouse=True)
def on(settings):
    settings.BOOST_ENABLED = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


STORY = "I send my mum her upkeep every month so she never has to ask."


def test_entering_is_free_but_needs_a_plan(user, recipients, make_plan):
    assert "Set up a plan" in boost.eligible(user)
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=25)
    assert boost.eligible(user) is None  # no top-up needed
    e = boost.enter(user, recipient_id=recipients["mum"].pk, story=STORY, consent_publish=True, now=lagos("2026-11-10T09:00"))
    assert e.month.month == "2026-11"
    boost.enter(user, recipient_id=recipients["mum"].pk, story=STORY + " Truly.", consent_publish=False, now=lagos("2026-11-11T09:00"))
    assert BoostEntry.objects.count() == 1  # editing, not a second entry


def test_bad_entries_are_refused(user, recipients, make_plan, settings):
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=25)
    with pytest.raises(FlowError):
        boost.enter(user, recipient_id=recipients["mum"].pk, story="too short", consent_publish=False)
    with pytest.raises(FlowError):
        boost.enter(user, recipient_id=None, story=STORY, consent_publish=False)
    settings.BOOST_ENABLED = False
    with pytest.raises(FlowError):
        boost.enter(user, recipient_id=recipients["mum"].pk, story=STORY, consent_publish=False)


def entered(user, recipients, make_plan):
    make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=25)
    return boost.enter(user, recipient_id=recipients["mum"].pk, story=STORY, consent_publish=True, now=lagos("2026-11-10T09:00"))


def test_draw_is_reproducible_and_only_after_the_month(user, recipients, make_plan):
    e = entered(user, recipients, make_plan)
    with pytest.raises(FlowError):
        boost.draw("2026-11", "NGX 98,765.43", now=lagos("2026-11-30T09:00"))
    m = boost.draw("2026-11", "NGX 98,765.43", now=lagos("2026-12-01T18:00"))
    assert m.winner_id == e.pk and m.pool_ids == [e.pk]
    assert m.seed == boost.seed_for("2026-11", "NGX 98,765.43", [e.pk])
    with pytest.raises(FlowError):
        boost.draw("2026-11", "again", now=lagos("2026-12-02T18:00"))


def test_shortlist_narrows_the_pool(user, recipients, make_plan, db):
    from accounts.models import User
    e = entered(user, recipients, make_plan)
    other = User.objects.create(username="bola", first_name="BOLA", kyc_status=User.Kyc.VERIFIED)
    other_entry = BoostEntry.objects.create(month=e.month, user=other, recipient=recipients["mum"], story=STORY)
    assert {x.pk for x in boost.pool(e.month)} == {e.pk}  # Bola has no active plan, so isn't eligible
    e.shortlisted = True
    e.save()
    assert [x.pk for x in boost.pool(e.month)] == [e.pk]
    assert other_entry.pk not in [x.pk for x in boost.pool(e.month)]


def test_pay_credits_once_from_promotions_and_tells_the_winner(user, recipients, make_plan):
    user.email = "ada@example.com"
    user.save()
    entered(user, recipients, make_plan)
    boost.draw("2026-11", "NGX 98,765.43", now=lagos("2026-12-01T18:00"))
    start = ledger.balance(user).available_kobo
    boost.pay("2026-11")
    boost.pay("2026-11")  # twice is harmless
    assert ledger.balance(user).available_kobo - start == 5_000_000
    assert ledger.account_balance(boost.PROMOTIONS) == -5_000_000 and ledger.trial_balance() == 0
    assert BoostMonth.objects.get(month="2026-11").status == "paid"
    assert OutboxMessage.objects.filter(template="boost_won", channel="email").count() == 1
    assert boost.winners()[0]["first_name"] == "Adaeze"
