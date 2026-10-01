from datetime import timedelta

import pytest

from conftest import lagos
from drips.models import Run
from drips.worker import Worker
from engine import naira
from ledger import services as ledger
from notifications.models import OutboxMessage
from providers.mock import MockMessenger, MockPaymentProvider


@pytest.fixture
def provider():
    return MockPaymentProvider()


@pytest.fixture
def worker(provider):
    return Worker(provider=provider, messenger=MockMessenger())


def runs_of(plan):
    return Run.objects.filter(plan=plan).order_by("scheduled_for")


def test_happy_path_sends_once_settles_and_notifies(user, top_up, recipients, make_plan, worker, provider):
    top_up(20_000)
    mum = make_plan("Mum", 10_000, recipients["mum"], frequency="monthly", month_day=2, time_local="10:00")
    t = lagos("2026-11-02T10:00")
    worker.tick(t)
    run = runs_of(mum).get(scheduled_for=t)
    assert run.status == Run.Status.PENDING
    worker.tick(t)  # ticking again must not resend
    assert provider.transfer_calls == 1

    worker.tick(t + timedelta(seconds=31))  # status check
    run.refresh_from_db()
    assert run.status == Run.Status.SUCCESSFUL
    assert ledger.balance(user).available_kobo == naira(20_000 - 10_050)
    assert ledger.balance(user).held_kobo == 0
    assert ledger.trial_balance() == 0
    wa = OutboxMessage.objects.get(run=run, channel="whatsapp")
    assert "₦10,000 just landed" in wa.body and wa.status == "mocked"
    assert OutboxMessage.objects.filter(run=run, template="self_paid", channel="in_app").exists()


def test_mum_on_the_2nd_waits_to_protect_upkeep(user, top_up, recipients, make_plan, worker):
    """Upkeep (₦5k/day) is priority 1, Mum (₦30k) is not, and ₦150k is available when Mum is due on 2 Nov."""
    upkeep = make_plan("Upkeep", 5_000, recipients["me"], priority=1, frequency="daily", time_local="06:00")
    upkeep.starts_at = lagos("2026-11-02T00:00")
    upkeep.save()
    mum = make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=2, time_local="10:00")
    top_up(155_050)

    worker.tick(lagos("2026-11-02T06:00"))  # upkeep goes out: ₦150,000 left
    worker.tick(lagos("2026-11-02T10:00"))
    run = runs_of(mum).get(scheduled_for=lagos("2026-11-02T10:00"))
    assert run.status == Run.Status.SKIPPED_PROTECTED
    msg = OutboxMessage.objects.get(run=run, channel="in_app")
    assert "keep your priorities safe" in msg.body and "Top up ₦21,450" in msg.body  # 28 × 5,050 + 30,050 − 150,000


def test_mum_on_the_20th_goes_through(user, top_up, recipients, make_plan, worker):
    make_plan("Upkeep", 5_000, recipients["me"], priority=1, frequency="daily", time_local="06:00")
    mum = make_plan("Mum", 30_000, recipients["mum"], frequency="monthly", month_day=20, time_local="10:00")
    top_up(150_000)
    worker.tick(lagos("2026-11-20T10:00"))  # that morning's 06:00 upkeep is still within the 6h late window, so it goes first
    run = runs_of(mum).get(scheduled_for=lagos("2026-11-20T10:00"))
    assert run.status == Run.Status.PENDING


def test_failed_transfer_gives_the_money_back(user, top_up, recipients, make_plan, worker):
    top_up(20_000)
    plan = make_plan("Oops", 10_000, recipients["bad"], frequency="monthly", month_day=2)  # mock fails accounts ending 0000
    worker.tick(lagos("2026-11-02T09:00"))
    run = runs_of(plan).get(scheduled_for=lagos("2026-11-02T09:00"))
    assert run.status == Run.Status.FAILED
    assert ledger.balance(user).available_kobo == naira(20_000)
    assert OutboxMessage.objects.filter(run=run, template="self_failed").exists()


def test_unknown_outcome_is_checked_not_resent(user, top_up, recipients, make_plan, worker, provider):
    top_up(20_000)
    plan = make_plan("Mum", 10_000, recipients["mum"], frequency="monthly", month_day=2)
    provider.crash_next = True
    t = lagos("2026-11-02T09:00")
    worker.tick(t)
    run = runs_of(plan).get(scheduled_for=t)
    assert run.status == Run.Status.UNKNOWN
    assert ledger.balance(user).held_kobo == naira(10_050)

    worker.tick(t + timedelta(seconds=31))
    run.refresh_from_db()
    assert run.status == Run.Status.SUCCESSFUL
    assert provider.transfer_calls == 1
    assert ledger.trial_balance() == 0


def test_run_too_late_is_marked_missed_not_sent(user, top_up, recipients, make_plan, worker, provider):
    top_up(20_000)
    plan = make_plan("Upkeep", 5_000, recipients["me"], frequency="monthly", month_day=2, time_local="06:00")
    from drips.services import materialise_runs
    materialise_runs(lagos("2026-11-02T05:00"))
    worker.tick(lagos("2026-11-02T13:00"))  # 7h late
    run = runs_of(plan).get(scheduled_for=lagos("2026-11-02T06:00"))
    assert run.status == Run.Status.MISSED
    assert provider.transfer_calls == 0
    assert ledger.balance(user).available_kobo == naira(20_000)


def test_pause_everything_skips_runs(user, top_up, recipients, make_plan, worker, provider):
    top_up(20_000)
    plan = make_plan("Mum", 10_000, recipients["mum"], frequency="monthly", month_day=2)
    from drips.services import materialise_runs
    materialise_runs(lagos("2026-11-02T08:00"))
    user.paused_all = True
    user.save()
    worker.tick(lagos("2026-11-02T09:00"))
    assert runs_of(plan).get(scheduled_for=lagos("2026-11-02T09:00")).status == Run.Status.SKIPPED_PAUSED
    assert provider.transfer_calls == 0


def test_daily_cap_holds_back_the_second_run(user, top_up, recipients, make_plan, worker):
    top_up(100_000)
    user.daily_cap_kobo = naira(50_000)
    user.save()
    a = make_plan("Fuel", 40_000, recipients["me"], frequency="monthly", month_day=2, time_local="09:00")
    b = make_plan("Rent", 20_000, recipients["me"], frequency="monthly", month_day=2, time_local="10:00")
    worker.tick(lagos("2026-11-02T09:00"))
    worker.tick(lagos("2026-11-02T10:00"))
    assert runs_of(a).get(scheduled_for=lagos("2026-11-02T09:00")).status == Run.Status.SUCCESSFUL  # confirmed by the 10:00 tick
    assert runs_of(b).get(scheduled_for=lagos("2026-11-02T10:00")).status == Run.Status.SKIPPED_CAP


def test_priority_runs_first_when_due_at_the_same_time(user, top_up, recipients, make_plan, worker):
    top_up(15_100)  # enough for one ₦10,050 run, not two
    other = make_plan("Fun", 10_000, recipients["me"], frequency="monthly", month_day=2)
    mum = make_plan("Mum", 10_000, recipients["mum"], priority=1, frequency="monthly", month_day=2)
    worker.tick(lagos("2026-11-02T09:00"))
    t = lagos("2026-11-02T09:00")
    assert runs_of(mum).get(scheduled_for=t).status == Run.Status.PENDING
    assert runs_of(other).get(scheduled_for=t).status == Run.Status.SKIPPED_INSUFFICIENT


def test_materialising_twice_creates_nothing_new(user, recipients, make_plan):
    from drips.services import materialise_runs
    make_plan("Upkeep", 5_000, recipients["me"], frequency="daily", time_local="06:00")
    first = materialise_runs(lagos("2026-11-01T00:00"))
    assert first > 30
    assert materialise_runs(lagos("2026-11-01T00:00")) == 0
