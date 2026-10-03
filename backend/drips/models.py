import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from engine import PlanLike, Schedule


class Recipient(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipients")
    label = models.CharField(max_length=60)  # what the user calls them: "Mum", "Me"
    is_self = models.BooleanField(default=False)
    bank_name = models.CharField(max_length=80)
    nip_bank_code = models.CharField(max_length=10)  # Liberty/NIP code, e.g. 000013 GTBank
    cbn_bank_code = models.CharField(max_length=10, blank=True)  # Paystack uses CBN codes
    paystack_recipient_code = models.CharField(max_length=40, blank=True)  # registered once, reused for every payout
    account_number = models.CharField(max_length=10)
    verified_account_name = models.CharField(max_length=120)  # from name enquiry
    whatsapp = models.CharField(max_length=20, blank=True)
    notify_whatsapp = models.BooleanField(default=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "nip_bank_code", "account_number"], name="recipient_unique_account")]

    def __str__(self):
        return f"{self.label} ({self.bank_name} ••{self.account_number[-4:]})"


class Plan(models.Model):
    class Kind(models.TextChoices):
        SINGLE = "single"  # one person
        GROUP = "group"  # several people, each with their own amount, paid together (PlanLine)

    class Frequency(models.TextChoices):
        DAILY = "daily"
        WEEKLY = "weekly"
        MONTHLY = "monthly"

    class Status(models.TextChoices):
        ACTIVE = "active"
        PAUSED = "paused"
        FINISHED = "finished"  # reached its end date and its last drip is done
        DELETED = "deleted"

    class EndMode(models.TextChoices):
        ONGOING = "ongoing"  # keeps going
        MONTHS = "months"  # for `duration_months` months from the start
        DATE = "date"  # until `ends_at`'s date, inclusive

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="plans")
    label = models.CharField(max_length=40)
    emoji = models.CharField(max_length=8, default="💸")
    tint = models.CharField(max_length=12, default="cobalt")
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.SINGLE)
    amount_kobo = models.BigIntegerField()  # group plans: the sum of their active lines, kept in step by save_lines()
    recipient = models.ForeignKey(Recipient, on_delete=models.PROTECT, related_name="plans", null=True, blank=True)  # empty for groups
    frequency = models.CharField(max_length=10, choices=Frequency.choices)
    weekday = models.PositiveSmallIntegerField(null=True, blank=True)  # ISO 1 = Monday … 7 = Sunday
    month_day = models.PositiveSmallIntegerField(null=True, blank=True)  # 1–31
    month_day_last = models.BooleanField(default=False)  # "last day of the month"
    time_local = models.CharField(max_length=5)  # HH:MM
    tz = models.CharField(max_length=64, default="Africa/Lagos")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)  # last moment a drip may fall (computed from end_mode)
    end_mode = models.CharField(max_length=8, choices=EndMode.choices, default=EndMode.ONGOING)
    duration_months = models.PositiveSmallIntegerField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    priority_rank = models.PositiveSmallIntegerField(null=True, blank=True)  # 1–3
    provider = models.CharField(max_length=20, default="liberty")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "priority_rank"], condition=Q(priority_rank__isnull=False), name="plan_unique_priority_per_user"),
            models.CheckConstraint(condition=Q(priority_rank__isnull=True) | Q(priority_rank__gte=1, priority_rank__lte=3), name="plan_priority_1_to_3"),
            models.CheckConstraint(condition=Q(amount_kobo__gt=0), name="plan_amount_positive"),
        ]

    def __str__(self):
        return f"{self.emoji} {self.label}"

    @property
    def schedule(self) -> Schedule:
        return Schedule(
            frequency=self.frequency, time_local=self.time_local, tz=self.tz, starts_at=self.starts_at,
            weekday=self.weekday, month_day="last" if self.month_day_last else self.month_day, ends_at=self.ends_at,
        )

    @property
    def is_group(self) -> bool:
        return self.kind == self.Kind.GROUP

    def active_lines(self) -> list["PlanLine"]:
        return [ln for ln in self.lines.all() if ln.active]

    def to_engine(self) -> PlanLike:
        line_amounts = next_amounts = None
        if self.is_group:
            lines = self.active_lines()
            line_amounts = tuple(ln.amount_kobo for ln in lines)
            if any(ln.skip_next or ln.next_amount_kobo is not None for ln in lines):
                next_amounts = tuple(ln.next_amount for ln in lines if not ln.skip_next)
        return PlanLike(
            id=str(self.pk), amount_kobo=self.amount_kobo, schedule=self.schedule, priority_rank=self.priority_rank,
            status="active" if self.status == self.Status.ACTIVE else "paused", order=self.pk,
            line_amounts=line_amounts, next_line_amounts=next_amounts,
        )


class PlanLine(models.Model):
    """One person on a group plan, with their own amount. Removed people stay (inactive) so past payouts keep their history."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="lines")
    recipient = models.ForeignKey(Recipient, on_delete=models.PROTECT, related_name="plan_lines")
    amount_kobo = models.BigIntegerField()  # every payout
    next_amount_kobo = models.BigIntegerField(null=True, blank=True)  # the next payout only (bonus or deduction)
    skip_next = models.BooleanField(default=False)  # left out of the next payout only
    position = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "recipient"], condition=Q(active=True), name="planline_one_per_person"),
            models.CheckConstraint(condition=Q(amount_kobo__gt=0), name="planline_amount_positive"),
        ]

    @property
    def next_amount(self) -> int:
        return self.next_amount_kobo if self.next_amount_kobo is not None else self.amount_kobo

    def __str__(self):
        return f"{self.recipient.label}: {self.amount_kobo / 100:,.0f}"


class RunBatch(models.Model):
    """One payout of a group plan: all of its transfers are decided together, so either everyone is paid or nobody is."""

    class Status(models.TextChoices):
        SCHEDULED = "scheduled"
        WAITING = "waiting"  # due, but the balance (or a limit) can't cover everyone yet; retried until the late window ends
        SENDING = "sending"  # money set aside, transfers going out
        DONE = "done"  # every transfer has a final answer
        SKIPPED = "skipped"  # never sent (no money in time, paused, missed)
        CANCELLED = "cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="batches")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="run_batches")
    scheduled_for = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCHEDULED)
    amount_kobo = models.BigIntegerField(default=0)
    fee_kobo = models.BigIntegerField(default=0)
    reason = models.CharField(max_length=40, blank=True)  # why it's waiting or was skipped
    short_by_kobo = models.BigIntegerField(default=0)
    # "Send again" after a failed or skipped payout: a fresh batch for the people who weren't paid, pointing back here.
    retry_of = models.OneToOneField("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="retry")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["plan", "scheduled_for"], name="batch_unique_per_plan_time")]
        indexes = [models.Index(fields=["status", "scheduled_for"])]

    @property
    def cost_kobo(self) -> int:
        return self.amount_kobo + self.fee_kobo


class Run(models.Model):
    """One occurrence of a plan. Its id is the request reference sent to the provider, so a run can never be paid twice."""

    class Status(models.TextChoices):
        SCHEDULED = "scheduled"
        RESERVED = "reserved"  # money set aside, transfer not yet confirmed as sent
        PENDING = "pending"  # provider accepted it, waiting for the final result
        UNKNOWN = "unknown"  # the transfer call failed mid-way; must check status before anything else
        SUCCESSFUL = "successful"
        FAILED = "failed"
        SKIPPED_PROTECTED = "skipped_protected"
        SKIPPED_INSUFFICIENT = "skipped_insufficient"
        SKIPPED_CAP = "skipped_cap"
        SKIPPED_PAUSED = "skipped_paused"
        MISSED = "missed"
        CANCELLED = "cancelled"

    IN_FLIGHT = (Status.RESERVED, Status.PENDING, Status.UNKNOWN)
    COUNTS_TOWARDS_CAP = (Status.RESERVED, Status.PENDING, Status.UNKNOWN, Status.SUCCESSFUL)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="runs")
    line = models.ForeignKey("PlanLine", on_delete=models.PROTECT, related_name="runs", null=True, blank=True)  # group plans
    batch = models.ForeignKey("RunBatch", on_delete=models.CASCADE, related_name="runs", null=True, blank=True)  # group plans
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="runs")
    scheduled_for = models.DateTimeField()
    amount_kobo = models.BigIntegerField()
    fee_kobo = models.BigIntegerField()  # total of the three parts below
    service_fee_kobo = models.BigIntegerField(default=0)  # SpenDrip's fee
    provider_fee_kobo = models.BigIntegerField(default=0)  # payout provider's transfer charge, passed through
    stamp_duty_kobo = models.BigIntegerField(default=0)  # government stamp duty, passed through
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.SCHEDULED)
    attempts = models.PositiveSmallIntegerField(default=0)  # status checks made
    provider = models.CharField(max_length=20, blank=True)
    provider_ref = models.CharField(max_length=120, blank=True)
    provider_session_id = models.CharField(max_length=120, blank=True)
    last_error = models.TextField(blank=True)
    needs_review = models.BooleanField(default=False)
    next_check_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plan", "scheduled_for"], condition=Q(line__isnull=True), name="run_unique_per_plan_time"),
            models.UniqueConstraint(fields=["line", "scheduled_for"], condition=Q(line__isnull=False), name="run_unique_per_line_time"),
        ]
        indexes = [models.Index(fields=["status", "scheduled_for"]), models.Index(fields=["status", "next_check_at"])]

    @property
    def fee_parts(self):
        from engine import FeeParts
        if self.service_fee_kobo + self.provider_fee_kobo + self.stamp_duty_kobo != self.fee_kobo:
            return FeeParts(service_kobo=self.fee_kobo)  # runs from before fees were itemised
        return FeeParts(self.service_fee_kobo, self.provider_fee_kobo, self.stamp_duty_kobo)

    @property
    def cost_kobo(self) -> int:
        return self.amount_kobo + self.fee_kobo

    @property
    def recipient(self) -> Recipient:
        return self.line.recipient if self.line_id else self.plan.recipient

    @property
    def label(self) -> str:
        """For ledger memos: the plan, plus the person on group plans."""
        return f"{self.plan.label} · {self.line.recipient.label}" if self.line_id else self.plan.label
