"""
Liberty Pay Core Banking adapter.

Endpoints come from Liberty's Postman collection ("Core Banking Service"). Liberty works in
naira; we work in kobo, so amounts are converted at this edge only. Status strings are mapped
onto our TransferStatus. Anything we don't recognise is treated as PENDING, so we keep asking
rather than guess.

Not live-tested yet: the sandbox and webhook payloads are still to come (docs/PLAN.md §9).
"""
from __future__ import annotations

import base64
import json
import time
from decimal import Decimal

import requests

from .base import InflowEvent, NameEnquiryResult, ProviderError, TransferRequest, TransferResult, TransferStatus, VirtualAccount

_STATUS = {
    "SUCCESSFUL": TransferStatus.SUCCESSFUL,
    "SUCCESS": TransferStatus.SUCCESSFUL,
    "FAILED": TransferStatus.FAILED,
    "REVERSED": TransferStatus.FAILED,
    "PENDING": TransferStatus.PENDING,
    "PROCESSING": TransferStatus.PENDING,
}


def _naira(kobo: int) -> float:
    return float(Decimal(kobo) / 100)


def _kobo(naira) -> int:
    return int((Decimal(str(naira)) * 100).to_integral_value())


class LibertyProvider:
    name = "liberty"

    def __init__(self, *, base_url: str, email: str, password: str, api_key: str, source_account: str,
                 mode: str = "LIVE", timeout: int = 20, session: requests.Session | None = None):
        self.base_url = base_url.rstrip("/")
        self.email, self.password, self.api_key = email, password, api_key
        self.source_account, self.mode, self.timeout = source_account, mode, timeout
        self.http = session or requests.Session()
        self._token: str | None = None
        self._token_exp = 0.0

    # ---------- auth ----------
    def _bearer(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        data = self._call("POST", "/api/v1/companies/auth/login/", auth=None, json={"email": self.email, "password": self.password})
        token = (data.get("data") or {}).get("access")
        if not token:
            raise ProviderError("Liberty login returned no access token")
        self._token, self._token_exp = token, _jwt_exp(token)
        return token

    def _call(self, method: str, path: str, *, auth: str | None = "bearer", **kw) -> dict:
        headers = kw.pop("headers", {})
        if auth == "bearer":
            headers["Authorization"] = f"Bearer {self._bearer()}"
        elif auth == "api_key":
            headers["Authorization"] = f"Api_key {self.api_key}"
        try:
            resp = self.http.request(method, self.base_url + path, headers=headers, timeout=self.timeout, **kw)
        except requests.RequestException as e:
            raise ProviderError(f"Liberty {path}: {e}") from e
        if resp.status_code >= 500:
            raise ProviderError(f"Liberty {path}: HTTP {resp.status_code}")
        try:
            body = resp.json()
        except ValueError as e:
            raise ProviderError(f"Liberty {path}: response was not JSON") from e
        if resp.status_code >= 400:
            body.setdefault("_http_status", resp.status_code)
        return body

    # ---------- money out ----------
    def transfer(self, req: TransferRequest) -> TransferResult:
        body = self._call("POST", "/accounts/transfer_money/", json={
            "source_account": self.source_account,
            "mode": self.mode,
            "account_name": req.account_name,
            "account_number": req.account_number,
            "bank_code": req.bank_code,
            "request_reference": req.reference,
            "amount": _naira(req.amount_kobo),
            "narration": req.narration[:60],
            "service_provider": "WEMA_BANK",
        })
        if body.get("_http_status") and 400 <= body["_http_status"] < 500:
            # Rejected before sending (validation, insufficient pool funds, bad account).
            return TransferResult(TransferStatus.FAILED, message=json.dumps(body.get("errors") or body)[:500], raw=body)
        tx = ((body.get("data") or {}).get("transaction")) or {}
        status = _STATUS.get(str(tx.get("status", "")).upper(), TransferStatus.PENDING)
        return TransferResult(status, provider_ref=tx.get("request_reference", ""), session_id=tx.get("session_id") or "", raw=body)

    def query_transfer(self, reference: str) -> TransferResult:
        body = self._call("GET", "/accounts/verify_transfer", params={"search": reference})
        txs = ((body.get("data") or {}).get("transactions")) or []
        tx = next((t for t in txs if t.get("company_reference") == reference or t.get("request_reference") == reference), None)
        if not tx:
            return TransferResult(TransferStatus.NOT_FOUND, raw=body)
        status = _STATUS.get(str(tx.get("transaction_status", "")).upper(), TransferStatus.PENDING)
        return TransferResult(status, provider_ref=tx.get("reference", ""), session_id=tx.get("session_id") or "", raw=body)

    def name_enquiry(self, bank_code: str, account_number: str) -> NameEnquiryResult:
        body = self._call("POST", "/api/v1/core/account_name_enquiry/", auth="api_key",
                          json={"bank_code": bank_code, "account_number": account_number})
        data = body.get("data") or body
        name = data.get("account_name") or data.get("accountname") or ""
        if not name:
            raise ValueError("We couldn't find that account. Check the number and bank.")
        return NameEnquiryResult(account_name=name.strip(), bank_code=bank_code, account_number=account_number)

    # ---------- money in ----------
    def create_virtual_account(self, *, first_name, last_name, email, phone=""):
        payload = {"first_name": first_name, "last_name": last_name, "email": email}
        if phone:
            payload["phone"] = phone
        body = self._call("POST", "/api/v1/wema/virtual_accounts/", json=payload)
        acct = (body.get("data") or {}).get("account_details") or {}
        if not acct.get("account_number"):
            raise ProviderError("Liberty did not return an account number")
        return VirtualAccount(
            account_number=acct["account_number"], bank_name=acct.get("bank_name", "Wema Bank"),
            bank_code=acct.get("bank_code", "000017"),
            account_name=" ".join(x for x in [acct.get("account_name_prefix"), acct.get("first_name"), acct.get("last_name")] if x),
            raw=body,
        )

    def verify_inflow(self, session_id: str) -> InflowEvent | None:
        body = self._call("GET", "/api/v1/wema/verify_event", params={"session_id": session_id})
        d = body.get("data") or {}
        if not d or d.get("type") != "CREDIT":
            return None
        return InflowEvent(
            provider=self.name, reference=d.get("session_id", session_id), account_number=d.get("recipient_account_number", ""),
            amount_kobo=_kobo(d.get("amount", 0)), sender_name=d.get("details", ""),
            successful=str(d.get("status", "")).upper() == "SUCCESSFUL", raw=body,
        )


def _jwt_exp(token: str) -> float:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except (IndexError, KeyError, ValueError):
        return time.time() + 300
