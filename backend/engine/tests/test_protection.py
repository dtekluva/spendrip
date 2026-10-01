import pytest

from engine import decide, forecast, naira, set_priority, validate_priorities
from engine.protection import GOES_OUT

from .helpers import FEE, TZ, at, plan

CFG = {"fee_kobo": FEE, "tz": TZ}


def by_plan(f, pid):
    return [e for e in f.events if e.plan_id == pid]


# ---------- funding totals ----------

def test_october_needs_349900_including_1900_fees():
    plans = [
        plan("fuel", 40_000, frequency="weekly", weekday=5, time_local="14:00"),
        plan("upkeep", 3_000, frequency="daily", time_local="06:00"),
        plan("mum", 30_000, frequency="monthly", month_day=30, time_local="10:00"),
        plan("cousin", 25_000, frequency="monthly", month_day=30, time_local="12:00"),
    ]
    f = forecast(plans, naira(120_000), at("2026-10-01T00:00"), **CFG)
    assert len(f.events) == 38
    assert f.total_needed_kobo == naira(349_900)
    assert f.top_up_kobo == naira(229_900)


# ---------- priority protection, monthly and prorated (November 2026 has 30 days) ----------

def nov():
    return [
        plan("upkeep", 5_000, 1, frequency="daily", time_local="06:00"),
        plan("mum", 30_000, 2, frequency="monthly", month_day=30, time_local="10:00"),
        plan("cousin", 25_000, frequency="monthly", month_day=30, time_local="12:00"),
    ]


def test_190k_cousin_not_paid_because_priorities_need_181550():
    f = forecast(nov(), naira(190_000), at("2026-11-01T00:00"), **CFG)
    assert f.protected_kobo == naira(181_550)
    assert f.free_kobo == naira(8_450)
    assert [e.plan_id for e in f.waiting] == ["cousin"]
    assert by_plan(f, "mum")[0].status == "protected"
    assert all(e.status == "protected" for e in by_plan(f, "upkeep"))
    assert f.top_up_kobo == naira(16_600)


def test_a_16600_top_up_sends_everything():
    f = forecast(nov(), naira(206_600), at("2026-11-01T00:00"), **CFG)
    assert f.waiting == [] and f.top_up_kobo == 0


def test_prorated_halfway_through_the_month():
    f = forecast(nov(), naira(100_000), at("2026-11-16T12:00"), **CFG)
    assert f.protected_kobo == 14 * naira(5_050) + naira(30_050)  # upkeep 17–30 Nov + Mum


def test_floor_resets_on_the_first():
    f = forecast(nov(), 0, at("2026-12-01T00:00"), **CFG)
    assert f.protected_kobo == 31 * naira(5_050) + naira(30_050)


# ---------- the same ₦30k on different days (Mum not priority, ₦150k available) ----------

def ask(day: int):
    plans = [
        plan("upkeep", 5_000, 1, frequency="daily", time_local="06:00"),
        plan("mum", 30_000, frequency="monthly", month_day=day, time_local="10:00"),
    ]
    return decide(plan_id="mum", at=at(f"2026-11-{day:02d}T10:00"), amount_kobo=naira(30_000), plans=plans,
                  available_kobo=naira(150_000), sent_today_kobo=0, **CFG)


def test_mum_on_the_2nd_is_skipped():
    d = ask(2)
    assert not d.ok and d.reason == "protected_for_priorities"
    assert d.reserved_for_others_kobo == 28 * naira(5_050)


def test_mum_on_the_3rd_needs_166400_for_a_successful_month():
    d = ask(3)
    assert not d.ok
    assert d.reserved_for_others_kobo + naira(30_050) == naira(166_400)


def test_mum_on_the_20th_goes_through():
    d = ask(20)
    assert d.ok
    assert d.reserved_for_others_kobo == 10 * naira(5_050)


# ---------- ordered priorities ----------

def ranked():
    return [
        plan("upkeep", 3_000, 1, frequency="daily", time_local="06:00"),
        plan("data", 10_000, 2, frequency="monthly", month_day=2),
        plan("gym", 15_000, 3, frequency="monthly", month_day=3),
        plan("fun", 5_000, frequency="monthly", month_day=4),
    ]


def test_priority_2_never_spends_what_priority_1_still_needs():
    f = forecast(ranked(), naira(100_000), at("2026-11-01T00:00"), **CFG)
    assert all(e.status == "protected" for e in by_plan(f, "upkeep"))
    assert by_plan(f, "data")[0].status == "short"
    assert by_plan(f, "gym")[0].status == "short"
    # Skipped priority runs free their money, so a small later non-priority run still fits.
    assert by_plan(f, "fun")[0].status == "send"


def test_enough_for_1_and_2_but_not_3():
    f = forecast(ranked(), naira(110_000), at("2026-11-01T00:00"), **CFG)
    assert by_plan(f, "data")[0].status == "protected"
    assert by_plan(f, "gym")[0].status == "short"
    assert f.priority_shortfall_kobo == naira(91_500 + 10_050 + 15_050 - 110_000)


def test_rejects_duplicate_priorities():
    class P:
        def __init__(self, i, r):
            self.id, self.priority_rank = i, r
    assert len(validate_priorities([P("a", 1), P("b", 1)])) == 1


def test_set_priority_pushes_down_and_drops_a_fourth():
    assert set_priority(["upkeep", "mum", "fuel"], "rent", 1) == (["rent", "upkeep", "mum"], ["fuel"])
    assert set_priority(["upkeep", "mum"], "mum", 0) == (["upkeep"], [])
    assert set_priority(["upkeep"], "mum", 3) == (["upkeep", "mum"], [])


# ---------- daily cap ----------

def test_daily_cap_holds_back_the_run_that_crosses_it():
    plans = [
        plan("fuel", 40_000, frequency="monthly", month_day=5, time_local="09:00"),
        plan("rent", 20_000, frequency="monthly", month_day=5, time_local="10:00"),
    ]
    f = forecast(plans, naira(500_000), at("2026-11-01T00:00"), daily_cap_kobo=naira(50_000), **CFG)
    assert [e.status for e in f.events] == ["send", "cap"]


# ---------- forecast and the live decision agree ----------

@pytest.mark.parametrize("available", [50_000, 120_000, 190_000, 260_000])
def test_forecast_matches_live_decisions(available):
    plans = [
        plan("upkeep", 5_000, 1, frequency="daily", time_local="06:00"),
        plan("fuel", 40_000, frequency="weekly", weekday=5, time_local="14:00"),
        plan("mum", 30_000, 2, frequency="monthly", month_day=30, time_local="10:00"),
        plan("cousin", 25_000, frequency="monthly", month_day=15, time_local="12:00"),
        plan("data", 8_000, 3, frequency="weekly", weekday=1),
    ]
    f = forecast(plans, naira(available), at("2026-11-01T00:00"), **CFG)
    balance = naira(available)
    for e in f.events:
        d = decide(plan_id=e.plan_id, at=e.at, amount_kobo=e.amount_kobo, plans=plans,
                   available_kobo=balance, sent_today_kobo=0, **CFG)
        assert d.ok == (e.status in GOES_OUT), (e.plan_id, e.at, e.status, d)
        if d.ok:
            balance -= e.cost_kobo
