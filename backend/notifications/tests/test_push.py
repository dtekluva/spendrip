import json
from types import SimpleNamespace

import pytest
from pywebpush import WebPushException

from api.tests.test_api import unlocked_client
from notifications.models import OutboxMessage, PushDevice
from notifications.services import notify, notify_app

SUB = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": "BKey", "auth": "auth1"}}


@pytest.fixture
def keys(settings):
    settings.WEB_PUSH = {"PUBLIC_KEY": "pub", "PRIVATE_KEY": "priv", "SUBJECT": "mailto:hello@spendrip.com"}


@pytest.fixture
def sent(monkeypatch):
    """Every web push the code tries to send, instead of sending it."""
    calls = []
    monkeypatch.setattr("pywebpush.webpush", lambda sub, data, **kw: calls.append((sub["endpoint"], json.loads(data), kw)))
    return calls


def device(user, endpoint=SUB["endpoint"]):
    return PushDevice.objects.create(user=user, endpoint=endpoint, p256dh="BKey", auth="auth1")


def test_register_and_remove_a_device(user, keys):
    user.notify_push = False
    user.save(update_fields=["notify_push"])
    c = unlocked_client(user)
    assert c.post("/api/push/devices", SUB, format="json").status_code == 201
    assert c.post("/api/push/devices", SUB, format="json").json()["devices"] == 1  # same phone again: still one
    user.refresh_from_db()
    assert user.notify_push  # turning it on for a device turns push on
    assert c.get("/api/me").json()["user"]["push_devices"] == 1
    assert c.delete("/api/push/devices", {"endpoint": SUB["endpoint"]}, format="json").json()["devices"] == 0


def test_rejects_a_bad_subscription(user):
    r = unlocked_client(user).post("/api/push/devices", {"endpoint": "http://evil", "keys": {}}, format="json")
    assert r.status_code == 400


def test_device_moves_to_whoever_signs_in(user, keys):
    from accounts.models import User
    other = User.objects.create(username="bola")
    device(other)
    unlocked_client(user).post("/api/push/devices", SUB, format="json")
    assert PushDevice.objects.get().user == user


def test_push_message_reaches_the_phone(user, keys, sent):
    device(user)
    msg = notify(user, key="run:1:paid:push", channel=OutboxMessage.Channel.PUSH, template="self_paid", body="🍲 Food: ₦5,000 sent")
    assert msg.status == OutboxMessage.Status.SENT
    (endpoint, data, kw), = sent
    assert data == {"title": "Money sent", "body": "🍲 Food: ₦5,000 sent", "url": "/activity", "tag": "run:1:paid"}
    assert kw["vapid_private_key"] == "priv" and kw["vapid_claims"] == {"sub": "mailto:hello@spendrip.com"}


def test_money_added_goes_to_the_app_and_the_phone(user, keys, sent):
    device(user)
    notify_app(user, key="inflow:9", template="self_topped_up", body="₦10,000 added to your SpenDrip balance.")
    assert {m.channel for m in OutboxMessage.objects.filter(user=user)} == {"in_app", "push"}
    assert sent[0][1]["title"] == "Money added"


def test_push_off_or_no_device_is_skipped(user, keys, sent):
    m = notify(user, key="a:push", channel="push", template="self_paid", body="x")
    assert m.status == OutboxMessage.Status.SKIPPED  # no device yet
    device(user)
    user.notify_push = False
    user.save(update_fields=["notify_push"])
    assert notify(user, key="b:push", channel="push", template="self_paid", body="x").status == OutboxMessage.Status.SKIPPED
    assert not sent


def test_without_keys_push_is_only_recorded(user, sent):
    device(user)
    assert notify(user, key="c:push", channel="push", template="self_paid", body="x").status == OutboxMessage.Status.MOCKED
    assert not sent


@pytest.mark.parametrize("code,kept", [(410, False), (404, False), (500, True)])
def test_gone_devices_are_dropped(user, keys, monkeypatch, code, kept):
    def boom(*a, **kw):
        raise WebPushException("nope", response=SimpleNamespace(status_code=code))
    monkeypatch.setattr("pywebpush.webpush", boom)
    device(user)
    assert notify(user, key="d:push", channel="push", template="self_paid", body="x").status == OutboxMessage.Status.SKIPPED
    assert PushDevice.objects.exists() is kept


def test_test_notification(user, keys, sent):
    c = unlocked_client(user)
    assert c.post("/api/push/test").status_code == 400  # nothing to send to
    device(user)
    assert c.post("/api/push/test").json()["sent"] == 1
    assert sent[0][1]["title"] == "Notifications are on"
