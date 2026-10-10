"""Resolved Telegram admin IDs (from env IDs + usernames)."""

_resolved_admin_ids: list[int] = []


def set_admin_ids(ids: list[int]) -> None:
    global _resolved_admin_ids
    _resolved_admin_ids = list(dict.fromkeys(ids))


def get_admin_ids() -> list[int]:
    return list(_resolved_admin_ids)


def add_admin_id(telegram_id: int) -> None:
    if telegram_id not in _resolved_admin_ids:
        _resolved_admin_ids.append(telegram_id)
