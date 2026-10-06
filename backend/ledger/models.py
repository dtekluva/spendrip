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
    # Running balance, moved only by ledger.services.post() under a row lock. Always equals the sum of its entries.
    balance_kobo = models.BigIntegerField(default=0)
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
    # The account's balance just before and just after this entry, recorded when it was posted.
    balance_before_kobo = models.BigIntegerField(null=True)
    balance_after_kobo = models.BigIntegerField(null=True)

    class Meta:
        indexes = [models.Index(fields=["account"])]
        verbose_name_plural = "ledger entries"

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
    source = models.CharField(max_length=10, default="manual")  # manual | autofill
    card = models.ForeignKey(SavedCard, null=True, blank=True, on_delete=models.SET_NULL, related_name="charges")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.STARTED)
    message = models.CharField(max_length=200, blank=True)
    inflow = models.OneToOneField(Inflow, null=True, blank=True, on_delete=models.PROTECT, related_name="card_charge")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class FeeLine(models.Model):
    """
    One fee, traceable to where it came from. Written in the same database transaction as the ledger
    posting that moved the money, so the Fees table always agrees with the fee accounts.
    """

    class Kind(models.TextChoices):
        SERVICE = "service", "SpenDrip fee"
        PROVIDER = "provider", "Transfer fee (Paystack)"
        STAMP_DUTY = "stamp_duty", "Stamp duty"
        CARD = "card_processing", "Card fee (Paystack)"

    class PaidTo(models.TextChoices):
        SPENDRIP = "spendrip", "SpenDrip (income)"
        PROVIDER = "provider", "Payment provider"
        GOVERNMENT = "government", "Government (FIRS)"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    paid_to = models.CharField(max_length=12, choices=PaidTo.choices)
    amount_kobo = models.BigIntegerField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="fee_lines")
    run = models.ForeignKey("drips.Run", null=True, blank=True, on_delete=models.PROTECT, related_name="fee_lines")
    card_charge = models.ForeignKey(CardCharge, null=True, blank=True, on_delete=models.PROTECT, related_name="fee_lines")
    ledger_transaction = models.ForeignKey(LedgerTransaction, null=True, blank=True, on_delete=models.PROTECT, related_name="fee_lines")
    account_code = models.CharField(max_length=80, blank=True)  # the ledger account it was posted to, if on our books
    provider = models.CharField(max_length=20, blank=True)
    reference = models.CharField(max_length=120, blank=True)  # the transfer or charge reference at the provider
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["run", "kind"], condition=models.Q(run__isnull=False), name="fee_once_per_run_kind"),
            models.UniqueConstraint(fields=["card_charge", "kind"], condition=models.Q(card_charge__isnull=False), name="fee_once_per_charge_kind"),
        ]
        indexes = [models.Index(fields=["kind", "created_at"])]

    def __str__(self):
        return f"{self.get_kind_display()} ₦{self.amount_kobo / 100:,.2f}"
