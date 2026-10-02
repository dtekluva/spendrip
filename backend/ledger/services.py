"""Ledger operations. Every operation is idempotent through its idempotency key."""
from __future__ import annotations

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from .models import FeeLine, Inflow, LedgerAccount, LedgerEntry, LedgerTransaction

LIBERTY_POOL = "liberty_pool"
PAYSTACK = "paystack"
FEES = "fees"  # SpenDrip's own fee income
FEES_PROVIDER = "fees:provider"  # transfer charges passed through to the payout provider
FEES_STAMP_DUTY = "fees:stamp_duty"  # stamp duty collected, owed to government
SYSTEM_ACCOUNTS = (LIBERTY_POOL, PAYSTACK, FEES, FEES_PROVIDER, FEES_STAMP_DUTY)
FEE_ACCOUNTS = {"service": (FEES, FeeLine.PaidTo.SPENDRIP), "provider": (FEES_PROVIDER, FeeLine.PaidTo.PROVIDER),
                "stamp_duty": (FEES_STAMP_DUTY, FeeLine.PaidTo.GOVERNMENT)}


class LedgerError(Exception):
    pass


class InsufficientFunds(LedgerError):
    def __init__(self, available_kobo: int, needed_kobo: int):
        super().__init__(f"available {available_kobo} kobo, needed {needed_kobo} kobo")
        self.available_kobo = available_kobo
        self.needed_kobo = needed_kobo


@dataclass(frozen=True)
class Balance:
    available_kobo: int  # spendable now
    held_kobo: int  # set aside for transfers in flight

    @property
    def total_kobo(self) -> int:
        return self.available_kobo + self.held_kobo


def wallet_code(user_id) -> str:
    return f"wallet:{user_id}"


def held_code(user_id) -> str:
    return f"held:{user_id}"


def account(code: str, *, kind: str = LedgerAccount.Kind.SYSTEM, user=None) -> LedgerAccount:
    acct, _ = LedgerAccount.objects.get_or_create(code=code, defaults={"kind": kind, "user": user})
    return acct


def ensure_user_accounts(user) -> tuple[LedgerAccount, LedgerAccount]:
    return (
        account(wallet_code(user.pk), kind=LedgerAccount.Kind.WALLET, user=user),
        account(held_code(user.pk), kind=LedgerAccount.Kind.HELD, user=user),
    )


def account_balance(code: str) -> int:
    total = LedgerEntry.objects.filter(account__code=code).aggregate(s=Sum("amount_kobo"))["s"]
    return int(total or 0)


def balance(user) -> Balance:
    return Balance(available_kobo=account_balance(wallet_code(user.pk)), held_kobo=account_balance(held_code(user.pk)))


def post(key: str, kind: str, lines: list[tuple[str, int]], *, memo: str = "", run=None) -> tuple[LedgerTransaction, bool]:
    """
    Write one balanced transaction. Returns (transaction, created). Posting the same key again
    returns the existing transaction and changes nothing.
    """
    if sum(amount for _, amount in lines) != 0:
        raise LedgerError(f"{key}: entries must sum to zero")
    if any(amount == 0 for _, amount in lines) or len(lines) < 2:
        raise LedgerError(f"{key}: needs at least two non-zero entries")
    existing = LedgerTransaction.objects.filter(idempotency_key=key).first()
    if existing:
        return existing, False
    try:
        with transaction.atomic():
            tx = LedgerTransaction.objects.create(idempotency_key=key, kind=kind, memo=memo, run=run)
            # Lock every account this posting touches (in a fixed order, so two postings can't deadlock),
            # then record each entry's balance before and after.
            codes = sorted({c for c, _ in lines})
            accounts = {a.code: a for a in LedgerAccount.objects.select_for_update().filter(code__in=codes).order_by("code")}
            missing = set(codes) - accounts.keys()
            if missing:
                raise LedgerError(f"{key}: unknown accounts {sorted(missing)}")
            entries = []
            for c, a in lines:
                acct = accounts[c]
                before = acct.balance_kobo
                acct.balance_kobo = before + a
                entries.append(LedgerEntry(transaction=tx, account=acct, amount_kobo=a, balance_before_kobo=before,
                                           balance_after_kobo=acct.balance_kobo))
            LedgerEntry.objects.bulk_create(entries)
            for acct in accounts.values():
                LedgerAccount.objects.filter(pk=acct.pk).update(balance_kobo=acct.balance_kobo)
            return tx, True
    except IntegrityError:
        # Another process posted the same key at the same moment.
        return LedgerTransaction.objects.get(idempotency_key=key), False


def lock_wallet(user) -> LedgerAccount:
    """Row lock on the user's wallet so two runs can't spend the same naira. Call inside transaction.atomic()."""
    ensure_user_accounts(user)
    return LedgerAccount.objects.select_for_update().get(code=wallet_code(user.pk))


def credit_inflow(inflow: Inflow, source: str = LIBERTY_POOL) -> bool:
    """Credit a verified inflow to its user's wallet, exactly once. Returns True if this call credited it."""
    if inflow.user_id is None:
        raise LedgerError("inflow has no user")
    ensure_user_accounts(inflow.user)
    account(source)
    with transaction.atomic():
        locked = Inflow.objects.select_for_update().get(pk=inflow.pk)
        if locked.status == Inflow.Status.CREDITED:
            return False
        _, created = post(
            f"inflow:{locked.provider}:{locked.reference}", "top_up",
            [(wallet_code(locked.user_id), locked.amount_kobo), (source, -locked.amount_kobo)],
            memo=f"Top-up from {locked.sender_name or locked.provider}",
        )
        locked.status = Inflow.Status.CREDITED
        locked.credited_at = timezone.now()
        locked.save(update_fields=["status", "credited_at"])
        inflow.refresh_from_db()
        return created


def reserve(user, run) -> bool:
    """
    Move a run's cost from the wallet into held. Must be called inside transaction.atomic()
    after lock_wallet(user). Raises InsufficientFunds. Returns False if already reserved.
    """
    cost = run.cost_kobo
    available = account_balance(wallet_code(user.pk))
    key = f"reserve:{run.pk}"
    if LedgerTransaction.objects.filter(idempotency_key=key).exists():
        return False
    if available < cost:
        raise InsufficientFunds(available, cost)
    _, created = post(key, "reserve", [(wallet_code(user.pk), -cost), (held_code(user.pk), cost)], run=run,
                      memo=f"Set aside for {run.plan.label}")
    return created


def settle(user, run) -> bool:
    """The transfer went out: held money leaves the pool and each fee goes to its own fee account,
    with one Fees-table row per fee pointing back at this run and this posting."""
    if not LedgerTransaction.objects.filter(idempotency_key=f"reserve:{run.pk}").exists():
        raise LedgerError(f"run {run.pk} was never reserved")
    if LedgerTransaction.objects.filter(idempotency_key=f"release:{run.pk}").exists():
        raise LedgerError(f"run {run.pk} was already released")
    pool = PAYSTACK if run.provider == "paystack" else LIBERTY_POOL
    account(pool)
    parts = run.fee_parts
    fees = [("service", parts.service_kobo), ("provider", parts.provider_kobo), ("stamp_duty", parts.stamp_duty_kobo)]
    lines = [(held_code(user.pk), -run.cost_kobo), (pool, run.amount_kobo)]
    for kind, amount in fees:
        if amount:
            lines.append((account(FEE_ACCOUNTS[kind][0]).code, amount))
    with transaction.atomic():
        txn, created = post(f"settle:{run.pk}", "settle", lines, run=run, memo=f"{run.plan.label} sent")
        for kind, amount in fees:
            if amount:
                code, paid_to = FEE_ACCOUNTS[kind]
                FeeLine.objects.get_or_create(run=run, kind=kind, defaults={
                    "paid_to": paid_to, "amount_kobo": amount, "user": user, "ledger_transaction": txn, "account_code": code,
                    "provider": run.provider, "reference": run.provider_ref or str(run.pk)})
    return created


def record_card_fee(charge, txn=None) -> None:
    """The card fee Paystack kept on a top-up. Paid by the cardholder on top of their top-up, so it never
    touches a SpenDrip account; it's recorded so every fee is visible in one table."""
    if charge.fee_kobo:
        FeeLine.objects.get_or_create(card_charge=charge, kind=FeeLine.Kind.CARD, defaults={
            "paid_to": FeeLine.PaidTo.PROVIDER, "amount_kobo": charge.fee_kobo, "user": charge.user,
            "ledger_transaction": txn, "provider": "paystack", "reference": charge.reference})


def release(user, run) -> bool:
    """The transfer definitely failed: give the held money back."""
    if not LedgerTransaction.objects.filter(idempotency_key=f"reserve:{run.pk}").exists():
        return False
    if LedgerTransaction.objects.filter(idempotency_key=f"settle:{run.pk}").exists():
        raise LedgerError(f"run {run.pk} was already settled")
    _, created = post(f"release:{run.pk}", "release", [(held_code(user.pk), -run.cost_kobo), (wallet_code(user.pk), run.cost_kobo)],
                      run=run, memo=f"{run.plan.label} returned")
    return created


def unreconciled_accounts() -> list[str]:
    """Accounts whose running balance doesn't match the sum of their entries. Should always be empty."""
    sums = dict(LedgerEntry.objects.values_list("account__code").annotate(s=Sum("amount_kobo")))
    return [a.code for a in LedgerAccount.objects.all() if a.balance_kobo != int(sums.get(a.code) or 0)]


def trial_balance() -> int:
    """Sum of every entry in the ledger. Always 0 if the books are consistent."""
    return int(LedgerEntry.objects.aggregate(s=Sum("amount_kobo"))["s"] or 0)
