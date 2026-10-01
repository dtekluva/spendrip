from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

MAX_PIN_ATTEMPTS = 5
WEAK_PINS = {"0000", "1111", "1234", "4321", "1212", "2222", "9999"}


class User(AbstractUser):
    class Kyc(models.TextChoices):
        NOT_STARTED = "not_started"
        NIN_VERIFIED = "nin_verified"
        DOC_UPLOADED = "doc_uploaded"
        VERIFIED = "verified"
        REJECTED = "rejected"
        NEEDS_REVIEW = "needs_review"

    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    kyc_status = models.CharField(max_length=20, choices=Kyc.choices, default=Kyc.NOT_STARTED)
    # The full NIN is never stored in plain text. We keep the last 4 digits for display and a
    # keyed hash for matching; the provider holds the record. Field-level encryption comes with
    # the real KYC provider (see docs/PLAN.md §6b).
    nin_last4 = models.CharField(max_length=4, blank=True)
    nin_hash = models.CharField(max_length=128, blank=True)

    pin_hash = models.CharField(max_length=256, blank=True)
    failed_pin_attempts = models.PositiveSmallIntegerField(default=0)
    locked_at = models.DateTimeField(null=True, blank=True)

    tz = models.CharField(max_length=64, default="Africa/Lagos")
    daily_cap_kobo = models.BigIntegerField(null=True, blank=True)
    paused_all = models.BooleanField(default=False)
    look = models.CharField(max_length=10, default="themed")  # themed | light | dark

    @property
    def is_verified(self) -> bool:
        return self.kyc_status == self.Kyc.VERIFIED

    def set_pin(self, pin: str) -> None:
        if not (len(pin) == 4 and pin.isdigit()):
            raise ValueError("PIN must be 4 digits")
        if pin in WEAK_PINS:
            raise ValueError("That PIN is too easy to guess")
        self.pin_hash = make_password(pin)
        self.failed_pin_attempts = 0
        self.locked_at = None

    def check_pin(self, pin: str) -> bool:
        """Checks the PIN and counts failures. After 5 wrong tries the account locks until reset by OTP."""
        if self.locked_at or not self.pin_hash:
            return False
        if check_password(pin, self.pin_hash):
            self.failed_pin_attempts = 0
            self.save(update_fields=["failed_pin_attempts"])
            return True
        self.failed_pin_attempts += 1
        if self.failed_pin_attempts >= MAX_PIN_ATTEMPTS:
            self.locked_at = timezone.now()
        self.save(update_fields=["failed_pin_attempts", "locked_at"])
        return False


class KycCheck(models.Model):
    """One row per verification step, with the provider's raw answer kept for audit."""

    class Step(models.TextChoices):
        NIN = "nin"
        DOCUMENT = "document"
        SELFIE = "selfie"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="kyc_checks")
    step = models.CharField(max_length=10, choices=Step.choices)
    passed = models.BooleanField()
    provider = models.CharField(max_length=30)
    provider_ref = models.CharField(max_length=120, blank=True)
    raw = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
