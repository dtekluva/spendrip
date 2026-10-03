import pytest

from accounts.services import FlowError
from ledger import cards
from ledger import services as ledger
from ledger.models import CardCharge, SavedCard
from providers.mock import MockCardGateway


@pytest.fixture(autouse=True)
def test_gateway(monkeypatch, settings):
    settings.PAYSTACK = {**settings.PAYSTACK, "PASS_CARD_FEES": True}
    gw = MockCardGateway("http://app.test")
    monkeypatch.setattr(cards, "gateway", lambda: gw)
    return gw


def test_quote_passes_the_fee_on():
    q = cards.quote(5_000_000)
    assert q.net_kobo == 5_000_000 and q.gross_kobo == q.net_kobo + q.fee_kobo and q.fee_kobo > 0


def test_top_up_credits_once_and_saves_the_card_encrypted(user):
    r = cards.start(user, 5_000_000, save_card=True)
    assert f"/fund/card?reference={r['reference']}" in r["authorization_url"] and r["test_mode"] is True
    charge = cards.complete(r["reference"])
    cards.complete(r["reference"])  # the webhook arriving too must not credit again
    assert charge.status == "success"
    assert ledger.balance(user).available_kobo == 5_000_000
    card = SavedCard.objects.get(user=user)
    assert card.last4 == "4081" and "AUTH_test" not in card.authorization_code_enc
    assert ledger.trial_balance() == 0


def test_one_tap_top_up_with_saved_card(user):
    cards.complete(cards.start(user, 1_000_000, save_card=True)["reference"])
    card = SavedCard.objects.get(user=user)
    c = cards.charge_saved_card(user, card, 2_000_000)
    assert c.status == "success" and c.card_id == card.id
    assert ledger.balance(user).available_kobo == 3_000_000


def test_declined_card_credits_nothing(user, monkeypatch):
    cards.complete(cards.start(user, 1_000_000, save_card=True)["reference"])
    card = SavedCard.objects.get(user=user)
    monkeypatch.setattr(cards, "quote", lambda n: cards.Quote(n, 13, n + 13, True))  # the test bank declines amounts ending in 13 kobo
    c = cards.charge_saved_card(user, card, 1_000_000)
    assert c.status == "failed" and "Declined" in c.message
    assert ledger.balance(user).available_kobo == 1_000_000


def test_wrong_amount_is_never_credited(user):
    r = cards.start(user, 1_000_000, save_card=False)
    c = cards.complete(r["reference"], {"status": "success", "amount_kobo": 100, "currency": "NGN", "message": "", "authorization": None})
    assert c.status == "failed" and ledger.balance(user).available_kobo == 0


def test_no_card_saved_when_not_asked(user):
    cards.complete(cards.start(user, 1_000_000, save_card=False)["reference"])
    assert not SavedCard.objects.filter(user=user).exists()


def test_amount_limits():
    with pytest.raises(FlowError):
        cards.quote(5_000)


def test_removed_card_cannot_be_charged(user):
    cards.complete(cards.start(user, 1_000_000, save_card=True)["reference"])
    card = SavedCard.objects.get(user=user)
    cards.remove_card(card)
    with pytest.raises(FlowError):
        cards.charge_saved_card(user, card, 1_000_000)


def test_card_fee_is_listed_with_its_top_up(user):
    from ledger.models import CardCharge, FeeLine
    import ledger.cards as lc
    charge = CardCharge.objects.create(user=user, reference="sdc_t1", net_kobo=5_000_000, fee_kobo=85_000, gross_kobo=5_085_000)
    lc.complete("sdc_t1", {"status": "success", "currency": "NGN", "amount_kobo": 5_085_000})
    lc.complete("sdc_t1", {"status": "success", "currency": "NGN", "amount_kobo": 5_085_000})
    f = FeeLine.objects.get(card_charge=charge)
    assert f.kind == "card_processing" and f.amount_kobo == 85_000 and f.paid_to == "provider"
    assert f.ledger_transaction.idempotency_key == "inflow:paystack:sdc_t1"


def test_bank_payment_credits_but_saves_no_card(user):
    r = cards.start(user, 1_000_000, save_card=True)
    charge = CardCharge.objects.get(reference=r["reference"])
    auth = {"authorization_code": "AUTH_bank", "reusable": True, "channel": "bank", "last4": "", "brand": "", "bank": "GTBank",
            "exp_month": "", "exp_year": "", "signature": ""}
    c = cards.complete(r["reference"], {"status": "success", "amount_kobo": charge.gross_kobo, "currency": "NGN", "message": "",
                                        "channel": "bank", "authorization": auth})
    assert c.status == "success" and ledger.balance(user).available_kobo == 1_000_000
    assert c.inflow.sender_name == "Bank top-up"
    assert not SavedCard.objects.filter(user=user).exists()


def test_checkout_offers_card_and_bank(settings, monkeypatch):
    from providers.paystack import PaystackCardGateway
    sent = {}

    class Client:
        secret_key = "sk_test_x"

        def call(self, method, path, json=None):
            sent.update(json)
            return 200, {"data": {"authorization_url": "https://checkout.paystack.com/x"}}

    PaystackCardGateway(Client()).initialize(email="a@b.co", amount_kobo=10_000, reference="r", callback_url="https://x", metadata={})
    assert sent["channels"] == ["card", "bank", "bank_transfer"]
