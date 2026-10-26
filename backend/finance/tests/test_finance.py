"""Finance: categories, the report's sections (each only when it applies), salary, expenses, fee ideas and Kobo's AI take."""
from unittest import mock

import pytest

from conftest import lagos
from finance import ai as fin_ai
from finance import categories as cats
from finance import report
from finance.models import Expense, FinanceProfile, FinanceSnapshot


def kinds(user, now="2026-10-20T12:00"):
    return {s["kind"]: s for s in report.build(user, lagos(now))["sections"]}


@pytest.mark.parametrize("name, who, want", [
    ("Upkeep", "Ada", "food"), ("Mama's money", "Mum", "family"), ("Fuel", "Me", "transport"), ("House rent", "Landlord", "housing"),
    ("Tunde (driver)", "", "staff"), ("Fibrenet Data", "", "bills"), ("Tithe", "", "giving"), ("Tobi's allowance", "Tobi", "education"),
    ("Emergency fund", "Me", "savings"),
])
def test_rules_guess_categories(name, who, want):
    assert cats.guess(name, who) == want


def test_user_choice_beats_the_guess(user, recipients, make_plan):
    p = make_plan("Upkeep", 5_000, recipients["mum"], frequency="daily")
    assert cats.plan_category(p) == ("food", "rule")
    p.category = "family"
    assert cats.plan_category(p) == ("family", "user")


def test_new_user_gets_a_tidy_report(user):
    k = kinds(user)
    assert {"headline", "insights", "salary", "trend", "savings"} <= set(k)
    assert "breakdown" not in k and k["trend"]["data"]["months"] is None and k["salary"]["data"]["salary_kobo"] is None
    assert {"missing"} <= set(k)  # rent and feeding prompts


def test_breakdown_salary_family_and_missing(user, recipients, make_plan):
    make_plan("Mum", 50_000, recipients["mum"], frequency="monthly", month_day=25)
    make_plan("Upkeep", 5_000, recipients["mum"], frequency="daily")
    FinanceProfile.objects.create(user=user, salary_kobo=50_000_000)
    s = report.build(user, lagos("2026-10-20T12:00"))["sections"]
    missing = [x["data"]["category"] for x in s if x["kind"] == "missing"]
    assert missing == ["housing"]  # feeding is covered by Upkeep
    k = {x["kind"]: x for x in s}
    rows = {r["key"]: r for r in k["breakdown"]["data"]["rows"]}
    assert rows["food"]["kobo"] == 30 * (500_000 + 5_000) and rows["family"]["kobo"] > 0  # 30 days in November, ₦50 fee each (test fees)
    sal = k["salary"]["data"]
    assert sal["salary_kobo"] == 50_000_000 and sal["planned_pct"] == round(k["breakdown"]["data"]["total_kobo"] * 100 / 50_000_000)
    assert k["family"]["data"]["people"] == ["Mum"]


def test_expenses_paid_elsewhere_count_and_fill_the_gap(user, recipients, make_plan):
    make_plan("Mum", 50_000, recipients["mum"], frequency="monthly", month_day=25)
    Expense.objects.create(user=user, label="Rent", category="housing", amount_kobo=120_000_000, every="year")
    Expense.objects.create(user=user, label="Market", category="food", amount_kobo=2_000_000, every="week")
    k = kinds(user)
    rows = {r["key"]: r["kobo"] for r in k["breakdown"]["data"]["rows"]}
    assert rows["housing"] == 10_000_000 and rows["food"] == round(2_000_000 * 52 / 12)
    assert "missing" not in k


def test_dismissing_a_missing_prompt(user):
    FinanceProfile.objects.create(user=user, dismissed=["missing:housing"])
    missing = [x["data"]["category"] for x in report.build(user, lagos("2026-10-20T12:00"))["sections"] if x["kind"] == "missing"]
    assert missing == ["food"]


def test_fee_ideas_daily_to_weekly(user, recipients, make_plan):
    make_plan("Upkeep", 5_000, recipients["mum"], frequency="daily")
    ideas = kinds(user)["fees"]["data"]["ideas"]
    assert ideas[0]["to"] == "weekly" and ideas[0]["new_amount_kobo"] == 3_500_000 and ideas[0]["saving_kobo"] > 0


def test_ai_take_is_cached_until_the_numbers_change(user, recipients, make_plan):
    p = make_plan("Oga's money", 20_000, recipients["mum"], frequency="monthly", month_day=25)
    answer = {"summary": "A calm month.", "suggestions": [{"title": "Save first", "body": "Add a savings drip of ₦20,000.", "kind": "savings"}],
              "categories": {str(p.pk): "family"}}
    with mock.patch("finance.ai.text_json", return_value=answer) as call:
        f = report.Facts(user)
        ai, status = fin_ai.insights(user, f.for_ai())
        assert status == "fresh" and ai["categories"] == {str(p.pk): "family"}
        # Applying the AI's categories mustn't change the facts (or it would call again every time).
        f2 = report.Facts(user, ai_categories=ai["categories"])
        assert fin_ai.facts_hash(f2.for_ai()) == fin_ai.facts_hash(f.for_ai())
        assert fin_ai.insights(user, f2.for_ai())[1] == "cached"
        assert call.call_count == 1
    built = report.build(user, ai=ai)["sections"]
    ins = next(x for x in built if x["kind"] == "insights")["data"]
    assert ins["source"] == "ai" and ins["summary"] == "A calm month."
    assert FinanceSnapshot.objects.count() == 1


def test_ai_failure_falls_back_to_rules(user, recipients, make_plan):
    make_plan("Upkeep", 5_000, recipients["mum"], frequency="daily")
    with mock.patch("finance.ai.text_json", side_effect=RuntimeError("down")):
        ai, status = fin_ai.insights(user, report.Facts(user).for_ai())
    assert ai is None and status == "error"
    ins = next(x for x in report.build(user)["sections"] if x["kind"] == "insights")["data"]
    assert ins["source"] == "rules" and ins["suggestions"]


def test_api(user, recipients, make_plan, settings):
    from rest_framework.test import APIClient
    import time
    make_plan("Upkeep", 5_000, recipients["mum"], frequency="daily")
    c = APIClient()
    c.force_login(user)
    s = c.session
    s["unlocked_at"] = s["last_seen"] = time.time()
    s.save()
    assert c.get("/api/finance").status_code == 200
    assert c.put("/api/finance/profile", {"salary_kobo": 40_000_000}, format="json").json()["salary_kobo"] == 40_000_000
    r = c.post("/api/finance/expenses", {"label": "Rent", "category": "housing", "amount_kobo": 90_000_000, "every": "year"}, format="json")
    assert r.status_code == 201
    plan_id = user.plans.first().pk
    assert c.put(f"/api/finance/plans/{plan_id}/category", {"category": "family"}, format="json").status_code == 200
    assert user.plans.first().category == "family"
    with mock.patch("finance.ai.text_json", return_value={"summary": "Hi.", "suggestions": [], "categories": {}}):
        assert c.post("/api/finance", {}, format="json").json()["ai_status"] == "fresh"
