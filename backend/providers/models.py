from django.db import models


class MockTransfer(models.Model):
    """
    State for the mock payment provider. Kept in the database (not memory) so the mock behaves
    the same when every request runs in a fresh process, as on Vercel.
    """

    reference = models.CharField(max_length=64, unique=True)
    account_number = models.CharField(max_length=10)
    amount_kobo = models.BigIntegerField()
    status = models.CharField(max_length=12)
    checks = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class ResolvedAccount(models.Model):
    """An account name a bank confirmed. Reused so saving a recipient (or adding the same account again)
    doesn't spend another name check; refreshed after a while in case the account changes hands."""

    nip_bank_code = models.CharField(max_length=10)
    account_number = models.CharField(max_length=10)
    account_name = models.CharField(max_length=120)
    provider = models.CharField(max_length=20)
    resolved_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["nip_bank_code", "account_number"], name="resolved_account_unique")]
