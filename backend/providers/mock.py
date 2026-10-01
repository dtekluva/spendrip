"""
In-memory stand-ins so the whole app runs and is testable without real money.

MockPaymentProvider behaves like Liberty: a transfer is accepted as PENDING and becomes
SUCCESSFUL on the next status check. Test hooks:
  - account numbers ending in 0000 fail
  - `crash_next` makes the next transfer() raise mid-way (unknown outcome)
"""
from __future__ import annotations

import hashlib
import threading

from .base import InflowEvent, NameEnquiryResult, ProviderError, TransferRequest, TransferResult, TransferStatus, VirtualAccount

_FAKE_NAMES = ["ADAEZE N. OKONKWO", "TUNDE A. BELLO", "CHIOMA E. EZE", "IBRAHIM M. SANI", "FUNMI O. ADEYEMI"]


class MockPaymentProvider:
    name = "mock"

    def __init__(self):
        self._lock = threading.Lock()
        self.transfers: dict[str, dict] = {}
        self.inflows: dict[str, InflowEvent] = {}
        self.crash_next = False
        self.transfer_calls = 0

    def name_enquiry(self, bank_code, account_number):
        if len(account_number) != 10 or not account_number.isdigit():
            raise ValueError("Account number must be 10 digits")
        idx = int(hashlib.sha256(f"{bank_code}{account_number}".encode()).hexdigest(), 16) % len(_FAKE_NAMES)
        return NameEnquiryResult(account_name=_FAKE_NAMES[idx], bank_code=bank_code, account_number=account_number)

    def transfer(self, req: TransferRequest) -> TransferResult:
        with self._lock:
            self.transfer_calls += 1
            if req.reference in self.transfers:  # idempotent, like a real provider should be
                return self._result(req.reference)
            fail = req.account_number.endswith("0000")
            self.transfers[req.reference] = {"req": req, "status": TransferStatus.FAILED if fail else TransferStatus.PENDING, "checks": 0}
            if self.crash_next:
                self.crash_next = False
                raise ProviderError("connection reset after sending")  # recorded, but caller never hears back
            return self._result(req.reference)

    def query_transfer(self, reference):
        with self._lock:
            t = self.transfers.get(reference)
            if not t:
                return TransferResult(TransferStatus.NOT_FOUND)
            t["checks"] += 1
            if t["status"] == TransferStatus.PENDING:
                t["status"] = TransferStatus.SUCCESSFUL
            return self._result(reference)

    def _result(self, reference):
        t = self.transfers[reference]
        return TransferResult(t["status"], provider_ref=f"MOCK-{reference[:8]}",
                              session_id=f"0000{abs(hash(reference)) % 10**26:026d}" if t["status"] == TransferStatus.SUCCESSFUL else "")

    def create_virtual_account(self, *, first_name, last_name, email, phone=""):
        digits = int(hashlib.sha256(email.encode()).hexdigest(), 16) % 10**6
        return VirtualAccount(account_number=f"8420{digits:06d}", bank_name="Wema Bank (mock)", bank_code="000017",
                              account_name=f"SpenDrip/{first_name} {last_name}".strip())

    # Dev helper: pretend money arrived in one of our virtual accounts.
    def simulate_inflow(self, *, session_id: str, account_number: str, amount_kobo: int, sender_name: str = "DEMO SENDER") -> InflowEvent:
        ev = InflowEvent(provider=self.name, reference=session_id, account_number=account_number, amount_kobo=amount_kobo, sender_name=sender_name)
        self.inflows[session_id] = ev
        return ev

    def verify_inflow(self, session_id):
        return self.inflows.get(session_id)


class MockMessenger:
    """Doesn't send anything. The outbox row it leaves behind is what the app shows as 'would have sent'."""

    name = "mock"

    def __init__(self):
        self.sent: list[dict] = []

    def send(self, *, channel, to, body):
        self.sent.append({"channel": channel, "to": to, "body": body})
        return "mocked"


class MockKycProvider:
    name = "mock"

    def lookup_nin(self, nin: str) -> dict | None:
        if len(nin) != 11 or not nin.isdigit() or nin == "00000000000":
            return None
        # A different phone per NIN, so several test sign-ups don't collide.
        return {"first_name": "ADAEZE", "last_name": "OKONKWO", "date_of_birth": "1994-03-14", "phone": "080" + nin[-8:]}

    def check_document(self, image_bytes: bytes, *, id_type: str, expected_name: str) -> dict:
        return {"passed": len(image_bytes) > 0, "checks": ["corners_visible", "text_readable", "name_matches"]}

    def match_selfie(self, image_bytes: bytes) -> dict:
        return {"passed": len(image_bytes) > 0, "liveness": True, "score": 0.97}


class DbMockPaymentProvider(MockPaymentProvider):
    """The same mock, with its state in the database so it survives across processes (serverless, worker vs web)."""

    def transfer(self, req: TransferRequest) -> TransferResult:
        from django.db import IntegrityError, transaction

        from .models import MockTransfer

        self.transfer_calls += 1
        status = TransferStatus.FAILED if req.account_number.endswith("0000") else TransferStatus.PENDING
        try:
            with transaction.atomic():
                t = MockTransfer.objects.create(reference=req.reference, account_number=req.account_number,
                                                amount_kobo=req.amount_kobo, status=status.value)
        except IntegrityError:
            t = MockTransfer.objects.get(reference=req.reference)
        if self.crash_next:
            self.crash_next = False
            raise ProviderError("connection reset after sending")
        return self._db_result(t)

    def query_transfer(self, reference):
        from .models import MockTransfer

        t = MockTransfer.objects.filter(reference=reference).first()
        if not t:
            return TransferResult(TransferStatus.NOT_FOUND)
        t.checks += 1
        if t.status == TransferStatus.PENDING.value:
            t.status = TransferStatus.SUCCESSFUL.value
        t.save(update_fields=["checks", "status"])
        return self._db_result(t)

    @staticmethod
    def _db_result(t):
        status = TransferStatus(t.status)
        session = f"0000{t.pk:026d}" if status == TransferStatus.SUCCESSFUL else ""
        return TransferResult(status, provider_ref=f"MOCK-{t.reference[:8]}", session_id=session)


class MockCardGateway:
    """
    Test-mode card checkout (used when no Paystack key is set and dev tools are on). "Checkout" sends
    you straight back to the app; every charge succeeds with a reusable test Visa ••4081, except
    amounts ending in 13 kobo, which are declined so the failure path can be tried.
    """

    name = "mock-card"
    test_mode = True

    def __init__(self, return_url: str):
        self.return_url = return_url.rstrip("/")

    def _auth(self):
        return {"authorization_code": "AUTH_test_4081", "reusable": True, "last4": "4081", "brand": "visa", "bank": "TEST BANK",
                "exp_month": "12", "exp_year": "2030", "signature": "SIG_test_4081"}

    def initialize(self, *, email, amount_kobo, reference, callback_url, metadata):
        sep = "&" if "?" in callback_url else "?"
        return {"authorization_url": f"{callback_url}{sep}reference={reference}&test=1", "access_code": f"test_{reference[:10]}"}

    def verify(self, reference):
        from ledger.models import CardCharge
        c = CardCharge.objects.filter(reference=reference).first()
        if not c:
            return {"status": "failed", "amount_kobo": 0, "currency": "NGN", "reference": reference, "message": "Unknown payment", "authorization": None}
        ok = c.gross_kobo % 100 != 13
        return {"status": "success" if ok else "failed", "amount_kobo": c.gross_kobo, "currency": "NGN", "reference": reference,
                "message": "Approved" if ok else "Declined by the test bank", "authorization": self._auth() if ok else None}

    def charge_authorization(self, *, email, amount_kobo, authorization_code, reference, metadata):
        ok = amount_kobo % 100 != 13
        return {"status": "success" if ok else "failed", "amount_kobo": amount_kobo, "currency": "NGN", "reference": reference,
                "message": "Approved" if ok else "Declined by the test bank", "authorization": self._auth() if ok else None}

    def deactivate(self, authorization_code):
        return None
