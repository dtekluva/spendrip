from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from drips.models import Plan, Recipient
from drips.services import materialise_runs
from engine import naira
from ledger import services as ledger
from ledger.models import FundingAccount, Inflow
from providers import get_payment_provider


class Command(BaseCommand):
    help = "Create a demo user with the plans from the mock (Upkeep, Mum, Fuel, Cousin) and a ₦250,000 balance."

    @transaction.atomic
    def handle(self, *args, **opts):
        user, created = User.objects.get_or_create(
            username="demo",
            defaults={"first_name": "ADAEZE", "last_name": "OKONKWO", "phone": "08031234417", "email": "demo@spendrip.local",
                      "kyc_status": User.Kyc.VERIFIED, "nin_last4": "8901", "is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password("demo")  # dev only: lets you into /admin as demo/demo
            user.set_pin("2580")
            user.save()
        ledger.ensure_user_accounts(user)

        provider = get_payment_provider()
        if not user.funding_accounts.exists():
            va = provider.create_virtual_account(first_name=user.first_name, last_name=user.last_name, email=user.email)
            FundingAccount.objects.create(user=user, provider=provider.name, account_number=va.account_number,
                                          bank_name=va.bank_name, bank_code=va.bank_code, account_name=va.account_name)

        def recipient(label, bank, code, number, whatsapp="", is_self=False):
            name = provider.name_enquiry(code, number).account_name
            r, _ = Recipient.objects.get_or_create(
                user=user, nip_bank_code=code, account_number=number,
                defaults={"label": label, "bank_name": bank, "verified_account_name": name, "whatsapp": whatsapp,
                          "is_self": is_self, "verified_at": timezone.now()},
            )
            return r

        me = recipient("Me", "GTBank", "000013", "0244132018", is_self=True)
        mum = recipient("Mum", "OPay", "100004", "9028906357", whatsapp="+2348030004417")
        cousin = recipient("Cousin", "Access Bank", "000014", "0123454410", whatsapp="+2348160002517")

        start = datetime(2026, 1, 1, tzinfo=ZoneInfo("Africa/Lagos"))
        plans = [
            dict(label="Upkeep", emoji="🍲", tint="sun", amount_kobo=naira(5_000), recipient=me, frequency="daily", time_local="06:00", priority_rank=1),
            dict(label="Mum", emoji="💛", tint="hibiscus", amount_kobo=naira(30_000), recipient=mum, frequency="monthly", month_day=30, time_local="10:00", priority_rank=2),
            dict(label="Fuel", emoji="⛽", tint="cobalt", amount_kobo=naira(40_000), recipient=me, frequency="weekly", weekday=5, time_local="14:00"),
            dict(label="Cousin", emoji="🤝", tint="mint", amount_kobo=naira(25_000), recipient=cousin, frequency="monthly", month_day=30, time_local="12:00"),
        ]
        for p in plans:
            Plan.objects.get_or_create(user=user, label=p["label"], defaults={**p, "starts_at": start})

        inflow, _ = Inflow.objects.get_or_create(
            provider="mock", reference="seed-demo-topup",
            defaults={"user": user, "amount_kobo": naira(250_000), "sender_name": "DEMO SEED", "raw": {"seed": True}},
        )
        ledger.credit_inflow(inflow)
        materialise_runs(timezone.now())
        bal = ledger.balance(user)
        self.stdout.write(self.style.SUCCESS(
            f"Demo user ready: username=demo password=demo PIN=2580 · balance ₦{bal.available_kobo // 100:,} · "
            f"account {user.funding_accounts.first().account_number}"))
