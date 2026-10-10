from app.i18n import t


def test_ar_welcome():
    msg = t("ar", "welcome", name="Ali", points=10)
    assert "Ali" in msg and "10" in msg


def test_en_button():
    assert "Start transfer" in t("en", "btn_transfer")
