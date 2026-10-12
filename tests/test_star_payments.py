from app.services.star_payments import payment_kind_from_payload


def test_payment_kind_from_payload():
    assert payment_kind_from_payload("topup:1:50") == "topup"
    assert payment_kind_from_payload("runopen:1:10") == "run_open"
    assert payment_kind_from_payload("playpass:2:20") == "play_pass"
