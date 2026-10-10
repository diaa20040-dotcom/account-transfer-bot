from app.services.promo import normalize_promo_code


def test_normalize_promo_code():
    assert normalize_promo_code("  welcome50 ") == "WELCOME50"
    assert normalize_promo_code("a b") == "AB"
