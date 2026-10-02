"""
Live identity checks:
- BVN: Paystack's customer validation, which confirms a BVN belongs to the person's own bank account
  and matches their name. The answer arrives by webhook (customeridentification.success / .failed).
- ID photo: Claude reads the document; we check it's readable, not expired, and the name matches.
- Selfie: Claude only checks it's one clear, real-looking face. No face matching or identification.
"""
from __future__ import annotations

import re
from datetime import date

from .banks import BY_NIP
from .base import ProviderError
from .claude import vision_json

DOC_PROMPT = """You are checking a photo submitted as a Nigerian identity document (NIN slip or card, driver's licence,
voter's card or international passport). Read it and answer with ONLY a JSON object, no other text:
{"is_identity_document": bool, "document_type": "nin"|"drivers_licence"|"voters_card"|"passport"|"other",
 "readable": bool, "surname": str, "given_names": str, "date_of_birth": "YYYY-MM-DD" or "",
 "document_number": str, "expiry_date": "YYYY-MM-DD" or "", "looks_edited_or_screen": bool,
 "quality_issues": [str]}
Use empty strings for anything you can't read. "looks_edited_or_screen" is true if it seems to be a photo of a screen,
a photocopy, or digitally altered. Do not guess."""

SELFIE_PROMPT = """This photo was taken as a selfie for an account check. Do not identify the person or describe who they are.
Only judge the photo. Answer with ONLY a JSON object, no other text:
{"faces": int, "face_clear": bool, "looks_live": bool, "issues": [str]}
"faces" is how many human faces are visible. "face_clear" is true if one face is in focus, well lit and not covered
(no sunglasses, mask or cap shadow). "looks_live" is false if it looks like a photo of a screen, a printed picture or an ID card."""

ALLOWED_DOCS = {"nin", "drivers_licence", "voters_card", "passport"}


def _tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^a-z]+", name.lower()) if len(t) > 1}


def names_match(expected_first: str, expected_last: str, read: str) -> bool:
    """The surname must appear, plus at least one given name. Tolerates order and middle names."""
    got = _tokens(read)
    last = _tokens(expected_last)
    first = _tokens(expected_first)
    return bool(last & got) and bool(first & got) if first else bool(last & got)


class LiveKycProvider:
    name = "live"
    mode = "live"

    def __init__(self, paystack_client_factory):
        self._make_ps, self._ps = paystack_client_factory, None

    @property
    def ps(self):
        if self._ps is None:
            self._ps = self._make_ps()  # only when a BVN check actually needs Paystack
        return self._ps

    # ---------- BVN via Paystack ----------
    def ensure_customer(self, *, email, first_name, last_name, phone="") -> str:
        status, body = self.ps.call("POST", "/customer", json={"email": email, "first_name": first_name, "last_name": last_name,
                                                                "phone": phone})
        code = (body.get("data") or {}).get("customer_code")
        if status >= 400 or not code:
            raise ProviderError(f"Paystack couldn't set up the customer: {body.get('message', '')}")
        return code

    def start_bvn_check(self, *, customer_code, bvn, first_name, last_name, nip_bank_code, account_number) -> None:
        bank = BY_NIP.get(nip_bank_code)
        if not bank or not bank[1]:
            raise ValueError("We can't check accounts at this bank yet. Choose another bank.")
        status, body = self.ps.call("POST", f"/customer/{customer_code}/identification", json={
            "country": "NG", "type": "bank_account", "account_number": account_number, "bvn": bvn, "bank_code": bank[1],
            "first_name": first_name, "last_name": last_name})
        if status >= 400:
            raise ValueError(body.get("message") or "Paystack couldn't start the BVN check.")

    # ---------- ID photo ----------
    def check_document(self, image_bytes: bytes, *, id_type: str, expected_first: str, expected_last: str) -> dict:
        r = vision_json(DOC_PROMPT, image_bytes)
        number = str(r.get("document_number") or "")
        out = {"passed": False, "document_type": r.get("document_type", ""), "date_of_birth": r.get("date_of_birth", ""),
               "expiry_date": r.get("expiry_date", ""), "number_last4": number[-4:], "name_read": f"{r.get('given_names', '')} {r.get('surname', '')}".strip(),
               "quality_issues": r.get("quality_issues") or [], "checks": []}
        if not r.get("is_identity_document") or r.get("document_type") not in ALLOWED_DOCS:
            return {**out, "message": "That doesn't look like a NIN slip, driver's licence, voter's card or passport. Try again with the front of your ID."}
        if not r.get("readable"):
            return {**out, "message": "We couldn't read that ID. Lay it flat in good light with all four corners showing."}
        if r.get("looks_edited_or_screen"):
            return {**out, "message": "Please take a photo of the ID itself, not a screen or a photocopy."}
        exp = r.get("expiry_date") or ""
        try:
            if exp and date.fromisoformat(exp) < date.today():
                return {**out, "message": "This ID has expired. Use a current one."}
        except ValueError:
            pass
        if not names_match(expected_first, expected_last, out["name_read"]):
            return {**out, "message": f"The name on this ID doesn't match {expected_first} {expected_last} from your BVN. Use your own ID."}
        return {**out, "passed": True, "checks": ["document_readable", "not_expired", "name_matches"]}

    # ---------- selfie ----------
    def match_selfie(self, image_bytes: bytes) -> dict:
        r = vision_json(SELFIE_PROMPT, image_bytes, max_tokens=300)
        ok = r.get("faces") == 1 and bool(r.get("face_clear")) and bool(r.get("looks_live"))
        msg = "" if ok else ("Take a selfie with just you in it." if (r.get("faces") or 0) > 1 else
                             "We couldn't see your face clearly. Try again in good light, looking straight at the camera.")
        return {"passed": ok, "faces": r.get("faces"), "face_clear": r.get("face_clear"), "looks_live": r.get("looks_live"),
                "issues": r.get("issues") or [], "message": msg, "face_match": "not_checked"}
