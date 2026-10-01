from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class ProviderError(Exception):
    """The provider call failed and we don't know the outcome (timeout, 5xx, bad response)."""


class TransferStatus(str, Enum):
    PENDING = "pending"
    SUCCESSFUL = "successful"
    FAILED = "failed"  # definitely not sent; safe to release the money
    NOT_FOUND = "not_found"  # provider has no record of this reference


@dataclass(frozen=True)
class TransferRequest:
    reference: str  # our run id; the provider must treat it as an idempotency key
    amount_kobo: int
    bank_code: str
    account_number: str
    account_name: str
    narration: str
    cbn_bank_code: str = ""  # Paystack identifies banks by CBN code
    recipient_code: str = ""  # Paystack recipient, if we registered this person before


@dataclass(frozen=True)
class TransferResult:
    status: TransferStatus
    provider_ref: str = ""
    session_id: str = ""
    message: str = ""
    raw: dict = field(default_factory=dict)
    recipient_code: str = ""  # Paystack: the recipient used, so we can remember it


@dataclass(frozen=True)
class NameEnquiryResult:
    account_name: str
    bank_code: str
    account_number: str


@dataclass(frozen=True)
class VirtualAccount:
    account_number: str
    bank_name: str
    bank_code: str
    account_name: str
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class InflowEvent:
    provider: str
    reference: str  # session id
    account_number: str  # which of our virtual accounts received it
    amount_kobo: int
    sender_name: str = ""
    successful: bool = True
    raw: dict = field(default_factory=dict)


class PaymentProvider(Protocol):
    name: str

    def name_enquiry(self, bank_code: str, account_number: str) -> NameEnquiryResult: ...
    def transfer(self, req: TransferRequest) -> TransferResult: ...
    def query_transfer(self, reference: str) -> TransferResult: ...
    def create_virtual_account(self, *, first_name: str, last_name: str, email: str, phone: str = "") -> VirtualAccount: ...
    def verify_inflow(self, session_id: str) -> InflowEvent | None: ...


class Messenger(Protocol):
    name: str

    def send(self, *, channel: str, to: str, body: str) -> str:
        """Send and return a status: 'sent', 'mocked' or 'failed'."""
        ...
