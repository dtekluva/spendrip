"""Group plans: several people, each with their own amount, paid together (all or nothing)."""
from datetime import timedelta

import pytest

from conftest import lagos
from drips.models import Plan, PlanLine, Run, RunBatch
from drips.services import materialise_runs, save_lines
from drips.worker import Worker
from engine import FeeSchedule, naira
from ledger import services as ledger
from ledger.models import FeeLine
from notifications.models import OutboxMessage
from providers.mock import MockMessenger, MockPaymentProvider

GROUP_FEE = naira(100)  # flat, whatever the number of people (transfer fees are off in tests, see conftest)


@pytest.fixture
def provider():
    return MockPaymentProvider()


@pytest.fixture
def worker(provider):
    return Worker(provider=provider, messenger=MockMessenger())


@pytest.fixture
def make_group(user):
    def _make(label, people, **sched):
        sched.setdefault("time_local", "09:00")
        sched.setdefault("frequency", "monthly")
        sched.setdefault("month_day", 2)
        plan = Plan.objects.create(user=user, kind=Plan.Kind.GROUP, label=label, amount_kobo=1, recipient=None,
                                   starts_at=lagos("2026-01-01T00:00"), **sched)
        save_lines(plan, [{"recipient": r, "amount_kobo": naira(n)} for r, n in people])
        return plan

    return _make


def batch_at(plan, iso):
    return RunBatch.objects.get(plan=plan, scheduled_for=lagos(iso))


def test_fee_schedule_charges_the_group_fee_once_and_transfer_fees_per_person():
    s = FeeSchedule(service_kobo=5_000, group_service_kobo=10_000)
    parts = s.group_parts([naira(80_000), naira(4_000), naira(20_000)])
    assert [p.service_kobo for p in parts] == [10_000, 0, 0]
    assert [p.provider_kobo for p in parts] == [5_000, 1_000, 2_500]
    assert [p.stamp_duty_kobo for p in parts] == [5_000, 0, 5_000]
    assert s.group_fee([naira(80_000), naira(4_000), naira(20_000)]) == 10_000 + 8_500 + 10_000


def test_everyone_paid_together_with_one_summary(user, top_up, recipients, make_group, worker, provider):
    top_up(20_000)
    staff = make_group("Staff", [(recipients["mum"], 10_000), (recipients["me"], 5_000)])
    assert staff.amount_kobo == naira(15_000)
    t = lagos("2026-11-02T09:00")
    worker.tick(t)
    b = batch_at(staff, "2026-11-02T09:00")
    assert b.status == RunBatch.Status.SENDING and b.fee_kobo == GROUP_FEE
    assert provider.transfer_calls == 2

    worker.tick(t + timedelta(seconds=31))
    b.refresh_from_db()
    assert b.status == RunBatch.Status.DONE
    assert set(b.runs.values_list("status", flat=True)) == {Run.Status.SUCCESSFUL}
    assert ledger.balance(user).available_kobo == naira(20_000 - 15_000 - 100)
    assert ledger.trial_balance() == 0
    assert list(FeeLine.objects.filter(kind="service").values_list("amount_kobo", flat=True)) == [GROUP_FEE]
    # Mum hears on WhatsApp; the sender gets one summary, not one note per person
    assert OutboxMessage.objects.filter(channel="whatsapp", template="recipient_paid").count() == 1
    assert not OutboxMessage.objects.filter(template="self_paid").exists()
    summary = OutboxMessage.objects.get(template="group_done", channel="in_app")
    assert "all 2 people paid" in summary.body
    worker.tick(t + timedelta(minutes=5))
    assert OutboxMessage.objects.filter(template="group_done", channel="in_app").count() == 1


def test_short_balance_waits_for_everyone_then_pays_all(user, top_up, recipients, make_group, worker, provider):
    top_up(12_000)
    staff = make_group("Staff", [(recipients["mum"], 10_000), (recipients["me"], 5_000)])
    t = lagos("2026-11-02T09:00")
    worker.tick(t)
    b = batch_at(staff, "2026-11-02T09:00")
    assert b.status == RunBatch.Status.WAITING and b.reason == "insufficient_funds"
    assert b.short_by_kobo == naira(15_100 - 12_000)
    assert provider.transfer_calls == 0  # nobody is paid while someone can't be
    assert ledger.balance(user).held_kobo == 0
    worker.tick(t + timedelta(minutes=10))
    assert OutboxMessage.objects.filter(template="group_waiting", channel="in_app").count() == 1
    assert "Add ₦3,100" in OutboxMessage.objects.get(template="group_waiting", channel="in_app").body

    top_up(5_000)
    worker.tick(t + timedelta(hours=2))
    b.refresh_from_db()
    assert b.status == RunBatch.Status.SENDING and provider.transfer_calls == 2


def test_still_short_after_the_late_window_skips_everyone(user, top_up, recipients, make_group, worker, provider):
    top_up(12_000)
    staff = make_group("Staff", [(recipients["mum"], 10_000), (recipients["me"], 5_000)])
    t = lagos("2026-11-02T09:00")
    worker.tick(t)
    worker.tick(t + timedelta(hours=7))
    b = batch_at(staff, "2026-11-02T09:00")
    assert b.status == RunBatch.Status.SKIPPED
    assert set(b.runs.values_list("status", flat=True)) == {Run.Status.SKIPPED_INSUFFICIENT}
    assert provider.transfer_calls == 0
    assert ledger.balance(user).available_kobo == naira(12_000)
    assert "Nobody on it was paid" in OutboxMessage.objects.get(template="group_skipped", channel="in_app").body


def test_one_failed_transfer_does_not_stop_the_others(user, top_up, recipients, make_group, worker):
    top_up(20_000)
    staff = make_group("Staff", [(recipients["mum"], 10_000), (recipients["bad"], 5_000)])  # mock fails accounts ending 0000
    t = lagos("2026-11-02T09:00")
    worker.tick(t)
    worker.tick(t + timedelta(seconds=31))
    b = batch_at(staff, "2026-11-02T09:00")
    assert b.status == RunBatch.Status.DONE
    assert dict(b.runs.values_list("line__recipient__label", "status")) == {"Mum": Run.Status.SUCCESSFUL, "Bad": Run.Status.FAILED}
    assert ledger.balance(user).available_kobo == naira(20_000 - 10_000 - 100)  # the flat fee sits on Mum's (first) transfer
    assert ledger.trial_balance() == 0
    assert "1 of 2 paid" in OutboxMessage.objects.get(template="group_done", channel="in_app").body


def test_one_off_changes_apply_to_the_next_payout_only(user, top_up, recipients, make_group, worker):
    top_up(100_000)
    staff = make_group("Staff", [(recipients["mum"], 10_000), (recipients["me"], 5_000)], frequency="weekly", weekday=1)
    PlanLine.objects.filter(plan=staff, recipient=recipients["mum"]).update(next_amount_kobo=naira(12_000))
    PlanLine.objects.filter(plan=staff, recipient=recipients["me"]).update(skip_next=True)
    staff.refresh_from_db()
    from drips.services import reschedule
    reschedule(staff, lagos("2026-11-01T12:00"))  # Sunday; next payouts Mon 2 Nov, Mon 9 Nov, ...
    first, second = RunBatch.objects.filter(plan=staff).order_by("scheduled_for")[:2]
    assert (first.amount_kobo, first.runs.count()) == (naira(12_000), 1)
    assert (second.amount_kobo, second.runs.count()) == (naira(15_000), 2)

    worker.tick(lagos("2026-11-02T09:00"))
    line = PlanLine.objects.get(plan=staff, recipient=recipients["me"])
    assert line.skip_next is False and PlanLine.objects.get(plan=staff, recipient=recipients["mum"]).next_amount_kobo is None


def test_forecast_counts_a_group_as_one_payout_with_its_flat_fee(user, recipients, make_group):
    from drips.services import user_forecast
    make_group("Staff", [(recipients["mum"], 10_000), (recipients["me"], 5_000)], month_day=20)
    f = user_forecast(user, lagos("2026-11-02T09:00"))
    (e,) = f.events
    assert (e.amount_kobo, e.fee_kobo) == (naira(15_000), GROUP_FEE)


def test_materialising_twice_creates_nothing_new(user, recipients, make_group):
    staff = make_group("Staff", [(recipients["mum"], 10_000), (recipients["me"], 5_000)])
    now = lagos("2026-11-01T09:00")
    materialise_runs(now)
    n = (RunBatch.objects.count(), Run.objects.count())
    assert materialise_runs(now) == 0
    assert (RunBatch.objects.count(), Run.objects.count()) == n
    assert Run.objects.filter(plan=staff, batch__isnull=True).count() == 0


def test_turning_a_single_plan_into_a_group_drops_its_single_drips(user, recipients, make_plan, worker, provider, top_up):
    from drips.services import reschedule
    top_up(50_000)
    plan = make_plan("Mum", 10_000, recipients["mum"], frequency="monthly", month_day=2)
    now = lagos("2026-11-01T09:00")
    reschedule(plan, now)
    assert Run.objects.filter(plan=plan, batch__isnull=True, status=Run.Status.SCHEDULED).exists()
    plan.kind = Plan.Kind.GROUP
    plan.save()
    save_lines(plan, [{"recipient": recipients["mum"], "amount_kobo": naira(10_000)}, {"recipient": recipients["me"], "amount_kobo": naira(5_000)}])
    reschedule(plan, now)
    assert not Run.objects.filter(plan=plan, batch__isnull=True, status=Run.Status.SCHEDULED).exists()
    worker.tick(lagos("2026-11-02T09:00"))
    assert provider.transfer_calls == 2  # Mum once (in the group), not twice


def test_a_waiting_payout_counts_in_the_top_up(user, top_up, recipients, make_group, worker):
    from drips.services import user_forecast
    top_up(12_000)
    make_group("Staff", [(recipients["mum"], 10_000), (recipients["me"], 5_000)])
    t = lagos("2026-11-02T09:00")
    worker.tick(t)
    f = user_forecast(user, t + timedelta(minutes=5))
    assert f.top_up_kobo == naira(15_100 - 12_000)


def test_a_skipped_payout_uses_up_the_one_off_changes(user, top_up, recipients, make_group, worker):
    top_up(1_000)
    staff = make_group("Staff", [(recipients["mum"], 10_000), (recipients["me"], 5_000)])
    PlanLine.objects.filter(plan=staff, recipient=recipients["me"]).update(skip_next=True)
    t = lagos("2026-11-02T09:00")
    worker.tick(t)
    worker.tick(t + timedelta(hours=7))  # still short: skipped
    assert batch_at(staff, "2026-11-02T09:00").status == RunBatch.Status.SKIPPED
    assert not PlanLine.objects.filter(plan=staff, skip_next=True).exists()


def test_send_again_pays_only_the_people_who_were_missed(user, top_up, recipients, make_group, worker, provider):
    from drips.services import retry_batch
    top_up(50_000)
    staff = make_group("Staff", [(recipients["mum"], 10_000), (recipients["bad"], 5_000)])  # "bad" fails at the mock bank
    t = lagos("2026-11-02T09:00")
    worker.tick(t)
    worker.tick(t + timedelta(seconds=31))
    first = batch_at(staff, "2026-11-02T09:00")
    assert first.status == RunBatch.Status.DONE and provider.transfer_calls == 2
    again = retry_batch(first, now=t + timedelta(hours=1))
    assert again.retry_of_id == first.pk and again.amount_kobo == naira(5_000)
    assert [r.line.recipient.label for r in again.runs.all()] == ["Bad"]
    with pytest.raises(ValueError, match="already_retried"):
        retry_batch(first, now=t + timedelta(hours=2))
    worker.tick(t + timedelta(hours=1))
    assert provider.transfer_calls == 3  # Mum isn't paid twice


def test_send_again_a_skipped_payout_after_topping_up(user, top_up, recipients, make_group, worker, provider):
    from drips.services import retry_batch
    top_up(1_000)
    staff = make_group("Staff", [(recipients["mum"], 10_000), (recipients["me"], 5_000)])
    t = lagos("2026-11-02T09:00")
    worker.tick(t)
    worker.tick(t + timedelta(hours=7))
    first = batch_at(staff, "2026-11-02T09:00")
    assert first.status == RunBatch.Status.SKIPPED
    top_up(20_000)
    again = retry_batch(first, now=t + timedelta(hours=8))
    worker.tick(t + timedelta(hours=8))
    worker.tick(t + timedelta(hours=8, seconds=31))
    again.refresh_from_db()
    assert again.status == RunBatch.Status.DONE and provider.transfer_calls == 2
    assert set(again.runs.values_list("status", flat=True)) == {Run.Status.SUCCESSFUL}
