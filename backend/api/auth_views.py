"""Sign-up (email → code → name → PIN → Face ID), identity checks later in the app (NIN/BVN → ID → selfie),
sign-in, unlock and passkeys."""
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
            "kyc_status": u.kyc_status, "kyc_id_type": u.kyc_id_type, "nin_last4": u.nin_last4, "has_name": bool(u.first_name), "has_pin": bool(u.pin_hash), "pin_locked": bool(u.locked_at),
            "has_face_id": u.passkeys.exists(), "look": u.look, "daily_cap_kobo": u.daily_cap_kobo, "paused_all": u.paused_all,
            "notify_push": u.notify_push, "notify_whatsapp_recipients": u.notify_whatsapp_recipients,
            "notify_daily_summary": u.notify_daily_summary, "notify_low_balance": u.notify_low_balance,
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
              "notify_push": bool, "notify_whatsapp_recipients": bool, "notify_daily_summary": bool, "notify_low_balance": bool}

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
                user = User(username=s["email"], email=s["email"])
                user.set_unusable_password()
                user.save()
            ledger.ensure_user_accounts(user)
        request.session.pop(SIGNUP, None)
        login(request, user, backend=BACKEND)
        acc.mark_unlocked(request)
        return Response({**me_json(request), "step": "name" if not user.first_name else "pin"})


class SignupName(APIView):
    """What should we call you? (Your legal name comes from your NIN/BVN when you verify.)"""

    def post(self, request):
        first = " ".join(str(request.data.get("first_name", "")).split())[:60]
        last = " ".join(str(request.data.get("last_name", "")).split())[:60]
        if not first:
            raise FlowError("Add your first name.")
        request.user.first_name, request.user.last_name = first.upper(), last.upper()
        request.user.save(update_fields=["first_name", "last_name"])
        return Response(me_json(request))


# ------------------------------------------------------------------ verify identity (in the app, before money moves)

KYC = "kyc"  # session key holding the looked-up NIN/BVN record until the person confirms it's them
ID_LOOKUPS = {"nin": "lookup_nin", "bvn": "lookup_bvn"}


def kyc_user(request) -> User:
    u = request.user
    if u.is_verified:
        raise FlowError("You're already verified.", code="already_verified", status=409)
    return u


class KycLookup(APIView):
    def post(self, request):
        kyc_user(request)
        id_type = str(request.data.get("id_type", "nin")).lower()
        if id_type not in ID_LOOKUPS:
            raise FlowError("Choose NIN or BVN.")
        label = id_type.upper()
        number = "".join(c for c in str(request.data.get("number", "")) if c.isdigit())
        if len(number) != 11:
            raise FlowError(f"Your {label} has 11 digits.")
        record = getattr(get_kyc_provider(), ID_LOOKUPS[id_type])(number)
        if not record:
            raise FlowError(f"We couldn't find that {label}. Check the 11 digits and try again.", code="id_not_found")
        phone = acc.normalise_phone(record["phone"])
        request.session[KYC] = {"id_type": id_type, "hash": acc.nin_fingerprint(f"{id_type}:{number}"), "last4": number[-4:],
                                "phone": phone, "first_name": record["first_name"], "last_name": record["last_name"],
                                "dob": record["date_of_birth"]}
        return Response({"name": f"{record['first_name']} {record['last_name']}", "date_of_birth": record["date_of_birth"],
                         "phone_masked": acc.mask_phone(phone)})


class KycConfirm(APIView):
    """The person said "Yes, that's me"."""

    def post(self, request):
        u = kyc_user(request)
        k = request.session.get(KYC)
        if not k:
            raise FlowError("Enter your NIN or BVN again.", code="kyc_missing", status=409)
        if User.objects.filter(nin_hash=k["hash"]).exclude(pk=u.pk).exists():
            raise FlowError(f"This {k['id_type'].upper()} is already linked to another SpenDrip account.", code="id_taken", status=409)
        if User.objects.filter(phone=k["phone"]).exclude(pk=u.pk).exists():
            raise FlowError("The phone number on this record is already linked to another SpenDrip account.", code="id_taken", status=409)
        u.first_name, u.last_name, u.phone = k["first_name"], k["last_name"], k["phone"]
        u.nin_hash, u.nin_last4, u.kyc_id_type, u.kyc_status = k["hash"], k["last4"], k["id_type"], User.Kyc.NIN_VERIFIED
        u.save()
        KycCheck.objects.create(user=u, step=KycCheck.Step.NIN, passed=True, provider=get_kyc_provider().name,
                                raw={"dob": k["dob"], "id_type": k["id_type"]})
        request.session.pop(KYC, None)
        return Response({"step": "document"})


def needs_id_number(u: User) -> None:
    if u.kyc_status == User.Kyc.NOT_STARTED:
        raise FlowError("Start with your NIN or BVN.", code="kyc_missing", status=409)


class KycDocument(APIView):
    def post(self, request):
        user = kyc_user(request)
        needs_id_number(user)
        image = request.FILES.get("image")
        id_type = request.data.get("id_type", "nin")
        if not image:
            raise FlowError("Add a photo of the front of your ID.")
        if image.size > 8 * 1024 * 1024:
            raise FlowError("That photo is too big. Use one under 8 MB.")
        result = get_kyc_provider().check_document(image.read(), id_type=id_type, expected_name=user.get_full_name())
        KycCheck.objects.create(user=user, step=KycCheck.Step.DOCUMENT, passed=result["passed"], provider=get_kyc_provider().name,
                                raw={"id_type": id_type, **result})
        if not result["passed"]:
            raise FlowError("We couldn't read that ID. Lay it flat in good light with all four corners showing.", code="doc_unreadable")
        user.kyc_status = User.Kyc.DOC_UPLOADED
        user.save(update_fields=["kyc_status"])
        return Response({"step": "selfie", "checks": result["checks"]})


class KycSelfie(APIView):
    def post(self, request):
        user = kyc_user(request)
        if user.kyc_status != User.Kyc.DOC_UPLOADED:
            raise FlowError("Add a photo of your ID first.", code="kyc_missing", status=409)
        image = request.FILES.get("image")
        if not image:
            raise FlowError("Take a selfie to continue.")
        result = get_kyc_provider().match_selfie(image.read())
        KycCheck.objects.create(user=user, step=KycCheck.Step.SELFIE, passed=result["passed"], provider=get_kyc_provider().name, raw=result)
        if not result["passed"]:
            raise FlowError("Your selfie didn't match your ID. Try again in good light, looking straight at the camera.", code="face_mismatch")
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
