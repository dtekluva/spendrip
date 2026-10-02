"""Sign-up (email → code → name → PIN → Face ID), identity checks later in the app (ID photo → three face angles),
sign-in, unlock and passkeys."""
import secrets

from django.conf import settings
from django.contrib.auth import login, logout
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import KycCheck, User, WebAuthnCredential
from accounts import services as acc
from accounts.services import FlowError
from ledger import services as ledger
from providers import get_kyc_provider
from providers.base import ProviderError

from .permissions import SignedIn, Unlocked

SIGNUP = "signup"  # session key holding the in-progress sign-up
BACKEND = "django.contrib.auth.backends.ModelBackend"


def dev_code(code: str) -> dict:
    """Only dev builds get the code back in the response, so the flow can be tried without an inbox."""
    return {"dev_code": code} if settings.SPENDRIP["DEV_TOOLS"] else {}


def me_json(request) -> dict:
    u = request.user
    dev = settings.SPENDRIP["DEV_TOOLS"]
    if not u.is_authenticated:
        s = request.session.get(SIGNUP) or {}
        return {"signed_in": False, "dev_tools": dev,
                "signup": {"step": s.get("step"), "email_masked": s.get("email_masked")} if s else None}
    fa = u.funding_accounts.first()
    return {
        "signed_in": True,
        "dev_tools": dev,
        "locked": not acc.is_unlocked(request),
        "user": {
            "first_name": u.first_name.title(), "last_name": u.last_name.title(), "email": u.email or "",
            "email_masked": acc.mask_email(u.email or ""), "phone_masked": acc.mask_phone(u.phone or ""),
            "kyc_status": u.kyc_status, "kyc_id_type": u.kyc_id_type, "kyc_message": u.kyc_message, "kyc_tier": u.kyc_tier,
            "kyc_mode": acc.kyc_mode(), "limits": acc.limits(u),
            "bank_transfer_funding": settings.SPENDRIP.get("BANK_TRANSFER_FUNDING", True), "nin_last4": u.nin_last4, "has_name": bool(u.first_name), "has_pin": bool(u.pin_hash), "pin_locked": bool(u.locked_at),
            "has_face_id": u.passkeys.exists(), "look": u.look, "daily_cap_kobo": u.daily_cap_kobo, "paused_all": u.paused_all,
            "notify_push": u.notify_push, "notify_whatsapp_recipients": u.notify_whatsapp_recipients,
            "notify_daily_summary": u.notify_daily_summary, "notify_low_balance": u.notify_low_balance, "notify_email": u.notify_email,
            "funding_account": {"account_number": fa.account_number, "bank_name": fa.bank_name, "account_name": fa.account_name} if fa else None,
        },
    }


@method_decorator(ensure_csrf_cookie, name="get")
class Me(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(me_json(request))


class MeUpdate(APIView):
    """Profile settings. Needs the app unlocked."""

    FIELDS = {"look": {"themed", "light", "dark"}, "paused_all": bool, "daily_cap_kobo": "cap",
              "notify_push": bool, "notify_whatsapp_recipients": bool, "notify_daily_summary": bool, "notify_low_balance": bool, "notify_email": bool}

    def patch(self, request):
        u = request.user
        changed = []
        for k, v in request.data.items():
            rule = self.FIELDS.get(k)
            if rule is None:
                raise FlowError(f"{k} can't be changed here.")
            if rule is bool:
                if not isinstance(v, bool):
                    raise FlowError(f"{k} must be true or false.")
            elif rule == "cap":
                if v is not None and (not isinstance(v, int) or v < 100_000):
                    raise FlowError("The daily limit must be at least ₦1,000, or off.")
            elif v not in rule:
                raise FlowError(f"{k} must be one of {', '.join(sorted(rule))}.")
            setattr(u, k, v)
            changed.append(k)
        u.save(update_fields=changed)
        return Response(me_json(request))


# ------------------------------------------------------------------ sign-up: email → code → (signed in) name → PIN → Face ID

def signup_state(request) -> dict:
    s = request.session.get(SIGNUP)
    if not s:
        raise FlowError("Start again with your email.", code="signup_missing", status=409)
    return s


class SignupStart(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = acc.normalise_email(str(request.data.get("email", "")))
        existing = User.objects.filter(email=email).first()
        if existing and existing.pin_hash:
            raise FlowError("That email already has a SpenDrip account. Sign in instead.", code="already_registered", status=409)
        code = acc.send_otp(email, "signup")
        request.session[SIGNUP] = {"step": "code", "email": email, "email_masked": acc.mask_email(email)}
        return Response({"step": "code", "email_masked": acc.mask_email(email), **dev_code(code)})


class SignupResendOtp(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = signup_state(request)
        code = acc.send_otp(s["email"], "signup")
        return Response({"email_masked": s["email_masked"], **dev_code(code)})


class SignupVerifyOtp(APIView):
    """The email is confirmed: create the account (or pick up an unfinished one) and sign in."""

    permission_classes = [AllowAny]

    def post(self, request):
        s = signup_state(request)
        acc.check_otp(s["email"], "signup", str(request.data.get("code", "")))
        with transaction.atomic():
            user = User.objects.filter(email=s["email"]).first()
            if user and user.pin_hash:
                raise FlowError("That email already has a SpenDrip account. Sign in instead.", code="already_registered", status=409)
            if not user:
                user = User(username=s["email"], email=s["email"], daily_cap_kobo=settings.SPENDRIP.get("DEFAULT_DAILY_CAP_KOBO") or None)
                user.set_unusable_password()
                user.save()
            ledger.ensure_user_accounts(user)
        request.session.pop(SIGNUP, None)
        login(request, user, backend=BACKEND)
        acc.mark_unlocked(request)
        return Response({**me_json(request), "step": "name" if not user.first_name else "pin"})


class SignupName(APIView):
    """What should we call you? (Your legal name comes from your ID when you verify.)"""

    def post(self, request):
        first = " ".join(str(request.data.get("first_name", "")).split())[:60]
        last = " ".join(str(request.data.get("last_name", "")).split())[:60]
        if not first:
            raise FlowError("Add your first name.")
        request.user.first_name, request.user.last_name = first.upper(), last.upper()
        request.user.save(update_fields=["first_name", "last_name"])
        return Response(me_json(request))


# ------------------------------------------------------------------ verify identity (in the app, before money moves):
# a photo of an ID, then three face angles in a shuffled order (liveness)

LIVENESS = "liveness"  # session: the pose order asked for in this attempt
POSES = ("front", "left", "right")
LIVENESS_TTL_SECONDS = 600
ID_TYPE_CODES = {"nin": "nin", "drivers_licence": "dl", "voters_card": "vc", "passport": "pp"}


def kyc_user(request) -> User:
    u = request.user
    if u.is_verified:
        raise FlowError("You're already verified.", code="already_verified", status=409)
    return u


class KycDocument(APIView):
    def post(self, request):
        user = kyc_user(request)
        image = request.FILES.get("image")
        id_type = request.data.get("id_type", "nin")
        if not image:
            raise FlowError("Add a photo of the front of your ID.")
        if image.size > 8 * 1024 * 1024:
            raise FlowError("That photo is too big. Use one under 8 MB.")
        provider = get_kyc_provider()
        try:
            result = provider.check_document(image.read(), id_type=id_type)
        except (ProviderError, ValueError):
            raise FlowError("We couldn't check your ID just now. Use a JPEG or PNG photo, or try again in a minute.", code="check_unavailable", status=503)
        number = "".join(ch for ch in str(result.pop("document_number", "")) if ch.isalnum()).upper()
        KycCheck.objects.create(user=user, step=KycCheck.Step.DOCUMENT, passed=result["passed"], provider=provider.name,
                                raw={"id_type": id_type, **result})
        if not result["passed"]:
            raise FlowError(result.get("message") or "We couldn't read that ID. Lay it flat in good light with all four corners showing.",
                            code="doc_unreadable")
        if number:
            fingerprint = acc.nin_fingerprint(f"doc:{result.get('document_type', '')}:{number}")
            if User.objects.filter(nin_hash=fingerprint).exclude(pk=user.pk).exists():
                raise FlowError("This ID is already linked to another SpenDrip account.", code="id_taken", status=409)
            user.nin_hash, user.nin_last4 = fingerprint, number[-4:]
        given, surname = str(result.get("given_names") or "").strip(), str(result.get("surname") or "").strip()
        if given and surname:  # the ID's name becomes the legal name
            user.first_name, user.last_name = given.split()[0].upper()[:60], surname.upper()[:60]
        user.kyc_id_type = ID_TYPE_CODES.get(result.get("document_type", ""), str(id_type)[:3])
        user.kyc_status, user.kyc_message = User.Kyc.DOC_UPLOADED, ""
        user.save()
        request.session.pop(LIVENESS, None)
        return Response({"step": "liveness", "checks": result.get("checks", [])})


def _doc_done(user: User) -> None:
    if user.kyc_status != User.Kyc.DOC_UPLOADED:
        raise FlowError("Add a photo of your ID first.", code="kyc_missing", status=409)


class KycLivenessStart(APIView):
    """The pose order for this attempt, shuffled so a recording can't simply be replayed."""

    def post(self, request):
        _doc_done(kyc_user(request))
        order = list(POSES)
        secrets.SystemRandom().shuffle(order)
        request.session[LIVENESS] = {"order": order, "at": timezone.now().timestamp()}
        return Response({"order": order})


class KycLiveness(APIView):
    """Three photos, in the order given by /kyc/liveness/start: each must be one clear, live face in the asked pose."""

    def post(self, request):
        user = kyc_user(request)
        _doc_done(user)
        ch = request.session.get(LIVENESS)
        if not ch or timezone.now().timestamp() - ch["at"] > LIVENESS_TTL_SECONDS:
            raise FlowError("Start the face check again.", code="liveness_expired", status=409)
        images = [request.FILES.get(f"image_{i}") for i in range(len(ch["order"]))]
        if not all(images):
            raise FlowError("Take all three photos to continue.")
        if any(img.size > 8 * 1024 * 1024 for img in images):
            raise FlowError("One of the photos is too big. Try again.")
        provider = get_kyc_provider()
        try:
            result = provider.check_liveness([img.read() for img in images], ch["order"])
        except (ProviderError, ValueError):
            raise FlowError("We couldn't check your photos just now. Try again in a minute.", code="check_unavailable", status=503)
        KycCheck.objects.create(user=user, step=KycCheck.Step.SELFIE, passed=result["passed"], provider=provider.name,
                                raw={"order": ch["order"], **result})
        request.session.pop(LIVENESS, None)
        if not result["passed"]:
            raise FlowError(result.get("message") or "That didn't work. Try again in good light, following each step.", code="liveness_failed")
        acc.finish_verification(user)
        return Response(me_json(request))


# ------------------------------------------------------------------ PIN

class SetPin(APIView):
    """First PIN right after sign-up (the session was just unlocked by the email code)."""

    def post(self, request):
        if request.user.pin_hash:
            raise FlowError("You already have a PIN. Change it from Profile.", code="pin_exists", status=409)
        try:
            request.user.set_pin(str(request.data.get("pin", "")))
        except ValueError as e:
            raise FlowError(f"{e}. Pick another.", code="pin_weak")
        request.user.save()
        return Response(me_json(request))


class ChangePin(APIView):
    def post(self, request):
        u = request.user
        if not u.check_pin(str(request.data.get("current", ""))):
            raise FlowError("That's not your current PIN.", code="pin_wrong")
        try:
            u.set_pin(str(request.data.get("new", "")))
        except ValueError as e:
            raise FlowError(f"{e}. Pick another.", code="pin_weak")
        u.save()
        return Response({"ok": True})


class Unlock(APIView):
    permission_classes = [SignedIn]

    def post(self, request):
        u = request.user
        if u.locked_at:
            raise FlowError("Too many wrong PINs. Sign in again with a code sent to your email.", code="pin_locked", status=423)
        if not u.check_pin(str(request.data.get("pin", ""))):
            u.refresh_from_db()
            if u.locked_at:
                raise FlowError("Too many wrong PINs. Sign in again with a code sent to your email.", code="pin_locked", status=423)
            left = 5 - u.failed_pin_attempts
            raise FlowError(f"Wrong PIN. {left} {'try' if left == 1 else 'tries'} left.", code="pin_wrong")
        acc.mark_unlocked(request)
        return Response(me_json(request))


class Lock(APIView):
    permission_classes = [SignedIn]

    def post(self, request):
        acc.lock(request)
        return Response({"locked": True})


# ------------------------------------------------------------------ sign-in on a new device / forgot PIN

def signin_user(email: str) -> User:
    user = User.objects.filter(email=email).exclude(pin_hash="").first()
    if not user:
        raise FlowError("We don't have a SpenDrip account for that email. Create one instead.", code="no_account", status=404)
    return user


class SigninStart(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = acc.normalise_email(str(request.data.get("email", "")))
        user = signin_user(email)
        code = acc.send_otp(email, "signin", user=user)
        return Response({"email_masked": acc.mask_email(email), "pin_locked": bool(user.locked_at), **dev_code(code)})


class SigninVerify(APIView):
    """Email code plus PIN. If the PIN is locked or forgotten, the code plus a new PIN resets it."""

    permission_classes = [AllowAny]

    def post(self, request):
        email = acc.normalise_email(str(request.data.get("email", "")))
        user = signin_user(email)
        acc.check_otp(email, "signin", str(request.data.get("code", "")))
        new_pin = request.data.get("new_pin")
        if new_pin:
            try:
                user.set_pin(str(new_pin))
            except ValueError as e:
                raise FlowError(f"{e}. Pick another.", code="pin_weak")
            user.save()
        elif not user.check_pin(str(request.data.get("pin", ""))):
            raise FlowError("Wrong PIN. If you've forgotten it, choose “Forgot PIN”.", code="pin_wrong")
        login(request, user, backend=BACKEND)
        acc.mark_unlocked(request)
        return Response(me_json(request))


class Signout(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response({"signed_in": False})


# ------------------------------------------------------------------ Face ID (WebAuthn passkeys)

from webauthn import (  # noqa: E402
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url  # noqa: E402
from webauthn.helpers.structs import (  # noqa: E402
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

WA = settings.WEBAUTHN


class PasskeyRegisterOptions(APIView):
    def post(self, request):
        u = request.user
        opts = generate_registration_options(
            rp_id=WA["RP_ID"], rp_name=WA["RP_NAME"], user_id=str(u.pk).encode(), user_name=u.email or u.username,
            user_display_name=u.get_full_name().title() or "SpenDrip user",
            exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id)) for c in u.passkeys.all()],
            authenticator_selection=AuthenticatorSelectionCriteria(
                authenticator_attachment=AuthenticatorAttachment.PLATFORM,
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
        )
        request.session["wa_reg"] = bytes_to_base64url(opts.challenge)
        return Response(_json(options_to_json(opts)))


class PasskeyRegisterVerify(APIView):
    def post(self, request):
        challenge = request.session.pop("wa_reg", None)
        if not challenge:
            raise FlowError("Start Face ID setup again.", code="passkey_expired")
        try:
            v = verify_registration_response(credential=request.data.get("credential"), expected_challenge=base64url_to_bytes(challenge),
                                             expected_rp_id=WA["RP_ID"], expected_origin=WA["ORIGIN"], require_user_verification=True)
        except Exception as e:
            raise FlowError("Face ID couldn't be set up on this device. You can keep using your PIN.", code="passkey_failed") from e
        WebAuthnCredential.objects.update_or_create(
            credential_id=bytes_to_base64url(v.credential_id),
            defaults={"user": request.user, "public_key": bytes_to_base64url(v.credential_public_key), "sign_count": v.sign_count,
                      "device_label": str(request.data.get("device_label", ""))[:80]},
        )
        return Response(me_json(request))


class PasskeyUnlockOptions(APIView):
    permission_classes = [SignedIn]

    def post(self, request):
        creds = list(request.user.passkeys.all())
        if not creds:
            raise FlowError("Face ID isn't set up on this account.", code="no_passkey", status=404)
        opts = generate_authentication_options(
            rp_id=WA["RP_ID"], user_verification=UserVerificationRequirement.REQUIRED,
            allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id)) for c in creds],
        )
        request.session["wa_auth"] = bytes_to_base64url(opts.challenge)
        return Response(_json(options_to_json(opts)))


class PasskeyUnlockVerify(APIView):
    permission_classes = [SignedIn]

    def post(self, request):
        challenge = request.session.pop("wa_auth", None)
        cred = request.data.get("credential") or {}
        stored = request.user.passkeys.filter(credential_id=cred.get("id", "")).first()
        if not challenge or not stored:
            raise FlowError("Face ID didn't work. Use your PIN.", code="passkey_failed")
        try:
            v = verify_authentication_response(credential=cred, expected_challenge=base64url_to_bytes(challenge), expected_rp_id=WA["RP_ID"],
                                               expected_origin=WA["ORIGIN"], credential_public_key=base64url_to_bytes(stored.public_key),
                                               credential_current_sign_count=stored.sign_count, require_user_verification=True)
        except Exception as e:
            raise FlowError("Face ID didn't work. Use your PIN.", code="passkey_failed") from e
        stored.sign_count, stored.last_used_at = v.new_sign_count, timezone.now()
        stored.save(update_fields=["sign_count", "last_used_at"])
        acc.mark_unlocked(request)
        return Response(me_json(request))


class PasskeyRemove(APIView):
    def delete(self, request):
        request.user.passkeys.all().delete()
        return Response(me_json(request))


def _json(s: str):
    import json
    return json.loads(s)
