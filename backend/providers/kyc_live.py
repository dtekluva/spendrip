"""
Live identity checks, read by Claude:
- ID photo: document type, name, date of birth, expiry, number; refused if unreadable, expired, edited or a screen.
- Liveness: three photos in a shuffled order (looking straight, head turned one way, then the other). Each must be one
  clear, live-looking face in the asked pose, and the two turns must go opposite ways. A still photo can't do that.
  This doesn't compare the face with the ID photo, and Claude is never asked who the person is.
"""
from __future__ import annotations

from datetime import date

from .claude import vision_json

DOC_PROMPT = """You are checking a photo submitted as a Nigerian identity document (NIN slip or card, driver's licence,
voter's card or international passport). Read it and answer with ONLY a JSON object, no other text:
{"is_identity_document": bool, "document_type": "nin"|"drivers_licence"|"voters_card"|"passport"|"other",
 "readable": bool, "surname": str, "given_names": str, "date_of_birth": "YYYY-MM-DD" or "",
 "document_number": str, "expiry_date": "YYYY-MM-DD" or "", "looks_edited_or_screen": bool,
 "quality_issues": [str]}
Use empty strings for anything you can't read. "looks_edited_or_screen" is true if it seems to be a photo of a screen,
a photocopy, or digitally altered. Do not guess."""

POSE_PROMPT = """This photo is one step of a liveness check, where a person turns their head on request.
Do not identify the person or describe who they are. Only judge the photo. Answer with ONLY a JSON object, no other text:
{"faces": int, "face_clear": bool, "looks_live": bool, "direction": "front"|"towards_image_left"|"towards_image_right"|"other"}
"faces": how many human faces are visible. "face_clear": one face is in focus, well lit and not covered (no sunglasses or mask).
"looks_live": false if it looks like a photo of a screen, a printed picture or an ID card.
"direction": where the nose points: "front" if looking at the camera, "towards_image_left" / "towards_image_right" if the head is
turned (about 20 degrees or more, so one cheek is clearly more visible than the other) towards that side of the image,
otherwise "other"."""

ALLOWED_DOCS = {"nin", "drivers_licence", "voters_card", "passport"}
STEP_WORDS = {"front": "looking straight at the camera", "left": "turned to your left", "right": "turned to your right"}


class LiveKycProvider:
    name = "live"
    mode = "live"

    def __init__(self, paystack_client_factory=None):
        self._make_ps = paystack_client_factory  # kept for future provider checks; not used by ID + liveness

    def check_document(self, image_bytes: bytes, *, id_type: str, **_) -> dict:
        r = vision_json(DOC_PROMPT, image_bytes)
        number = str(r.get("document_number") or "")
        out = {"passed": False, "document_type": r.get("document_type", ""), "date_of_birth": r.get("date_of_birth", ""),
               "expiry_date": r.get("expiry_date", ""), "number_last4": number[-4:], "document_number": number,
               "surname": r.get("surname", ""), "given_names": r.get("given_names", ""),
               "quality_issues": r.get("quality_issues") or [], "checks": []}
        if not r.get("is_identity_document") or r.get("document_type") not in ALLOWED_DOCS:
            return {**out, "message": "That doesn't look like a NIN slip, driver's licence, voter's card or passport. Try again with the front of your ID."}
        if not r.get("readable") or not (r.get("surname") and r.get("given_names")):
            return {**out, "message": "We couldn't read the name on that ID. Lay it flat in good light with all four corners showing."}
        if r.get("looks_edited_or_screen"):
            return {**out, "message": "Please take a photo of the ID itself, not a screen or a photocopy."}
        exp = r.get("expiry_date") or ""
        try:
            if exp and date.fromisoformat(exp) < date.today():
                return {**out, "message": "This ID has expired. Use a current one."}
        except ValueError:
            pass
        return {**out, "passed": True, "checks": ["document_readable", "not_expired", "not_a_screen"]}

    def check_liveness(self, images: list[bytes], order: list[str]) -> dict:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(images)) as pool:  # side by side, so the person waits for one check, not three
            reads = list(pool.map(lambda img: vision_json(POSE_PROMPT, img, max_tokens=200), images))
        steps = []
        for i, (pose, r) in enumerate(zip(order, reads), start=1):
            step = {"pose": pose, "faces": r.get("faces"), "face_clear": r.get("face_clear"), "looks_live": r.get("looks_live"),
                    "direction": r.get("direction")}
            steps.append(step)
            if r.get("faces") != 1:
                return {"passed": False, "steps": steps, "message": f"Photo {i}: we need just your face in the photo."}
            if not r.get("face_clear"):
                return {"passed": False, "steps": steps, "message": f"Photo {i}: we couldn't see your face clearly. Try again in good light."}
            if not r.get("looks_live"):
                return {"passed": False, "steps": steps, "message": "Take the photos of yourself live, not of a screen or a printed picture."}
            wants_front = pose == "front"
            if wants_front != (r.get("direction") == "front") or (not wants_front and r.get("direction") == "other"):
                if not wants_front and r.get("direction") == "front":
                    return {"passed": False, "steps": steps,
                            "message": f"Photo {i}: turn your head further to your {pose}, until we can see your ear. Let's try again."}
                return {"passed": False, "steps": steps, "message": f"Photo {i} should be {STEP_WORDS[pose]}. Let's try again."}
        turns = [s["direction"] for s in steps if s["pose"] != "front"]
        if len(set(turns)) != 2:
            return {"passed": False, "steps": steps, "message": "Turn your head one way, then the other way. Let's try again."}
        return {"passed": True, "steps": steps, "face_match": "not_checked"}
