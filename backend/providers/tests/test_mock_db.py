import pytest

from providers import TransferRequest, TransferStatus
from providers.mock import DbMockPaymentProvider


@pytest.mark.django_db
def test_db_mock_keeps_state_across_instances():
    req = TransferRequest(reference="r1", amount_kobo=100, bank_code="000013", account_number="0244132018", account_name="A", narration="x")
    assert DbMockPaymentProvider().transfer(req).status == TransferStatus.PENDING
    assert DbMockPaymentProvider().transfer(req).status == TransferStatus.PENDING  # idempotent
    assert DbMockPaymentProvider().query_transfer("r1").status == TransferStatus.SUCCESSFUL  # a "new process" still knows it
    assert DbMockPaymentProvider().query_transfer("nope").status == TransferStatus.NOT_FOUND
