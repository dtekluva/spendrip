import base64
import json
import time

import pytest

from providers import ProviderError, TransferRequest, TransferStatus
from providers.liberty import LibertyProvider


def jwt(exp):
    body = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"h.{body}.s"


class FakeResp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        path = url.split("banking.test", 1)[1]
        r = self.routes[(method, path)]
        return r(kw) if callable(r) else r


def provider(routes):
    login = FakeResp(200, {"data": {"access": jwt(time.time() + 3600)}})
    session = FakeSession({("POST", "/api/v1/companies/auth/login/"): login, **routes})
    return LibertyProvider(base_url="https://banking.test", email="e", password="p", api_key="k", source_account="8420000002",
                           session=session), session


REQ = TransferRequest(reference="run-1", amount_kobo=5_005_000, bank_code="000013", account_number="0244132018",
                      account_name="ADA", narration="SpenDrip Mum")


def test_transfer_sends_naira_with_our_reference_and_maps_pending():
    p, s = provider({("POST", "/accounts/transfer_money/"): FakeResp(200, {"data": {"transaction": {"status": "PENDING", "request_reference": "run-1"}}})})
    r = p.transfer(REQ)
    assert r.status == TransferStatus.PENDING
    method, url, kw = s.calls[-1]
    assert kw["json"]["amount"] == 50_050.0 and kw["json"]["request_reference"] == "run-1"
    assert kw["json"]["source_account"] == "8420000002" and kw["headers"]["Authorization"].startswith("Bearer ")


def test_transfer_rejected_with_4xx_is_a_definite_failure():
    p, _ = provider({("POST", "/accounts/transfer_money/"): FakeResp(400, {"errors": {"amount": "insufficient"}})})
    assert p.transfer(REQ).status == TransferStatus.FAILED


def test_server_error_means_unknown_outcome():
    p, _ = provider({("POST", "/accounts/transfer_money/"): FakeResp(502, {})})
    with pytest.raises(ProviderError):
        p.transfer(REQ)


def test_status_query_finds_our_reference():
    body = {"data": {"transactions": [{"company_reference": "run-1", "transaction_status": "SUCCESSFUL", "session_id": "0000172408"}]}}
    p, _ = provider({("GET", "/accounts/verify_transfer"): FakeResp(200, body)})
    r = p.query_transfer("run-1")
    assert r.status == TransferStatus.SUCCESSFUL and r.session_id == "0000172408"


def test_status_query_with_no_match_is_not_found():
    p, _ = provider({("GET", "/accounts/verify_transfer"): FakeResp(200, {"data": {"transactions": []}})})
    assert p.query_transfer("run-1").status == TransferStatus.NOT_FOUND


def test_name_enquiry_uses_api_key():
    p, s = provider({("POST", "/api/v1/core/account_name_enquiry/"): FakeResp(200, {"data": {"account_name": " ADAEZE OKONKWO "}})})
    assert p.name_enquiry("100004", "9028906357").account_name == "ADAEZE OKONKWO"
    assert s.calls[-1][2]["headers"]["Authorization"] == "Api_key k"


def test_inflow_amount_is_converted_to_kobo():
    body = {"data": {"type": "CREDIT", "status": "SUCCESSFUL", "amount": 7000, "session_id": "100004", "recipient_account_number": "8420330457"}}
    p, _ = provider({("GET", "/api/v1/wema/verify_event"): FakeResp(200, body)})
    ev = p.verify_inflow("100004")
    assert ev.amount_kobo == 700_000 and ev.successful
