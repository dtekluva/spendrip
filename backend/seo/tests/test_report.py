import base64
import json
from datetime import date
from unittest import mock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core import mail
from django.core.management import call_command

from seo import report, search_console


def q(query, clicks, imp, pos, key="query"):
    return {key: query, "clicks": clicks, "impressions": imp, "ctr": clicks / imp if imp else 0, "position": pos}


def data(**kw):
    base = dict(
        start=date(2026, 10, 1), end=date(2026, 10, 31),
        totals=q("", 30, 1200, 14.2), totals_prev=q("", 10, 600, 20.0), totals_world=q("", 34, 1500, 15.0),
        queries=[q("send money to parents monthly", 5, 200, 3.0), q("how to budget", 0, 90, 34.0),
                 q("upkeep allowance", 4, 60, 8.5), q("pay house help salary", 1, 12, 6.0)],
        queries_prev=[q("send money to parents monthly", 2, 150, 4.0)],
        pages=[q("https://spendrip.com/", 20, 800, 10.0, key="page"), q("https://spendrip.com/fees/", 5, 200, 6.0, key="page")],
        sitemap=["https://spendrip.com/", "https://spendrip.com/fees/", "https://spendrip.com/household-payroll/"],
    )
    base.update(kw)
    return report.Data(**base)


def test_last_month():
    assert report.last_month(date(2026, 11, 4)) == (date(2026, 10, 1), date(2026, 10, 31))
    assert report.last_month(date(2027, 1, 4)) == (date(2026, 12, 1), date(2026, 12, 31))


def test_sections():
    s = report.sections(data())
    assert s["top"][0]["query"] == "send money to parents monthly" and s["top"][0]["change"] == 50
    assert {x["query"] for x in s["new"]} == {"how to budget", "upkeep allowance", "pay house help salary"}
    assert [x["query"] for x in s["wins"]] == ["upkeep allowance", "pay house help salary"]
    assert [x["query"] for x in s["low_ctr"]] == ["send money to parents monthly"]  # top 5, 2.5% click rate
    assert [x["query"] for x in s["gaps"]] == ["how to budget"]
    assert s["unseen"] == ["https://spendrip.com/household-payroll/"]


def test_render_handles_an_empty_month():
    empty = q("", 0, 0, 0.0)
    subject, text, html = report.render(data(totals=empty, totals_prev=empty, totals_world=empty, queries=[], queries_prev=[], pages=[]))
    assert "0 clicks" in subject and "Nothing this month." in text and "<table" in html


def test_render():
    subject, text, html = report.render(data())
    assert "October 2026" in subject and "+200%" in text and "Pages not showing up yet" in html


def test_token_is_a_signed_jwt():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    creds = {"client_email": "r@x.iam.gserviceaccount.com", "private_key": pem, "token_uri": "https://oauth2.example/token"}
    with mock.patch("seo.search_console.requests.post") as post:
        post.return_value.json.return_value = {"access_token": "tok"}
        assert search_console.access_token(creds) == "tok"
    assertion = post.call_args.kwargs["data"]["assertion"]
    claims = json.loads(base64.urlsafe_b64decode(assertion.split(".")[1] + "=="))
    assert claims["iss"] == creds["client_email"] and claims["scope"].endswith("webmasters.readonly")


@pytest.mark.django_db
def test_command_emails_the_report(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    fake = mock.Mock()
    with mock.patch("seo.management.commands.seo_report.Client", return_value=fake), \
         mock.patch("seo.report.fetch", return_value=data()) as fetch:
        call_command("seo_report", "--today", "2026-11-04")
    assert fetch.call_args.args[1] == date(2026, 11, 4)
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["hello@spendrip.com"]
