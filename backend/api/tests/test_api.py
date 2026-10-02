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

def sign_up(c, email="ada@example.com", first="Ada"):
    r = c.post("/api/signup/start", {"email": email}, format="json").json()
    me = c.post("/api/signup/otp/verify", {"code": r["dev_code"]}, format="json").json()
    c.post("/api/signup/name", {"first_name": first, "last_name": "Okafor"}, format="json")
    c.post("/api/auth/pin", {"pin": "2580"}, format="json")
    return me


def test_sign_up_is_email_code_name_pin_with_no_id_checks(dev, db):
    from django.core import mail
    c = APIClient()
    assert c.get("/api/me").json() == {"signed_in": False, "dev_tools": True, "signup": None}

    bad = c.post("/api/signup/start", {"email": "not-an-email"}, format="json")
    assert bad.status_code == 400 and "email" in bad.json()["error"]
    r = c.post("/api/signup/start", {"email": " Ada@Example.com "}, format="json").json()
    assert r["step"] == "code" and r["email_masked"] == "ad•@example.com" and len(r["dev_code"]) == 6
    assert mail.outbox[-1].to == ["ada@example.com"] and r["dev_code"] in mail.outbox[-1].subject
    assert c.get("/api/me").json()["signup"] == {"step": "code", "email_masked": "ad•@example.com"}

    wrong = c.post("/api/signup/otp/verify", {"code": "000000" if r["dev_code"] != "000000" else "111111"}, format="json")
    assert wrong.status_code == 400 and wrong.json()["code"] == "otp_wrong"
    me = c.post("/api/signup/otp/verify", {"code": r["dev_code"]}, format="json").json()
    assert me["signed_in"] and not me["locked"] and me["step"] == "name"
    assert me["user"]["kyc_status"] == "not_started" and me["user"]["funding_account"] is None

    assert c.post("/api/signup/name", {"first_name": "  "}, format="json").status_code == 400
    assert c.post("/api/signup/name", {"first_name": "Ada", "last_name": "Okafor"}, format="json").json()["user"]["first_name"] == "Ada"
    weak = c.post("/api/auth/pin", {"pin": "1234"}, format="json")
    assert weak.status_code == 400 and "too easy" in weak.json()["error"]
    assert c.post("/api/auth/pin", {"pin": "2580"}, format="json").json()["user"]["has_pin"] is True
    # In the app straight away: plans and recipients work, money doesn't move yet.
    assert c.get("/api/summary").status_code == 200
    r = c.post("/api/funding/card/start", {"amount_kobo": 500_000}, format="json")
    assert r.status_code == 403 and r.json()["code"] == "kyc_required"


def test_same_email_cannot_sign_up_twice(dev, db):
    sign_up(APIClient())
    again = APIClient().post("/api/signup/start", {"email": "ADA@example.com"}, format="json")
    assert again.status_code == 409 and again.json()["code"] == "already_registered"


def test_unfinished_sign_up_can_start_again(dev, db):
    c = APIClient()
    r = c.post("/api/signup/start", {"email": "ada@example.com"}, format="json").json()
    c.post("/api/signup/otp/verify", {"code": r["dev_code"]}, format="json")  # then closed the app before a PIN
    c2 = APIClient()
    r = c2.post("/api/signup/start", {"email": "ada@example.com"}, format="json").json()
    me = c2.post("/api/signup/otp/verify", {"code": r["dev_code"]}, format="json").json()
    assert me["signed_in"] and User.objects.filter(email="ada@example.com").count() == 1


def test_skipping_steps_is_refused(dev, db):
    r = APIClient().post("/api/signup/otp/verify", {"code": "123456"}, format="json")
    assert r.status_code == 409 and r.json()["code"] == "signup_missing"


# ------------------------------------------------------------------ verify identity, later

@pytest.mark.parametrize("id_type,phone_masked", [("nin", "0804 ••• 8901"), ("bvn", "0814 ••• 8901")])
def test_verify_with_nin_or_bvn_then_id_then_selfie(dev, db, id_type, phone_masked):
    c = APIClient()
    sign_up(c)
    assert c.post("/api/kyc/selfie", {"image": IMG()}).json()["code"] == "kyc_missing"
    r = c.post("/api/kyc/lookup", {"id_type": id_type, "number": "123 4567 8901"}, format="json").json()
    assert r["name"] == "ADAEZE OKONKWO" and r["phone_masked"] == phone_masked
    assert c.post("/api/kyc/confirm").json() == {"step": "document"}
    assert c.post("/api/kyc/document", {"image": IMG(), "id_type": "nin"}).json()["step"] == "selfie"
    me = c.post("/api/kyc/selfie", {"image": IMG()}).json()
    u = me["user"]
    assert u["kyc_status"] == "verified" and u["kyc_id_type"] == id_type and u["first_name"] == "Adaeze"
    assert u["funding_account"]["account_number"].startswith("8420")
    assert c.post("/api/kyc/lookup", {"id_type": "nin", "number": "12345678901"}, format="json").status_code == 409


def test_same_nin_cannot_verify_two_accounts(dev, db):
    a, b = APIClient(), APIClient()
    sign_up(a, "a@example.com")
    sign_up(b, "b@example.com")
    for c in (a, b):
        c.post("/api/kyc/lookup", {"id_type": "nin", "number": "12345678901"}, format="json")
    assert a.post("/api/kyc/confirm").status_code == 200
    r = b.post("/api/kyc/confirm")
    assert r.status_code == 409 and r.json()["code"] == "id_taken"


def test_unverified_users_plans_do_not_send(dev, db, settings):
    from datetime import timedelta
    from django.utils import timezone
    from drips.models import Recipient, Run
    from drips.worker import Worker
    c = APIClient()
    sign_up(c)
    u = User.objects.get(email="ada@example.com")
    rec = Recipient.objects.create(user=u, label="Me", is_self=True, bank_name="GTBank", nip_bank_code="000013",
                                   account_number="0123456789", verified_account_name="ADA OKAFOR")
    plan = Plan.objects.create(user=u, label="Data", amount_kobo=100_000, recipient=rec, frequency="daily", time_local="09:00",
                               starts_at=timezone.now() - timedelta(days=1))
    run = Run.objects.create(plan=plan, user=u, scheduled_for=timezone.now() - timedelta(minutes=1), amount_kobo=100_000, fee_kobo=5000)
    Worker().process_due(timezone.now())
    run.refresh_from_db()
    assert run.status == Run.Status.SKIPPED_PAUSED and run.last_error == "not_verified"


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


def test_five_wrong_pins_lock_until_email_reset(demo, dev):
    c = APIClient()
    c.force_login(demo)
    for _ in range(5):
        r = c.post("/api/auth/unlock", {"pin": "9999"}, format="json")
    assert r.status_code == 423 and r.json()["code"] == "pin_locked"

    new = APIClient()
    code = new.post("/api/auth/signin/start", {"email": "Demo@SpenDrip.com"}, format="json").json()["dev_code"]
    me = new.post("/api/auth/signin/verify", {"email": "demo@spendrip.com", "code": code, "new_pin": "3698"}, format="json").json()
    assert me["signed_in"] and not me["locked"] and not me["user"]["pin_locked"]


def test_sign_in_on_a_new_device_needs_code_and_pin(demo, dev):
    c = APIClient()
    code = c.post("/api/auth/signin/start", {"email": "demo@spendrip.com"}, format="json").json()["dev_code"]
    bad = c.post("/api/auth/signin/verify", {"email": "demo@spendrip.com", "code": code, "pin": "0000"}, format="json")
    assert bad.status_code == 400 and bad.json()["code"] == "pin_wrong"
    code = c.post("/api/auth/signin/start", {"email": "demo@spendrip.com"}, format="json").json()["dev_code"]
    assert c.post("/api/auth/signin/verify", {"email": "demo@spendrip.com", "code": code, "pin": "2580"}, format="json").json()["signed_in"]


def test_unknown_email_gets_a_plain_message(dev, db):
    r = APIClient().post("/api/auth/signin/start", {"email": "nobody@example.com"}, format="json")
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


# ------------------------------------------------------------------ start and end dates

def test_plan_for_three_months_shows_the_whole_commitment(demo, dev):
    from datetime import date, timedelta
    c = unlocked_client(demo)
    start = (date.today() + timedelta(days=10)).isoformat()
    body = plan_body(demo, label="Rent help", frequency="monthly", month_day=int(start[8:]), weekday=None,
                     start_date=start, end_mode="months", duration_months=3)
    pv = c.post("/api/plans/preview", body, format="json").json()
    assert pv["total_drips"] == 3 and pv["total_amount_kobo"] == 3_000_000 and pv["last_drip_at"]
    p = c.post("/api/plans", body, format="json").json()["plan"]
    assert p["state"] == "scheduled" and p["end_mode"] == "months" and p["duration_months"] == 3
    assert p["total_drips"] == 3 and p["drips_done"] == 0 and str(p["start_date"]) == start


def test_until_a_date_and_bad_windows(demo, dev):
    from datetime import date, timedelta
    c = unlocked_client(demo)
    today = date.today()
    ok = c.post("/api/plans", plan_body(demo, frequency="daily", weekday=None, end_mode="date",
                                         end_date=(today + timedelta(days=6)).isoformat()), format="json")
    assert ok.status_code == 201 and ok.json()["plan"]["end_mode"] == "date"
    past = c.post("/api/plans", plan_body(demo, start_date=(today - timedelta(days=1)).isoformat()), format="json")
    assert past.status_code == 400 and "today or a later date" in past.json()["error"]
    before = c.post("/api/plans", plan_body(demo, start_date=(today + timedelta(days=5)).isoformat(), end_mode="date",
                                             end_date=(today + timedelta(days=2)).isoformat()), format="json")
    assert before.status_code == 400 and "before the start" in before.json()["error"]
    none = c.post("/api/plans", plan_body(demo, frequency="monthly", weekday=None, month_day=28, start_date=today.isoformat(),
                                           end_mode="date", end_date=today.isoformat()), format="json")
    assert none.status_code == 400 or none.json()["plan"]["total_drips"] >= 1
    too_long = c.post("/api/plans", plan_body(demo, end_mode="months", duration_months=40), format="json")
    assert too_long.status_code == 400 and "between 1 and 36" in too_long.json()["error"]


def test_finished_plan_releases_priority_and_can_be_extended(demo, dev):
    from datetime import timedelta
    from django.utils import timezone
    from drips.services import finish_plans
    c = unlocked_client(demo)
    upkeep = demo.plans.get(label="Upkeep")  # priority 1; Mum is 2
    upkeep.end_mode, upkeep.ends_at = "date", timezone.now() - timedelta(days=1)
    upkeep.save()
    from drips.models import Run
    Run.objects.filter(plan=upkeep, status="scheduled").delete()
    assert finish_plans(timezone.now()) == 1
    ranks = {p["label"]: (p["priority_rank"], p["state"]) for p in c.get("/api/plans").json()}
    assert ranks["Upkeep"] == (None, "finished") and ranks["Mum"][0] == 1
    assert c.patch(f"/api/plans/{upkeep.id}", {"status": "active"}, format="json").json()["code"] == "finished"
    from datetime import date
    ext = c.patch(f"/api/plans/{upkeep.id}", {"end_mode": "date", "end_date": (date.today() + timedelta(days=30)).isoformat()}, format="json")
    assert ext.status_code == 200 and ext.json()["plan"]["state"] in ("active", "scheduled")
