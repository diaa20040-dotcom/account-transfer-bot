WITHDRAW_PRODUCTS = {
    "ray_01": {
        "cost": 12,
        "title_ar": "سحب 0.1$ — راي دفع",
        "title_en": "Withdraw $0.10 — RAY pay",
    },
    "link_005": {
        "cost": 6,
        "title_ar": "سحب 0.05$ — رابط دفع",
        "title_en": "Withdraw $0.05 — payment link",
    },
}


def product_title(key: str, lang: str) -> str:
    p = WITHDRAW_PRODUCTS.get(key)
    if not p:
        return key
    return p["title_ar"] if lang == "ar" else p["title_en"]


def product_cost(key: str) -> int:
    p = WITHDRAW_PRODUCTS.get(key)
    return int(p["cost"]) if p else 0
