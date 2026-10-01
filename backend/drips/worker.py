"""
The payout worker. Each tick:
  1. creates upcoming runs from plans,
  2. handles runs that are due: protection check → set money aside → send,
  3. checks transfers in flight with the provider (TSQ) → settle or release.

Rules that keep money safe:
  - A run's id is the provider request reference, and runs are unique per (plan, time).
  - Money is set aside (reserved) under a row lock before any transfer call.
  - If a transfer call fails mid-way we never resend. We ask the provider first.
  - Money is released only when the provider says the transfer definitely failed.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from engine import compare_key, decide
from ledger import services as ledger
from notifications.models import OutboxMessage
from notifications.services import notify
from providers import ProviderError, TransferRequest, TransferStatus, get_messenger, get_payment_provider
from providers import messages as copy

from .models import Plan, Run
from .services import engine_plans, materialise_runs, sent_today_kobo

log = logging.getLogger("spendrip.worker")
ADVISORY_LOCK_KEY = 0x5D_D21F  # one worker at a time
SKIP_STATUS = {
    "protected_for_priorities": Run.Status.SKIPPED_PROTECTED,
    "insufficient_funds": Run.Status.SKIPPED_INSUFFICIENT,
    "daily_cap": Run.Status.SKIPPED_CAP,
}
NOT_FOUND_GIVE_UP_AFTER = 3


class Worker:
    def __init__(self, provider=None, messenger=None):
        self.provider = provider or get_payment_provider()
        self.messenger = messenger or get_messenger()
        self.cfg = settings.SPENDRIP

    # ------------------------------------------------------------------ tick
    def tick(self, now: datetime | None = None) -> dict:
        now = now or timezone.now()
        with connection.cursor() as c:
            c.execute("SELECT pg_try_advisory_lock(%s)", [ADVISORY_LOCK_KEY])
            if not c.fetchone()[0]:
                log.info("another worker holds the lock; skipping tick")
                return {"skipped": True}
        try:
            created = materialise_runs(now)
            handled = self.process_due(now)
            checked = self.check_in_flight(now)
            return {"created": created, "handled": handled, "checked": checked}
        finally:
            with connection.cursor() as c:
                c.execute("SELECT pg_advisory_unlock(%s)", [ADVISORY_LOCK_KEY])

    # ------------------------------------------------------------- due runs
    def process_due(self, now: datetime) -> int:
        due = list(Run.objects.filter(status=Run.Status.SCHEDULED, scheduled_for__lte=now)
                   .select_related("plan", "plan__recipient", "user"))
        by_user = defaultdict(list)
        for run in due:
            by_user[run.user_id].append(run)
        for runs in by_user.values():
            runs.sort(key=lambda r: compare_key(r.scheduled_for, r.plan.priority_rank, r.plan.pk))
            for run in runs:
                self._handle_due(run, now)
        return len(due)

    def _handle_due(self, run: Run, now: datetime) -> None:
        plan, user = run.plan, run.user
        if plan.status != Plan.Status.ACTIVE or user.paused_all:
            self._set(run, Run.Status.SKIPPED_PAUSED)
            return
        if now - run.scheduled_for > timedelta(hours=self.cfg["LATE_SEND_WINDOW_HOURS"]):
            self._set(run, Run.Status.MISSED)
            self._tell_self(run, "missed", copy.self_missed(emoji=plan.emoji, label=plan.label, amount_kobo=run.amount_kobo))
            return

        with transaction.atomic():
            ledger.lock_wallet(user)
            available = ledger.balance(user).available_kobo
            d = decide(
                plan_id=str(plan.pk), at=run.scheduled_for, amount_kobo=run.amount_kobo, plans=engine_plans(user),
                available_kobo=available, sent_today_kobo=sent_today_kobo(user, run.scheduled_for),
                fee_kobo=run.fee_kobo, tz=user.tz, daily_cap_kobo=user.daily_cap_kobo,
            )
            if not d.ok:
                self._set(run, SKIP_STATUS[d.reason], last_error=d.reason)
                skipped = (run, d)
            else:
                ledger.reserve(user, run)
                self._set(run, Run.Status.RESERVED, provider=self.provider.name)
                skipped = None
        if skipped:
            self._tell_self(run, "skipped", copy.self_skipped(emoji=plan.emoji, label=plan.label, amount_kobo=run.amount_kobo,
                                                              reason=d.reason, short_by_kobo=d.short_by_kobo))
            return
        self._send(run, now)

    def _send(self, run: Run, now: datetime) -> None:
        r = run.plan.recipient
        req = TransferRequest(reference=str(run.pk), amount_kobo=run.amount_kobo, bank_code=r.nip_bank_code,
                              account_number=r.account_number, account_name=r.verified_account_name,
                              narration=f"SpenDrip {run.plan.label}")
        try:
            result = self.provider.transfer(req)
        except ProviderError as e:
            log.warning("transfer %s outcome unknown: %s", run.pk, e)
            self._set(run, Run.Status.UNKNOWN, last_error=str(e)[:500], sent_at=now, next_check_at=now + self._backoff(0))
            return
        self._apply(run, result, now, first=True)

    # ----------------------------------------------------------- in flight
    def check_in_flight(self, now: datetime) -> int:
        stuck_reserved = now - timedelta(minutes=2)
        runs = list(
            Run.objects.filter(status__in=[Run.Status.PENDING, Run.Status.UNKNOWN], next_check_at__lte=now)
            .select_related("plan", "plan__recipient", "user")
        ) + list(
            # Reserved but the worker died before the transfer call returned: treat as unknown.
            Run.objects.filter(status=Run.Status.RESERVED, updated_at__lte=stuck_reserved).select_related("plan", "plan__recipient", "user")
        )
        for run in runs:
            try:
                result = self.provider.query_transfer(str(run.pk))
            except ProviderError as e:
                run.attempts += 1
                self._set(run, run.status, attempts=run.attempts, last_error=str(e)[:500], next_check_at=now + self._backoff(run.attempts))
                continue
            self._apply(run, result, now, first=False)
        return len(runs)

    def _apply(self, run: Run, result, now: datetime, *, first: bool) -> None:
        if result.status == TransferStatus.SUCCESSFUL:
            self._complete(run, result, now)
        elif result.status == TransferStatus.FAILED:
            self._fail(run, result.message or "provider reported failure", now)
        elif result.status == TransferStatus.NOT_FOUND and not first:
            run.attempts += 1
            if run.attempts >= NOT_FOUND_GIVE_UP_AFTER:
                self._fail(run, "the transfer never reached the provider", now)
            else:
                self._set(run, Run.Status.UNKNOWN, attempts=run.attempts, next_check_at=now + self._backoff(run.attempts))
        else:  # pending
            attempts = 0 if first else run.attempts + 1
            review = attempts >= len(self.cfg["TSQ_BACKOFF_SECONDS"])
            self._set(run, Run.Status.PENDING, attempts=attempts, provider_ref=result.provider_ref or run.provider_ref,
                      sent_at=run.sent_at or now, next_check_at=now + self._backoff(attempts), needs_review=review)
            if review:
                self._tell_self(run, "slow", f"{run.plan.emoji} {run.plan.label} is taking longer than usual. We're still checking with the bank.")

    def _complete(self, run: Run, result, now: datetime) -> None:
        with transaction.atomic():
            ledger.settle(run.user, run)
            self._set(run, Run.Status.SUCCESSFUL, completed_at=now, provider_session_id=result.session_id or run.provider_session_id,
                      provider_ref=result.provider_ref or run.provider_ref, next_check_at=None, needs_review=False)
        plan, r, user = run.plan, run.plan.recipient, run.user
        self._tell_self(run, "paid", copy.self_paid(emoji=plan.emoji, label=plan.label, amount_kobo=run.amount_kobo,
                                                    recipient_label=r.label, bank=r.bank_name, last4=r.account_number[-4:]))
        if not r.is_self and r.notify_whatsapp and r.whatsapp:
            notify(user, key=f"run:{run.pk}:wa", channel=OutboxMessage.Channel.WHATSAPP, template="recipient_paid", to=r.whatsapp, run=run,
                   messenger=self.messenger,
                   body=copy.recipient_paid(recipient_label=r.label, amount_kobo=run.amount_kobo, bank=r.bank_name,
                                            last4=r.account_number[-4:], sender_first_name=user.first_name.title() or "a friend"))

    def _fail(self, run: Run, reason: str, now: datetime) -> None:
        with transaction.atomic():
            ledger.release(run.user, run)
            self._set(run, Run.Status.FAILED, last_error=reason[:500], completed_at=now, next_check_at=None)
        self._tell_self(run, "failed", copy.self_failed(emoji=run.plan.emoji, label=run.plan.label, amount_kobo=run.amount_kobo))

    # --------------------------------------------------------------- helpers
    def _backoff(self, attempt: int) -> timedelta:
        steps = self.cfg["TSQ_BACKOFF_SECONDS"]
        return timedelta(seconds=steps[min(attempt, len(steps) - 1)])

    def _set(self, run: Run, status: str, **fields) -> None:
        run.status = status
        for k, v in fields.items():
            setattr(run, k, v)
        run.save(update_fields=["status", "updated_at", *fields.keys()])

    def _tell_self(self, run: Run, kind: str, body: str) -> None:
        for channel in (OutboxMessage.Channel.IN_APP, OutboxMessage.Channel.PUSH):
            notify(run.user, key=f"run:{run.pk}:{kind}:{channel}", channel=channel, template=f"self_{kind}", body=body, run=run,
                   messenger=self.messenger)
