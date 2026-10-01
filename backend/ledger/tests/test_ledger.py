import threading

import pytest
from django.db import connection, transaction

from conftest import lagos
from engine import naira
from ledger import services as ledger
from ledger.models import Inflow


def make_run(plan, when="2026-11-02T09:00"):
    from drips.models import Run
    return Run.objects.create(plan=plan, user=plan.user, scheduled_for=lagos(when), amount_kobo=plan.amount_kobo, fee_kobo=naira(50))


def test_top_up_is_credited_exactly_once(user, top_up):
    inflow = top_up(10_000)
    assert ledger.credit_inflow(inflow) is False  # second time does nothing
    assert ledger.balance(user).available_kobo == naira(10_000)
    assert Inflow.objects.get(pk=inflow.pk).status == "credited"
    assert ledger.trial_balance() == 0


def test_reserve_then_settle_moves_amount_out_and_fee_to_fees(user, top_up, recipients, make_plan):
    top_up(10_000)
    run = make_run(make_plan("Upkeep", 5_000, recipients["me"], frequency="daily"))
    with transaction.atomic():
        ledger.lock_wallet(user)
        assert ledger.reserve(user, run) is True
        assert ledger.reserve(user, run) is False  # idempotent
    assert ledger.balance(user).available_kobo == naira(4_950)
    assert ledger.balance(user).held_kobo == naira(5_050)
    ledger.settle(user, run)
    assert ledger.balance(user).held_kobo == 0
    assert ledger.account_balance(ledger.FEES) == naira(50)
    assert ledger.trial_balance() == 0


def test_release_returns_the_money_and_blocks_a_later_settle(user, top_up, recipients, make_plan):
    top_up(10_000)
    run = make_run(make_plan("Upkeep", 5_000, recipients["me"], frequency="daily"))
    with transaction.atomic():
        ledger.lock_wallet(user)
        ledger.reserve(user, run)
    ledger.release(user, run)
    assert ledger.balance(user).available_kobo == naira(10_000)
    with pytest.raises(ledger.LedgerError):
        ledger.settle(user, run)


def test_reserve_refuses_to_overdraw(user, top_up, recipients, make_plan):
    top_up(5_000)
    run = make_run(make_plan("Upkeep", 5_000, recipients["me"], frequency="daily"))  # needs 5,050 with the fee
    with pytest.raises(ledger.InsufficientFunds), transaction.atomic():
        ledger.lock_wallet(user)
        ledger.reserve(user, run)
    assert ledger.balance(user).available_kobo == naira(5_000)


def test_unbalanced_entries_are_rejected(user):
    with pytest.raises(ledger.LedgerError):
        ledger.post("bad", "adjust", [(ledger.wallet_code(user.pk), 100), (ledger.held_code(user.pk), -99)])


@pytest.mark.django_db(transaction=True)
def test_two_runs_at_once_cannot_spend_the_same_naira(user, top_up, recipients, make_plan):
    top_up(6_000)  # enough for one ₦5,050 run, not two
    plan = make_plan("Upkeep", 5_000, recipients["me"], frequency="daily")
    runs = [make_run(plan, "2026-11-02T09:00"), make_run(plan, "2026-11-03T09:00")]
    results, barrier = [], threading.Barrier(2)

    def attempt(run):
        try:
            barrier.wait()
            with transaction.atomic():
                ledger.lock_wallet(user)
                ledger.reserve(user, run)
            results.append("ok")
        except ledger.InsufficientFunds:
            results.append("insufficient")
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=(r,)) for r in runs]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == ["insufficient", "ok"]
    assert ledger.balance(user).available_kobo == naira(950)
