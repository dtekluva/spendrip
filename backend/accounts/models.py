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

    # Email is how people sign up and sign in. The phone comes from their NIN/BVN record when they verify.
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    kyc_status = models.CharField(max_length=20, choices=Kyc.choices, default=Kyc.NOT_STARTED)
    # The full NIN is never stored in plain text. We keep the last 4 digits for display and a
    # keyed hash for matching; the provider holds the record. Field-level encryption comes with
    # the real KYC provider (see docs/PLAN.md §6b).
    nin_last4 = models.CharField(max_length=4, blank=True)
    nin_hash = models.CharField(max_length=128, blank=True)
    kyc_id_type = models.CharField(max_length=3, default="nin")  # which number nin_* holds: nin | bvn

    pin_hash = models.CharField(max_length=256, blank=True)
    failed_pin_attempts = models.PositiveSmallIntegerField(default=0)
    locked_at = models.DateTimeField(null=True, blank=True)

    tz = models.CharField(max_length=64, default="Africa/Lagos")
    daily_cap_kobo = models.BigIntegerField(null=True, blank=True)
    paused_all = models.BooleanField(default=False)
    look = models.CharField(max_length=10, default="themed")  # themed | light | dark
    notify_push = models.BooleanField(default=True)
    notify_whatsapp_recipients = models.BooleanField(default=True)
    notify_daily_summary = models.BooleanField(default=True)
    notify_low_balance = models.BooleanField(default=True)
    notify_email = models.BooleanField(default=True)  # email me when a drip is delivered

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


class OneTimeCode(models.Model):
    """A one-time code sent to an email address (or a phone). Only a hash is stored."""

    class Purpose(models.TextChoices):
        SIGNUP = "signup"
        SIGNIN = "signin"

    target = models.CharField(max_length=254, db_index=True)  # lower-case email, or a normalised phone
    purpose = models.CharField(max_length=10, choices=Purpose.choices)
    code_hash = models.CharField(max_length=256)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class WebAuthnCredential(models.Model):
    """A passkey (Face ID / fingerprint) registered on one of the user's devices."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="passkeys")
    credential_id = models.CharField(max_length=512, unique=True)  # base64url
    public_key = models.TextField()  # base64url COSE key
    sign_count = models.PositiveBigIntegerField(default=0)
    device_label = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)


class WaitlistEntry(models.Model):
    """Someone who asked to be invited from the landing page."""

    contact = models.CharField(max_length=120, unique=True)  # normalised phone (080…) or lower-case email
    kind = models.CharField(max_length=5)  # phone | email
    name = models.CharField(max_length=80, blank=True)
    source = models.CharField(max_length=40, blank=True)  # e.g. "landing"
    invited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "waitlist"

    def __str__(self):
        return f"{self.name or self.contact} ({self.kind})"
