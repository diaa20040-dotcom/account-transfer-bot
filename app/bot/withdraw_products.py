WITHDRAW_PRODUCTS = {
    "ray_01": {
        "cost": 12,
        "title_ar": "💵 0.1$ — راي دفع",
        "title_en": "💵 $0.10 — RAY pay",
        "prompt_key": "withdraw_prompt_ray",
        "short_key": "withdraw_ray_short",
        "admin_field_ar": "بيانات راي دفع",
        "admin_field_en": "RAY details",
    },
    "link_005": {
        "cost": 6,
        "title_ar": "🔗 0.05$ — رابط دفع",
        "title_en": "🔗 $0.05 — payment link",
        "prompt_key": "withdraw_prompt_link",
        "short_key": "withdraw_link_short",
        "admin_field_ar": "رابط الدفع",
        "admin_field_en": "Payment link",
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


def product_prompt_key(key: str) -> str:
    p = WITHDRAW_PRODUCTS.get(key)
    return (p or {}).get("prompt_key") or "withdraw_prompt_link"


def product_short_key(key: str) -> str:
    p = WITHDRAW_PRODUCTS.get(key)
    return (p or {}).get("short_key") or "withdraw_link_short"


def product_admin_field(key: str, lang: str = "ar") -> str:
    p = WITHDRAW_PRODUCTS.get(key)
    if not p:
        return "—"
    return p["admin_field_ar"] if lang == "ar" else p["admin_field_en"]
