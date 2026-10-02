from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = ("Delete ALL app data (users except staff, plans, drips, ledger, cards, messages, KYC records, sessions) "
            "to start live mode clean. Keeps staff/admin logins and the waitlist. Needs --yes-delete-everything.")

    def add_arguments(self, parser):
        parser.add_argument("--yes-delete-everything", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opts):
        if not opts["yes_delete_everything"]:
            raise CommandError("Refusing to run without --yes-delete-everything.")
        from accounts.models import KycCheck, OneTimeCode, User, WebAuthnCredential
        from drips.models import Plan, Recipient, Run
        from ledger.models import CardCharge, FeeLine, FundingAccount, Inflow, LedgerAccount, LedgerEntry, LedgerTransaction, SavedCard
        from notifications.models import OutboxMessage
        from providers.models import MockTransfer, ResolvedAccount
        order = [FeeLine, LedgerEntry, LedgerTransaction, OutboxMessage, CardCharge, SavedCard, Inflow, Run, Plan, Recipient,
                 FundingAccount, LedgerAccount, MockTransfer, ResolvedAccount, KycCheck, OneTimeCode, WebAuthnCredential, Session]
        for model in order:
            n, _ = model.objects.all().delete()
            self.stdout.write(f"{model.__name__}: {n} deleted")
        n, _ = User.objects.filter(is_staff=False, is_superuser=False).delete()
        self.stdout.write(f"User (non-staff): {n} deleted")
        self.stdout.write(self.style.SUCCESS("Done. Staff logins and the waitlist were kept."))
