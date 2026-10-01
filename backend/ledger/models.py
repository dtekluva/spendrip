"""
Double-entry, append-only ledger. Our ledger is the only record of each user's balance:
the money itself sits in one Liberty pool account.

Every transaction's entries sum to zero. Balances are SUM(entries) per account, so there is
no balance column that can drift. Sign convention: positive = more money in that account.

  user wallet   wallet:<user_id>   spendable balance
  user held     held:<user_id>     set aside for a transfer that is in flight
  liberty_pool  system             counter-account for money in and out of the Liberty pool
  paystack      system             counter-account for card top-ups
  fees          system             transfer fees
"""
from django.conf import settings
from django.db import models


class LedgerAccount(models.Model):
    class Kind(models.TextChoices):
        WALLET = "wallet"
        HELD = "held"
        SYSTEM = "system"

    code = models.CharField(max_length=80, unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="ledger_accounts")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


class LedgerTransaction(models.Model):
    idempotency_key = models.CharField(max_length=160, unique=True)
    kind = models.CharField(max_length=20)  # top_up | reserve | settle | release | adjust
    memo = models.CharField(max_length=200, blank=True)
    run = models.ForeignKey("drips.Run", null=True, blank=True, on_delete=models.PROTECT, related_name="ledger_transactions")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.idempotency_key


class LedgerEntry(models.Model):
    transaction = models.ForeignKey(LedgerTransaction, on_delete=models.PROTECT, related_name="entries")
    account = models.ForeignKey(LedgerAccount, on_delete=models.PROTECT, related_name="entries")
    amount_kobo = models.BigIntegerField()

    class Meta:
        indexes = [models.Index(fields=["account"])]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Ledger entries are append-only")
        super().save(*args, **kwargs)


class FundingAccount(models.Model):
    """A user's personal account number (a Liberty virtual account). Transfers into it fund their wallet."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="funding_accounts")
    provider = models.CharField(max_length=20)
    account_number = models.CharField(max_length=20, unique=True)
    bank_name = models.CharField(max_length=80)
    bank_code = models.CharField(max_length=10)
    account_name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)


class Inflow(models.Model):
    """Money that arrived (bank transfer or card). Credited only once verified, and only once."""

    class Status(models.TextChoices):
        RECEIVED = "received"
        CREDITED = "credited"
        REJECTED = "rejected"

    provider = models.CharField(max_length=20)
    reference = models.CharField(max_length=120)  # provider session id / reference
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="inflows")
    funding_account = models.ForeignKey(FundingAccount, null=True, blank=True, on_delete=models.PROTECT)
    amount_kobo = models.BigIntegerField()
    sender_name = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RECEIVED)
    reject_reason = models.CharField(max_length=200, blank=True)
    raw = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    credited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "reference"], name="inflow_unique_provider_ref")]


class SavedCard(models.Model):
    """A card saved through Paystack. We keep only Paystack's reusable token (encrypted) and display details."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cards")
    provider = models.CharField(max_length=20, default="paystack")
    authorization_code_enc = models.TextField()  # encrypted; never sent to the browser
    signature = models.CharField(max_length=120)  # Paystack's id for the physical card, to avoid saving it twice
    brand = models.CharField(max_length=20, blank=True)
    last4 = models.CharField(max_length=4)
    bank = models.CharField(max_length=80, blank=True)
    exp_month = models.CharField(max_length=2, blank=True)
    exp_year = models.CharField(max_length=4, blank=True)
    email = models.CharField(max_length=120)  # Paystack ties the token to the email it was charged with
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "signature"], name="card_unique_per_user")]


class CardCharge(models.Model):
    """One card top-up attempt. `net_kobo` is what lands in the wallet; `gross_kobo` is what the card is charged."""

    class Status(models.TextChoices):
        STARTED = "started"
        SUCCESS = "success"
        FAILED = "failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="card_charges")
    reference = models.CharField(max_length=64, unique=True)
    net_kobo = models.BigIntegerField()
    fee_kobo = models.BigIntegerField()
    gross_kobo = models.BigIntegerField()
    save_card = models.BooleanField(default=True)
    card = models.ForeignKey(SavedCard, null=True, blank=True, on_delete=models.SET_NULL, related_name="charges")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.STARTED)
    message = models.CharField(max_length=200, blank=True)
    inflow = models.OneToOneField(Inflow, null=True, blank=True, on_delete=models.PROTECT, related_name="card_charge")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
