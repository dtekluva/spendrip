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
