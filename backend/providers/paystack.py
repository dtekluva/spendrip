"""
Paystack: card top-ups (with saved cards), payouts and account name checks.

Paystack works in kobo, like us. It identifies banks by CBN codes, so NIP codes from our recipients
are mapped through providers/banks.py. Docs: https://paystack.com/docs/api/
"""
from __future__ import annotations

import hashlib
import hmac
import json
from math import ceil

import requests

from .banks import BY_NIP
from .base import NameEnquiryResult, ProviderError, TransferRequest, TransferResult, TransferStatus

# Paystack local card pricing: 1.5% + ₦100 (the ₦100 is waived under ₦2,500), capped at ₦2,000.
CARD_PERCENT = 0.015
CARD_FLAT_KOBO = 10_000
CARD_FLAT_WAIVED_UNDER_KOBO = 250_000
CARD_CAP_KOBO = 200_000

_TRANSFER_STATUS = {
    "success": TransferStatus.SUCCESSFUL,
    "failed": TransferStatus.FAILED,
    "reversed": TransferStatus.FAILED,
    "abandoned": TransferStatus.FAILED,
    "blocked": TransferStatus.FAILED,
    "rejected": TransferStatus.FAILED,
    "pending": TransferStatus.PENDING,
    "received": TransferStatus.PENDING,
    "queued": TransferStatus.PENDING,
    "processing": TransferStatus.PENDING,
}


def card_fee_kobo(gross_kobo: int) -> int:
    """What Paystack keeps from a local card charge of `gross_kobo`."""
    flat = CARD_FLAT_KOBO if gross_kobo >= CARD_FLAT_WAIVED_UNDER_KOBO else 0
    return min(round(gross_kobo * CARD_PERCENT) + flat, CARD_CAP_KOBO)


def gross_for_net(net_kobo: int) -> int:
    """The amount to charge so that exactly `net_kobo` lands after Paystack's fee (fee passed on to the payer)."""
    gross = 0
    for flat in (0, CARD_FLAT_KOBO):  # the ₦100 applies only at ₦2,500 and above, so pick the consistent case
        gross = ceil((net_kobo + flat) / (1 - CARD_PERCENT))
        if (gross >= CARD_FLAT_WAIVED_UNDER_KOBO) == (flat > 0):
            break
    if round(gross * CARD_PERCENT) + (CARD_FLAT_KOBO if gross >= CARD_FLAT_WAIVED_UNDER_KOBO else 0) > CARD_CAP_KOBO:
        gross = net_kobo + CARD_CAP_KOBO
    while gross - card_fee_kobo(gross) < net_kobo:  # rounding: nudge up a kobo or two
        gross += 1
    while gross - 1 - card_fee_kobo(gross - 1) >= net_kobo:
        gross -= 1
    return gross


def verify_webhook(secret: str, raw_body: bytes, signature: str) -> bool:
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest()
    return bool(signature) and hmac.compare_digest(expected, signature)


class PaystackClient:
    def __init__(self, *, secret_key: str, base_url: str = "https://api.paystack.co", timeout: int = 20, session: requests.Session | None = None):
        if not secret_key:
            raise ValueError("PAYSTACK_SECRET_KEY is not set")
        self.secret_key, self.base_url, self.timeout = secret_key, base_url.rstrip("/"), timeout
        self.http = session or requests.Session()

    def call(self, method: str, path: str, **kw) -> tuple[int, dict]:
        try:
            resp = self.http.request(method, self.base_url + path, timeout=self.timeout,
                                     headers={"Authorization": f"Bearer {self.secret_key}", "Content-Type": "application/json"}, **kw)
        except requests.RequestException as e:
            raise ProviderError(f"Paystack {path}: {e}") from e
        if resp.status_code >= 500:
            raise ProviderError(f"Paystack {path}: HTTP {resp.status_code}")
        try:
            body = resp.json()
        except ValueError as e:
            raise ProviderError(f"Paystack {path}: response was not JSON") from e
        return resp.status_code, body


# ---------------------------------------------------------------- payouts + name checks

class PaystackProvider:
    """Payout provider. Funding accounts (account numbers) still come from the accounts provider (Liberty)."""

    name = "paystack"

    def __init__(self, client: PaystackClient):
        self.client = client

    @staticmethod
    def _cbn(nip_code: str) -> str:
        bank = BY_NIP.get(nip_code)
        if not bank or not bank[1]:
            raise ValueError("Paystack can't pay this bank yet. Choose another bank.")
        return bank[1]

    def name_enquiry(self, bank_code, account_number):
        status, body = self.client.call("GET", "/bank/resolve", params={"account_number": account_number, "bank_code": self._cbn(bank_code)})
        name = (body.get("data") or {}).get("account_name") if body.get("status") else None
        if status >= 400 or not name:
            raise ValueError("We couldn't find that account. Check the number and bank.")
        return NameEnquiryResult(account_name=name.strip(), bank_code=bank_code, account_number=account_number)

    def create_recipient(self, req: TransferRequest) -> str:
        status, body = self.client.call("POST", "/transferrecipient", json={
            "type": "nuban", "name": req.account_name, "account_number": req.account_number,
            "bank_code": req.cbn_bank_code or self._cbn(req.bank_code), "currency": "NGN"})
        code = (body.get("data") or {}).get("recipient_code")
        if status >= 400 or not code:
            raise ProviderError(f"Paystack couldn't register this recipient: {body.get('message', '')}")
        return code

    def transfer(self, req: TransferRequest) -> TransferResult:
        recipient = req.recipient_code or self.create_recipient(req)
        status, body = self.client.call("POST", "/transfer", json={
            "source": "balance", "amount": req.amount_kobo, "recipient": recipient,
            "reference": req.reference, "reason": req.narration[:100], "currency": "NGN"})
        data = body.get("data") or {}
        msg = str(body.get("message", ""))
        if status >= 400:
            if "duplicate" in msg.lower():
                # We sent this reference before: never resend, let the status check decide.
                return TransferResult(TransferStatus.PENDING, message=msg, raw=body, recipient_code=recipient)
            return TransferResult(TransferStatus.FAILED, message=msg[:300], raw=body, recipient_code=recipient)
        if data.get("status") == "otp":
            # Transfer OTP is on for this Paystack account, so the transfer was not sent.
            return TransferResult(TransferStatus.FAILED, raw=body, recipient_code=recipient,
                                  message="Paystack is asking for an OTP. Turn off transfer OTP in the Paystack dashboard to allow scheduled payouts.")
        st = _TRANSFER_STATUS.get(str(data.get("status", "")).lower(), TransferStatus.PENDING)
        return TransferResult(st, provider_ref=data.get("transfer_code", ""), raw=body, recipient_code=recipient)

    def query_transfer(self, reference):
        status, body = self.client.call("GET", f"/transfer/verify/{reference}")
        if status == 404 or (status >= 400 and "not found" in str(body.get("message", "")).lower()):
            return TransferResult(TransferStatus.NOT_FOUND, raw=body)
        if status >= 400:
            raise ProviderError(f"Paystack transfer check failed: {body.get('message', '')}")
        data = body.get("data") or {}
        st = _TRANSFER_STATUS.get(str(data.get("status", "")).lower(), TransferStatus.PENDING)
        return TransferResult(st, provider_ref=data.get("transfer_code", ""), session_id=str(data.get("session", {}).get("id", "") if isinstance(data.get("session"), dict) else ""), raw=body)

    def create_virtual_account(self, **kw):
        raise ProviderError("Account numbers come from the accounts provider, not Paystack")

    def verify_inflow(self, session_id):
        return None


# ---------------------------------------------------------------- card top-ups

def _charge(data: dict) -> dict:
    """Normalise a Paystack transaction into what the card service needs."""
    auth = data.get("authorization") or {}
    return {
        "status": str(data.get("status", "")).lower(),  # success | failed | abandoned | ongoing | pending | send_otp ...
        "amount_kobo": int(data.get("amount") or 0),
        "currency": data.get("currency", "NGN"),
        "reference": data.get("reference", ""),
        "message": data.get("gateway_response") or data.get("message") or "",
        "authorization": {
            "authorization_code": auth.get("authorization_code", ""), "reusable": bool(auth.get("reusable")),
            "last4": auth.get("last4", ""), "brand": (auth.get("brand") or auth.get("card_type") or "").strip(),
            "bank": auth.get("bank", ""), "exp_month": str(auth.get("exp_month", "")), "exp_year": str(auth.get("exp_year", "")),
            "signature": auth.get("signature", ""),
        } if auth else None,
    }


class PaystackCardGateway:
    name = "paystack"

    def __init__(self, client: PaystackClient):
        self.client = client
        self.test_mode = client.secret_key.startswith("sk_test_")  # Paystack's test environment: no real money

    def initialize(self, *, email, amount_kobo, reference, callback_url, metadata):
        status, body = self.client.call("POST", "/transaction/initialize", json={
            "email": email, "amount": amount_kobo, "reference": reference, "callback_url": callback_url,
            "currency": "NGN", "channels": ["card"], "metadata": json.dumps(metadata)})
        data = body.get("data") or {}
        if status >= 400 or not data.get("authorization_url"):
            raise ProviderError(f"Paystack couldn't start the payment: {body.get('message', '')}")
        return {"authorization_url": data["authorization_url"], "access_code": data.get("access_code", "")}

    def verify(self, reference):
        status, body = self.client.call("GET", f"/transaction/verify/{reference}")
        if status >= 400 or not body.get("status"):
            raise ProviderError(f"Paystack couldn't check this payment: {body.get('message', '')}")
        return _charge(body.get("data") or {})

    def charge_authorization(self, *, email, amount_kobo, authorization_code, reference, metadata):
        status, body = self.client.call("POST", "/transaction/charge_authorization", json={
            "email": email, "amount": amount_kobo, "authorization_code": authorization_code, "reference": reference,
            "currency": "NGN", "metadata": json.dumps(metadata)})
        if status >= 400 and not body.get("data"):
            return {"status": "failed", "amount_kobo": amount_kobo, "currency": "NGN", "reference": reference,
                    "message": body.get("message", "The card was declined."), "authorization": None}
        return _charge(body.get("data") or {})

    def deactivate(self, authorization_code):
        self.client.call("POST", "/customer/deactivate_authorization", json={"authorization_code": authorization_code})
