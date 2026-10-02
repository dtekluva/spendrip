import time

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from rest_framework.test import APIClient

from accounts.models import User
from drips.models import Plan

IMG = lambda: SimpleUploadedFile("id.jpg", b"\xff\xd8fake-jpeg-bytes", content_type="image/jpeg")  # noqa: E731


@pytest.fixture
def dev(settings):
    settings.SPENDRIP = {**settings.SPENDRIP, "DEV_TOOLS": True, "OTP_RESEND_SECONDS": 0}
    return settings


@pytest.fixture
def demo(db, dev):
    call_command("seed_demo")
    return User.objects.get(username="demo")


def unlocked_client(user):
    c = APIClient()
    c.force_login(user)
    s = c.session
    s["unlocked_at"] = s["last_seen"] = time.time()
    s.save()
    return c


# ------------------------------------------------------------------ sign-up

def test_full_sign_up_nin_id_selfie_code_pin(dev, db):
    c = APIClient()
    assert c.get("/api/me").json() == {"signed_in": False, "dev_tools": True, "signup": None}

    r = c.post("/api/signup/nin", {"nin": "123 4567 8901"}, format="json").json()
    assert r["name"] == "ADAEZE OKONKWO" and r["phone_masked"] == "0804 ••• 8901"
    assert c.post("/api/signup/confirm").json() == {"step": "document"}
    assert c.post("/api/signup/document", {"image": IMG(), "id_type": "nin"}).json()["step"] == "selfie"
    otp = c.post("/api/signup/selfie", {"image": IMG()}).json()
    assert otp["step"] == "otp" and len(otp["dev_code"]) == 6

    wrong = c.post("/api/signup/otp/verify", {"code": "000000" if otp["dev_code"] != "000000" else "111111"}, format="json")
    assert wrong.status_code == 400 and wrong.json()["code"] == "otp_wrong"
    me = c.post("/api/signup/otp/verify", {"code": otp["dev_code"]}, format="json").json()
    assert me["signed_in"] and not me["locked"] and me["user"]["kyc_status"] == "verified"
    assert me["user"]["funding_account"]["account_number"].startswith("8420")

    weak = c.post("/api/auth/pin", {"pin": "1234"}, format="json")
    assert weak.status_code == 400 and "too easy" in weak.json()["error"]
    assert c.post("/api/auth/pin", {"pin": "2580"}, format="json").json()["user"]["has_pin"] is True


def test_same_nin_cannot_sign_up_twice(dev, db):
    def sign_up():
        c = APIClient()
        c.post("/api/signup/nin", {"nin": "12345678901"}, format="json")
        return c, c.post("/api/signup/confirm")
    c, _ = sign_up()
    c.post("/api/signup/document", {"image": IMG()})
    code = c.post("/api/signup/selfie", {"image": IMG()}).json()["dev_code"]
    c.post("/api/signup/otp/verify", {"code": code}, format="json")
    _, again = sign_up()
    assert again.status_code == 409 and again.json()["code"] == "already_registered"


def test_skipping_steps_is_refused(dev, db):
    r = APIClient().post("/api/signup/selfie", {"image": IMG()})
    assert r.status_code == 409 and r.json()["code"] == "signup_missing"


# ------------------------------------------------------------------ lock, unlock, sign-in

def test_app_locks_after_idle_and_pin_unlocks(demo, dev):
    c = unlocked_client(demo)
    assert c.get("/api/summary").status_code == 200
    s = c.session
    s["last_seen"] = time.time() - 3600
    s.save()
    locked = c.get("/api/summary")
    assert locked.status_code == 403 and locked.json()["code"] == "locked"
    bad = c.post("/api/auth/unlock", {"pin": "1111"}, format="json").json()
    assert bad["error"] == "Wrong PIN. 4 tries left."
    assert c.post("/api/auth/unlock", {"pin": "2580"}, format="json").json()["locked"] is False
    assert c.get("/api/summary").status_code == 200


def test_five_wrong_pins_lock_until_sms_reset(demo, dev):
    c = APIClient()
    c.force_login(demo)
    for _ in range(5):
        r = c.post("/api/auth/unlock", {"pin": "9999"}, format="json")
    assert r.status_code == 423 and r.json()["code"] == "pin_locked"

    new = APIClient()
    code = new.post("/api/auth/signin/start", {"phone": "+234 803 123 4417"}, format="json").json()["dev_code"]
    me = new.post("/api/auth/signin/verify", {"phone": "08031234417", "code": code, "new_pin": "3698"}, format="json").json()
    assert me["signed_in"] and not me["locked"] and not me["user"]["pin_locked"]


def test_sign_in_on_a_new_device_needs_code_and_pin(demo, dev):
    c = APIClient()
    code = c.post("/api/auth/signin/start", {"phone": "08031234417"}, format="json").json()["dev_code"]
    bad = c.post("/api/auth/signin/verify", {"phone": "08031234417", "code": code, "pin": "0000"}, format="json")
    assert bad.status_code == 400 and bad.json()["code"] == "pin_wrong"
    code = c.post("/api/auth/signin/start", {"phone": "08031234417"}, format="json").json()["dev_code"]
    assert c.post("/api/auth/signin/verify", {"phone": "08031234417", "code": code, "pin": "2580"}, format="json").json()["signed_in"]


def test_unknown_number_gets_a_plain_message(dev, db):
    r = APIClient().post("/api/auth/signin/start", {"phone": "08000000000"}, format="json")
    assert r.status_code == 404 and "Create one instead" in r.json()["error"]


# ------------------------------------------------------------------ plans, priorities, recipients

def plan_body(demo, **kw):
    me = demo.recipients.get(is_self=True)
    return {"label": "Data", "emoji": "📱", "tint": "mint", "amount_kobo": 1_000_000, "recipient_id": me.id,
            "frequency": "weekly", "weekday": 1, "time_local": "09:00", **kw}


def test_new_priority_1_pushes_others_down_and_drops_the_fourth(demo, dev):
    c = unlocked_client(demo)
    c.post("/api/plans", plan_body(demo, label="Rent", priority_rank=3), format="json")  # Upkeep 1, Mum 2, Rent 3
    r = c.post("/api/plans", plan_body(demo, label="Data", priority_rank=1), format="json").json()
    assert r["dropped_priorities"] == ["Rent"]
    ranks = {p["label"]: p["priority_rank"] for p in c.get("/api/plans").json()}
    assert ranks == {"Upkeep": 2, "Mum": 3, "Fuel": None, "Cousin": None, "Rent": None, "Data": 1}


def test_preview_shows_cost_and_top_up_change(demo, dev):
    c = unlocked_client(demo)
    r = c.post("/api/plans/preview", plan_body(demo, frequency="daily", amount_kobo=500_000), format="json").json()
    assert len(r["next_dates"]) == 5
    assert r["month_cost_kobo"] == r["runs_this_month"] * 505_000
    assert r["top_up_after_kobo"] >= r["top_up_before_kobo"]


def test_bad_plan_input_gets_a_plain_message(demo, dev):
    c = unlocked_client(demo)
    r = c.post("/api/plans", plan_body(demo, frequency="weekly", weekday=9), format="json")
    assert r.status_code == 400 and r.json()["error"] == "Weekly plans need a weekday 1–7 (Mon–Sun)."
    r = c.post("/api/plans", plan_body(demo, amount_kobo=50), format="json")
    assert "between ₦100" in r.json()["error"]


def test_pause_and_delete_a_plan(demo, dev):
    c = unlocked_client(demo)
    fuel = Plan.objects.get(user=demo, label="Fuel")
    assert c.patch(f"/api/plans/{fuel.id}", {"status": "paused"}, format="json").json()["plan"]["next_at"] is None
    assert c.delete(f"/api/plans/{fuel.id}").status_code == 204
    assert "Fuel" not in [p["label"] for p in c.get("/api/plans").json()]


def test_recipients_are_checked_and_protected(demo, dev):
    c = unlocked_client(demo)
    look = c.post("/api/recipients/lookup", {"nip_bank_code": "000014", "account_number": "0011223344"}, format="json").json()
    assert look["bank_name"] == "Access Bank" and look["account_name"]
    r = c.post("/api/recipients", {"label": "Sis", "nip_bank_code": "000014", "account_number": "0011223344"}, format="json")
    assert r.status_code == 201 and r.json()["verified_account_name"] == look["account_name"]
    dup = c.post("/api/recipients", {"label": "Sis", "nip_bank_code": "000014", "account_number": "0011223344"}, format="json")
    assert dup.status_code == 409
    mum = demo.recipients.get(label="Mum")
    in_use = c.delete(f"/api/recipients/{mum.id}")
    assert in_use.status_code == 409 and "Mum still pays this person" in in_use.json()["error"]


def test_summary_calendar_activity_and_settings(demo, dev):
    c = unlocked_client(demo)
    s = c.get("/api/summary").json()
    assert s["balance"]["available_kobo"] == 25_000_000 and s["fee_kobo"] == 5_000
    assert c.get("/api/calendar").json()["events"]
    assert c.get("/api/calendar", {"month": "2030-01"}).status_code == 400
    c.post("/api/dev/top-up", {"amount_naira": 1000}, format="json")
    assert c.get("/api/activity").json()[0]["kind"] == "inflow"
    me = c.patch("/api/me/settings", {"look": "dark", "daily_cap_kobo": 5_000_000, "paused_all": True}, format="json").json()
    assert me["user"]["look"] == "dark" and me["user"]["paused_all"] is True
    assert c.patch("/api/me/settings", {"look": "neon"}, format="json").status_code == 400


# ------------------------------------------------------------------ system

def test_cron_tick_needs_the_secret(settings, db):
    c = APIClient()
    settings.SPENDRIP = {**settings.SPENDRIP, "CRON_SECRET": ""}
    assert c.get("/api/cron/tick").status_code == 503
    settings.SPENDRIP = {**settings.SPENDRIP, "CRON_SECRET": "s3cret"}
    assert c.get("/api/cron/tick", HTTP_AUTHORIZATION="Bearer nope").status_code == 403
    assert c.get("/api/cron/tick", HTTP_AUTHORIZATION="Bearer s3cret").status_code == 200


def test_webhook_credits_a_verified_inflow_once(demo, monkeypatch):
    from api import system_views
    from ledger import services as ledger
    from providers.base import InflowEvent

    acct = demo.funding_accounts.first().account_number

    class FakeLiberty:
        name = "liberty"

        def verify_inflow(self, session_id):
            return InflowEvent(provider="liberty", reference=session_id, account_number=acct, amount_kobo=700_000, sender_name="TOLU")

    monkeypatch.setattr(system_views, "get_payment_provider", lambda: FakeLiberty())
    c = APIClient()
    assert c.post("/api/webhooks/liberty", {"session_id": "S1"}, format="json").json()["credited"] is True
    assert c.post("/api/webhooks/liberty", {"session_id": "S1"}, format="json").json()["credited"] is False
    assert ledger.balance(demo).available_kobo == 25_000_000 + 700_000


def test_dev_tools_are_off_in_production(demo, settings):
    settings.SPENDRIP = {**settings.SPENDRIP, "DEV_TOOLS": False}
    c = unlocked_client(demo)
    assert c.post("/api/dev/top-up", {"amount_naira": 1000}, format="json").status_code == 404
    assert c.post("/api/dev/tick").status_code == 404
    assert APIClient().get("/api/summary").json()["code"] == "signed_out"


def test_waitlist_takes_phone_or_email_once(db):
    c = APIClient()
    r = c.post("/api/waitlist", {"contact": "+234 803 123 4567", "name": "Tolu"}, format="json")
    assert r.status_code == 201 and "on the list" in r.json()["message"]
    again = c.post("/api/waitlist", {"contact": "08031234567"}, format="json")
    assert again.status_code == 200 and again.json()["already"] is True
    assert c.post("/api/waitlist", {"contact": "Ada@Example.com"}, format="json").status_code == 201
    bad = c.post("/api/waitlist", {"contact": "hello"}, format="json")
    assert bad.status_code == 400 and "phone number" in bad.json()["error"]
    from accounts.models import WaitlistEntry
    assert sorted(WaitlistEntry.objects.values_list("contact", flat=True)) == ["08031234567", "ada@example.com"]


def test_waitlist_is_rate_limited(db):
    from django.core.cache import cache
    cache.clear()
    c = APIClient()
    for i in range(10):
        c.post("/api/waitlist", {"contact": f"user{i}@example.com"}, format="json")
    assert c.post("/api/waitlist", {"contact": "one.more@example.com"}, format="json").status_code == 429


def test_waitlist_emails_a_welcome_only_to_new_email_signups(db):
    from django.core import mail
    from django.core.cache import cache
    cache.clear()
    c = APIClient()
    c.post("/api/waitlist", {"contact": "ada@example.com", "name": "Ada"}, format="json")
    c.post("/api/waitlist", {"contact": "ada@example.com"}, format="json")  # already on the list: no second email
    c.post("/api/waitlist", {"contact": "08031234567"}, format="json")  # phone: no email
    assert len(mail.outbox) == 1
    m = mail.outbox[0]
    assert m.to == ["ada@example.com"] and "waitlist" in m.subject and "Hi Ada" in m.body
    assert m.alternatives and "You're on the list" in m.alternatives[0][0].replace("&#x27;", "'")


def test_waitlist_still_joins_when_email_fails(db, monkeypatch):
    from django.core.cache import cache
    from accounts.models import WaitlistEntry
    cache.clear()

    def boom(*a, **k):
        raise RuntimeError("mail down")
    monkeypatch.setattr("django.core.mail.EmailMultiAlternatives.send", boom)
    r = APIClient().post("/api/waitlist", {"contact": "bo@example.com"}, format="json")
    assert r.status_code == 201 and WaitlistEntry.objects.filter(contact="bo@example.com").exists()


def test_admin_invite_action_emails_and_stamps(db):
    from django.contrib.admin.sites import site
    from django.core import mail
    from django.test import RequestFactory
    from accounts.models import WaitlistEntry
    a = WaitlistEntry.objects.create(contact="ada@example.com", kind="email", name="Ada")
    WaitlistEntry.objects.create(contact="08031234567", kind="phone")
    model_admin = site._registry[WaitlistEntry]
    req = RequestFactory().post("/")
    model_admin.message_user = lambda *args, **kw: None
    model_admin.send_invites(req, WaitlistEntry.objects.all())
    assert [m.to for m in mail.outbox] == [["ada@example.com"]] and "invite" in mail.outbox[0].subject
    a.refresh_from_db()
    assert a.invited_at is not None


def test_mailgun_backend_posts_to_the_api(settings, monkeypatch):
    from django.core.mail import EmailMultiAlternatives
    from notifications.mailgun import MailgunBackend
    settings.MAILGUN = {"API_KEY": "k", "DOMAIN": "mg.example.com", "API_BASE": "https://api.mailgun.net"}
    calls = []

    class R:
        def raise_for_status(self): pass
    monkeypatch.setattr("notifications.mailgun.requests.post", lambda url, **kw: calls.append((url, kw)) or R())
    m = EmailMultiAlternatives("Hi", "text", "SpenDrip <hello@mg.example.com>", ["a@b.com"])
    m.attach_alternative("<b>html</b>", "text/html")
    assert MailgunBackend().send_messages([m]) == 1
    url, kw = calls[0]
    assert url == "https://api.mailgun.net/v3/mg.example.com/messages" and kw["auth"] == ("api", "k")
    assert kw["data"]["html"] == "<b>html</b>" and kw["data"]["to"] == ["a@b.com"]
