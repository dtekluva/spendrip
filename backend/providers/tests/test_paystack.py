import hashlib
import hmac
import json

import pytest

from providers import TransferRequest, TransferStatus
from providers.paystack import PaystackClient, PaystackProvider, card_fee_kobo, gross_for_net, verify_webhook


class FakeResp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def request(self, method, url, **kw):
        path = url.split("api.paystack.test", 1)[1]
        self.calls.append((method, path, kw))
        r = self.routes[(method, path)]
        return r(kw) if callable(r) else r


def provider(routes):
    s = FakeSession(routes)
    return PaystackProvider(PaystackClient(secret_key="sk_test_x", base_url="https://api.paystack.test", session=s)), s


REQ = TransferRequest(reference="0b4f2b8e-1111-4c4c-9c9c-123456789abc", amount_kobo=3_000_000, bank_code="000013",
                      account_number="0244132018", account_name="ADA OKONKWO", narration="SpenDrip Mum")


@pytest.mark.parametrize("net", [10_000, 200_000, 249_000, 250_000, 5_000_000, 50_000_000, 200_000_000])
def test_passing_on_the_card_fee_lands_exactly_the_amount(net):
    gross = gross_for_net(net)
    assert gross - card_fee_kobo(gross) >= net
    assert (gross - 1) - card_fee_kobo(gross - 1) < net  # and it's the smallest such charge


def test_card_fee_rules():
    assert card_fee_kobo(200_000) == 3_000  # ₦2,000: 1.5%, flat fee waived
    assert card_fee_kobo(5_000_000) == 85_000  # ₦50,000: 1.5% + ₦100
    assert card_fee_kobo(500_000_000) == 200_000  # capped at ₦2,000


def test_webhook_signature():
    body = json.dumps({"event": "charge.success"}).encode()
    sig = hmac.new(b"sk_test_x", body, hashlib.sha512).hexdigest()
    assert verify_webhook("sk_test_x", body, sig)
    assert not verify_webhook("sk_test_x", body, "nope")
    assert not verify_webhook("sk_test_x", body + b" ", sig)


def test_transfer_registers_recipient_with_cbn_code_and_sends_kobo():
    p, s = provider({
        ("POST", "/transferrecipient"): FakeResp(201, {"status": True, "data": {"recipient_code": "RCP_abc"}}),
        ("POST", "/transfer"): FakeResp(200, {"status": True, "data": {"status": "pending", "transfer_code": "TRF_1"}}),
    })
    r = p.transfer(REQ)
    assert r.status == TransferStatus.PENDING and r.recipient_code == "RCP_abc" and r.provider_ref == "TRF_1"
    assert s.calls[0][2]["json"]["bank_code"] == "058"  # GTBank's CBN code, mapped from NIP 000013
    sent = s.calls[1][2]["json"]
    assert sent["amount"] == 3_000_000 and sent["recipient"] == "RCP_abc" and sent["reference"] == REQ.reference


def test_known_recipient_is_not_registered_again():
    from dataclasses import replace
    p, s = provider({("POST", "/transfer"): FakeResp(200, {"status": True, "data": {"status": "success"}})})
    assert p.transfer(replace(REQ, recipient_code="RCP_known")).status == TransferStatus.SUCCESSFUL
    assert [c[1] for c in s.calls] == ["/transfer"]


def test_duplicate_reference_is_checked_not_failed():
    from dataclasses import replace
    p, _ = provider({("POST", "/transfer"): FakeResp(400, {"status": False, "message": "Duplicate Transfer Reference"})})
    assert p.transfer(replace(REQ, recipient_code="RCP_k")).status == TransferStatus.PENDING


def test_transfer_otp_means_not_sent():
    from dataclasses import replace
    p, _ = provider({("POST", "/transfer"): FakeResp(200, {"status": True, "data": {"status": "otp"}})})
    r = p.transfer(replace(REQ, recipient_code="RCP_k"))
    assert r.status == TransferStatus.FAILED and "OTP" in r.message


def test_status_check_maps_reversed_and_not_found():
    p, _ = provider({("GET", f"/transfer/verify/{REQ.reference}"): FakeResp(200, {"status": True, "data": {"status": "reversed"}})})
    assert p.query_transfer(REQ.reference).status == TransferStatus.FAILED
    p, _ = provider({("GET", f"/transfer/verify/{REQ.reference}"): FakeResp(404, {"status": False, "message": "Transfer not found"})})
    assert p.query_transfer(REQ.reference).status == TransferStatus.NOT_FOUND


def test_name_check_uses_cbn_code():
    p, s = provider({("GET", "/bank/resolve"): FakeResp(200, {"status": True, "data": {"account_name": "ADAEZE OKONKWO "}})})
    assert p.name_enquiry("100004", "9028906357").account_name == "ADAEZE OKONKWO"
    assert s.calls[0][2]["params"] == {"account_number": "9028906357", "bank_code": "999992"}  # OPay
