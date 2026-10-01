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
        return {"first_name": "ADAEZE", "last_name": "OKONKWO", "date_of_birth": "1994-03-14", "phone": "08031234417"}

    def check_document(self, image_bytes: bytes, *, id_type: str, expected_name: str) -> dict:
        return {"passed": len(image_bytes) > 0, "checks": ["corners_visible", "text_readable", "name_matches"]}

    def match_selfie(self, image_bytes: bytes) -> dict:
        return {"passed": len(image_bytes) > 0, "liveness": True, "score": 0.97}
