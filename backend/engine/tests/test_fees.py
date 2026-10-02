from engine import FeeSchedule


def test_paystack_tiers_and_stamp_duty():
    f = FeeSchedule()
    def lines(naira):
        p = f.parts(naira * 100)
        return p.service_kobo // 100, p.provider_kobo // 100, p.stamp_duty_kobo // 100, p.total_kobo // 100
    assert lines(3_000) == (50, 10, 0, 60)
    assert lines(5_000) == (50, 10, 0, 60)
    assert lines(5_001) == (50, 25, 0, 75)
    assert lines(9_999) == (50, 25, 0, 75)
    assert lines(10_000) == (50, 25, 50, 125)
    assert lines(50_000) == (50, 25, 50, 125)
    assert lines(50_001) == (50, 50, 50, 150)


def test_lines_skip_zero_parts_and_keep_order():
    assert [l["kind"] for l in FeeSchedule().parts(300_000).lines()] == ["service", "provider"]
    assert [l["label"] for l in FeeSchedule().parts(3_000_000).lines()] == ["SpenDrip fee", "Transfer fee (Paystack)", "Stamp duty"]
