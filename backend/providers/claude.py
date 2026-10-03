"""A small client for Claude's Messages API, used to read ID photos and check selfies."""
from __future__ import annotations

import base64
import json
import logging
import re
import time

import requests
from django.conf import settings

from .base import ProviderError

log = logging.getLogger(__name__)
RETRY_STATUSES = {408, 409, 429, 500, 502, 503, 504, 529}  # busy, rate-limited or briefly down: worth another go


def media_type(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    raise ValueError("unsupported image type")


def vision_json(prompt: str, image: bytes, *, max_tokens: int = 700, session: requests.Session | None = None) -> dict:
    """Send one image and a prompt that asks for a JSON object; return that object."""
    cfg = settings.ANTHROPIC
    if not cfg["API_KEY"]:
        raise ProviderError("ANTHROPIC_API_KEY is not set")
    body = {
        "model": cfg["MODEL"], "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type(image), "data": base64.b64encode(image).decode()}},
            {"type": "text", "text": prompt},
        ]}],
    }
    headers = {"x-api-key": cfg["API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"}
    for attempt in range(3):
        last = attempt == 2
        try:
            r = (session or requests).post(f"{cfg['BASE_URL']}/v1/messages", json=body, timeout=40, headers=headers)
        except requests.RequestException as e:
            if last:
                raise ProviderError(f"Claude: {e}") from e
            log.warning("Claude call failed (%s); retrying", e)
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code in RETRY_STATUSES and not last:
            wait = min(float(r.headers.get("retry-after") or 1.5 * (attempt + 1)), 8)
            log.warning("Claude HTTP %s; retrying in %.1fs", r.status_code, wait)
            time.sleep(wait)
            continue
        break
    if r.status_code >= 400:
        raise ProviderError(f"Claude: HTTP {r.status_code} {r.text[:300]}")
    text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ProviderError("Claude: no JSON in the answer")
    try:
        return json.loads(m.group(0))
    except ValueError as e:
        raise ProviderError("Claude: the answer wasn't valid JSON") from e
