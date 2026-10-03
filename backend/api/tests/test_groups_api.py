"""Group plans through the API: create, preview, edit people and one-off changes, and Activity."""
import pytest

from api.tests.test_api import demo, dev, unlocked_client  # noqa: F401  (fixtures)
from drips.models import Plan, Recipient


def people(demo, n=3):
    out = list(demo.recipients.all()[:n])
    for i in range(len(out), n):
        out.append(Recipient.objects.create(user=demo, label=f"Staff {i}", bank_name="GTBank", nip_bank_code="000013",
                                            account_number=f"012345678{i}", verified_account_name=f"STAFF {i}"))
    return out


def group_body(demo, amounts=(4_000_000, 3_000_000, 2_500_000), **kw):
    return {"kind": "group", "label": "Staff pay", "emoji": "👷", "tint": "sun", "frequency": "monthly", "month_day": 28,
            "time_local": "09:00", "lines": [{"recipient_id": r.id, "amount_kobo": a} for r, a in zip(people(demo, len(amounts)), amounts)], **kw}


def test_create_a_group_and_read_it_back(demo, dev):
    c = unlocked_client(demo)
    r = c.post("/api/plans", group_body(demo), format="json")
    assert r.status_code == 201, r.json()
    p = r.json()["plan"]
    assert p["kind"] == "group" and p["people"] == 3 and p["amount_kobo"] == 9_500_000 and p["recipient"] is None
    assert [ln["amount_kobo"] for ln in p["lines"]] == [4_000_000, 3_000_000, 2_500_000]
    assert p["next_payout"] == {"people": 3, "amount_kobo": 9_500_000, "fee_kobo": p["fee_kobo"], "changed": False}


@pytest.mark.parametrize("change, code_or_text", [
    (lambda b: b.update(lines=b["lines"][:1]), "2 to 50 people"),
    (lambda b: b["lines"].append(dict(b["lines"][0])), "duplicate_person"),
    (lambda b: b["lines"][1].update(amount_kobo=0), "between ₦100"),
    (lambda b: [ln.update(skip_next=True) for ln in b["lines"]], "all_skipped"),
])
def test_bad_group_lists_are_refused(demo, dev, change, code_or_text):
    body = group_body(demo)
    change(body)
    r = unlocked_client(demo).post("/api/plans", body, format="json")
    assert r.status_code == 400 and (r.json().get("code") == code_or_text or code_or_text in r.json()["error"])


def test_each_persons_amount_is_held_to_the_per_transfer_limit(demo, dev, settings):
    settings.SPENDRIP = {**settings.SPENDRIP, "KYC_PROVIDER": "live", "TIER1_MAX_DRIP_KOBO": 3_500_000}
    r = unlocked_client(demo).post("/api/plans", group_body(demo), format="json")
    assert r.status_code == 400 and r.json()["code"] == "over_limit"


def test_preview_shows_group_fees_once(demo, dev, settings):
    settings.SPENDRIP = {**settings.SPENDRIP, "STAMP_DUTY_KOBO": 5_000, "PASS_THROUGH_TRANSFER_FEES": True}
    p = unlocked_client(demo).post("/api/plans/preview", group_body(demo), format="json").json()
    lines = {ln["kind"]: ln["amount_kobo"] for ln in p["fee_lines"]}
    assert lines == {"service": 10_000, "provider": 7_500, "stamp_duty": 15_000}
    assert p["fee_kobo"] == 32_500


def test_one_off_change_and_skip_then_edit_people(demo, dev):
    c = unlocked_client(demo)
    plan = c.post("/api/plans", group_body(demo), format="json").json()["plan"]
    lines = [{"recipient_id": ln["recipient"]["id"], "amount_kobo": ln["amount_kobo"]} for ln in plan["lines"]]
    lines[0]["next_amount_kobo"] = 5_000_000  # bonus next time
    lines[2]["skip_next"] = True
    p = c.patch(f"/api/plans/{plan['id']}", {"lines": lines}, format="json").json()["plan"]
    assert p["amount_kobo"] == 9_500_000  # the regular amount is unchanged
    assert p["next_payout"]["changed"] and p["next_payout"]["people"] == 2 and p["next_payout"]["amount_kobo"] == 8_000_000

    p = c.patch(f"/api/plans/{plan['id']}", {"lines": lines[:2]}, format="json").json()["plan"]  # remove the third person
    assert p["people"] == 2 and p["amount_kobo"] == 7_000_000
    assert Plan.objects.get(pk=plan["id"]).lines.filter(active=False).count() == 1  # kept for history


def test_a_person_on_a_group_cannot_be_deleted(demo, dev):
    c = unlocked_client(demo)
    c.post("/api/plans", group_body(demo), format="json")
    third = people(demo)[2]
    r = c.delete(f"/api/recipients/{third.id}")
    assert r.status_code == 409 and "Staff pay" in r.json()["error"]
