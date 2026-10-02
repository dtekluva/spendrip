from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from engine import naira

LAGOS = ZoneInfo("Africa/Lagos")


def lagos(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=LAGOS)


@pytest.fixture(autouse=True)
def offline_providers(settings):
    """Tests never call real Paystack or Liberty, whatever is in .env."""
    from providers import registry

    settings.SPENDRIP = {**settings.SPENDRIP, "PAYMENT_PROVIDER": "mock", "PAYOUT_PROVIDER": ""}
    settings.PAYSTACK = {**settings.PAYSTACK, "SECRET_KEY": "", "PUBLIC_KEY": "", "NAME_CHECK_SECRET_KEY": ""}
    for f in (registry.get_payment_provider, registry.get_payout_provider, registry.get_card_gateway):
        f.cache_clear()
    yield
    for f in (registry.get_payment_provider, registry.get_payout_provider, registry.get_card_gateway):
        f.cache_clear()


@pytest.fixture
def user(db):
    from accounts.models import User
    from ledger import services as ledger

    u = User.objects.create(username="ada", first_name="ADAEZE", last_name="OKONKWO", kyc_status=User.Kyc.VERIFIED)
    ledger.ensure_user_accounts(u)
    return u


@pytest.fixture
def top_up(user):
    from ledger import services as ledger
    from ledger.models import Inflow

    counter = {"n": 0}

    def _top_up(amount_naira, who=None):
        counter["n"] += 1
        inflow = Inflow.objects.create(provider="mock", reference=f"t{counter['n']}", user=who or user, amount_kobo=naira(amount_naira))
        ledger.credit_inflow(inflow)
        return inflow

    return _top_up


@pytest.fixture
def recipients(user):
    from drips.models import Recipient

    def make(label, number, is_self=False, whatsapp=""):
        return Recipient.objects.create(user=user, label=label, bank_name="GTBank", nip_bank_code="000013", account_number=number,
                                        verified_account_name=label.upper(), is_self=is_self, whatsapp=whatsapp)

    return {"me": make("Me", "0244132018", is_self=True), "mum": make("Mum", "9028906357", whatsapp="+2348030004417"),
            "bad": make("Bad", "1111110000")}


@pytest.fixture
def make_plan(user):
    from drips.models import Plan

    def _make(label, amount_naira, recipient, priority=None, **sched):
        sched.setdefault("time_local", "09:00")
        return Plan.objects.create(user=user, label=label, amount_kobo=naira(amount_naira), recipient=recipient, priority_rank=priority,
                                   starts_at=lagos("2026-01-01T00:00"), **sched)

    return _make
