"""
A small Google Search Console client: signs in as a service account (no Google SDK needed) and runs Search Analytics queries.

Credentials: the service account's JSON key, either base64 in GSC_CREDENTIALS_B64 or as a file at GSC_CREDENTIALS_FILE.
The service account's email must be added as a user (Restricted is enough) on the Search Console property.
"""
from __future__ import annotations

import base64
import json
import time
from datetime import date
from urllib.parse import quote

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings

SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
API = "https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"


class NotConfigured(Exception):
    pass


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def credentials() -> dict:
    c = settings.SEARCH_CONSOLE
    if c["CREDENTIALS_B64"]:
        return json.loads(base64.b64decode(c["CREDENTIALS_B64"]))
    if c["CREDENTIALS_FILE"]:
        with open(c["CREDENTIALS_FILE"]) as f:
            return json.load(f)
    raise NotConfigured("Set GSC_CREDENTIALS_B64 or GSC_CREDENTIALS_FILE to the service account's JSON key.")


def access_token(creds: dict) -> str:
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = _b64url(json.dumps({"iss": creds["client_email"], "scope": SCOPE, "aud": creds["token_uri"],
                                 "iat": now, "exp": now + 3600}).encode())
    key = serialization.load_pem_private_key(creds["private_key"].encode(), password=None)
    sig = _b64url(key.sign(f"{header}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256()))
    r = requests.post(creds["token_uri"], data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                                "assertion": f"{header}.{claims}.{sig}"}, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


class Client:
    def __init__(self, site: str | None = None, token: str | None = None):
        self.site = site or settings.SEARCH_CONSOLE["SITE"]
        self.token = token or access_token(credentials())

    def query(self, start: date, end: date, dimensions: list[str], country: str | None = None, limit: int = 1000) -> list[dict]:
        """Rows as {keys..., clicks, impressions, ctr, position}, keyed by dimension name."""
        body: dict = {"startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": dimensions, "rowLimit": limit}
        if country:
            body["dimensionFilterGroups"] = [{"filters": [{"dimension": "country", "operator": "equals", "expression": country}]}]
        r = requests.post(API.format(site=quote(self.site, safe="")), json=body,
                          headers={"Authorization": f"Bearer {self.token}"}, timeout=30)
        r.raise_for_status()
        return [{**dict(zip(dimensions, row.get("keys", []))), **{k: row[k] for k in ("clicks", "impressions", "ctr", "position")}}
                for row in r.json().get("rows", [])]
