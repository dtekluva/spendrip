import pytest

from providers import names
from providers.base import NameEnquiryError, NameEnquiryResult, ProviderError


class Fake:
    name = "fake"

    def __init__(self, outcome):
        self.outcome, self.calls = outcome, 0

    def name_enquiry(self, code, number):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return NameEnquiryResult(self.outcome, code, number)


@pytest.fixture
def use(monkeypatch):
    def _use(outcome):
        f = Fake(outcome)
        monkeypatch.setattr(names, "get_name_checker", lambda: f)
        return f
    return _use


def test_each_account_costs_one_check(db, use):
    f = use("ADA OKAFOR")
    assert names.resolve("000013", "0123456789").account_name == "ADA OKAFOR"
    assert names.resolve("000013", "0123456789").account_name == "ADA OKAFOR"
    assert f.calls == 1


def test_limit_in_test_mode_gives_a_labelled_test_name(db, use, settings):
    settings.SPENDRIP = {**settings.SPENDRIP, "DEV_TOOLS": True}
    settings.PAYSTACK = {**settings.PAYSTACK, "MODE": "test"}
    use(NameEnquiryError("Test mode daily limit of 3 live bank resolves exceeded.", kind="limit"))
    n = names.resolve("000013", "0123456789")
    assert n.test_name and n.account_name
    from providers.models import ResolvedAccount
    assert not ResolvedAccount.objects.exists()  # made-up names are never remembered


def test_limit_in_live_mode_says_try_again(db, use, settings):
    settings.SPENDRIP = {**settings.SPENDRIP, "DEV_TOOLS": False}
    use(NameEnquiryError("limit", kind="limit"))
    with pytest.raises(names.NameCheckFailed) as e:
        names.resolve("000013", "0123456789")
    assert e.value.code == "lookup_busy" and e.value.status == 429


def test_bank_down_is_not_called_not_found(db, use):
    use(ProviderError("Paystack /bank/resolve: HTTP 502"))
    with pytest.raises(names.NameCheckFailed) as e:
        names.resolve("000013", "0123456789")
    assert e.value.code == "lookup_unavailable" and "can't reach the bank" in e.value.message


def test_saving_an_unknown_account_is_a_message_not_a_crash(db, use, dev_user_client):
    use(NameEnquiryError("We couldn't find that account. Check the number and bank."))
    r = dev_user_client.post("/api/recipients", {"label": "Sis", "nip_bank_code": "000014", "account_number": "0011223344"}, format="json")
    assert r.status_code == 400 and r.json()["code"] == "lookup_failed"


@pytest.fixture
def dev_user_client(user):
    import time
    from rest_framework.test import APIClient
    c = APIClient()
    c.force_login(user)
    s = c.session
    s["unlocked_at"] = s["last_seen"] = time.time()
    s.save()
    return c


def test_live_name_checker_can_only_look_up_names(settings):
    from providers import registry
    from providers.paystack import PaystackNameChecker
    settings.PAYSTACK = {**settings.PAYSTACK, "NAME_CHECK_SECRET_KEY": "sk_live_x"}
    checker = registry.get_name_checker()
    assert isinstance(checker, PaystackNameChecker)
    assert not any(hasattr(checker, m) for m in ("transfer", "create_recipient", "query_transfer", "charge"))
    assert registry.get_payout_provider() is not checker
