import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_seed_then_summary_and_dev_top_up(settings):
    from django.core.management import call_command

    settings.SPENDRIP = {**settings.SPENDRIP, "DEV_TOOLS": True}
    call_command("seed_demo")
    c = APIClient()
    assert c.get("/api/health").json()["ok"] is True

    s = c.get("/api/summary").json()
    assert s["balance"]["available_kobo"] == 25_000_000
    assert s["funding_account"]["account_number"].startswith("8420")
    assert {e["status"] for e in s["forecast"]["events"]} <= {"protected", "send", "wait", "short", "cap"}

    r = c.post("/api/dev/top-up", {"amount_naira": 1000}, format="json")
    assert r.status_code == 201 and r.json()["available_kobo"] == 25_100_000
    assert len(c.get("/api/plans").json()) == 4


@pytest.mark.django_db
def test_dev_tools_are_off_in_production(settings):
    settings.SPENDRIP = {**settings.SPENDRIP, "DEV_TOOLS": False}
    c = APIClient()
    assert c.get("/api/summary").status_code == 403
    assert c.post("/api/dev/top-up", {"amount_naira": 1000}, format="json").status_code == 403
