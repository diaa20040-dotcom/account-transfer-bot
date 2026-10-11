"""Push / pull startup_seed.json via GitHub API so Render restarts recover live data."""

import base64
import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

SEED_PATH = "data/startup_seed.json"
_last_push_monotonic = 0.0
_PUSH_MIN_INTERVAL_SEC = 45.0


def _token() -> str:
    return (settings.github_backup_token or "").strip()


def _repo() -> str:
    repo = (settings.github_repo or "").strip()
    if repo and "/" in repo:
        return repo
    return ""


def github_backup_configured() -> bool:
    return bool(_token() and _repo())


def fetch_seed_from_github() -> dict[str, Any] | None:
    if not github_backup_configured():
        return None
    owner, name = _repo().split("/", 1)
    url = f"https://api.github.com/repos/{owner}/{name}/contents/{SEED_PATH}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content_b64 = data.get("content", "")
        if data.get("encoding") == "base64":
            raw = base64.b64decode(content_b64)
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            logger.warning("GitHub fetch seed HTTP %s", exc.code)
    except Exception:
        logger.exception("GitHub fetch seed failed")
    return None


def push_seed_to_github(payload: dict[str, Any], force: bool = False) -> bool:
    global _last_push_monotonic
    if not github_backup_configured():
        return False
    now = time.monotonic()
    if not force and now - _last_push_monotonic < _PUSH_MIN_INTERVAL_SEC:
        return False
    owner, name = _repo().split("/", 1)
    url = f"https://api.github.com/repos/{owner}/{name}/contents/{SEED_PATH}"
    body_text = json.dumps(payload, ensure_ascii=False, indent=2)
    body_b64 = base64.b64encode(body_text.encode("utf-8")).decode("ascii")

    sha: str | None = None
    try:
        get_req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {_token()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(get_req, timeout=25) as resp:
            existing = json.loads(resp.read().decode("utf-8"))
            sha = existing.get("sha")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            logger.warning("GitHub get sha HTTP %s", exc.code)
            return False
    except Exception:
        logger.exception("GitHub get sha failed")
        return False

    put_body = {
        "message": "chore: auto backup bot data",
        "content": body_b64,
        "committer": {
            "name": "BrainDaemon",
            "email": "built-with@braindaemon.com",
        },
    }
    if sha:
        put_body["sha"] = sha

    put_req = urllib.request.Request(
        url,
        data=json.dumps(put_body).encode("utf-8"),
        method="PUT",
        headers={
            "Authorization": f"Bearer {_token()}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(put_req, timeout=30) as resp:
            if 200 <= resp.status < 300:
                _last_push_monotonic = now
                logger.info("GitHub seed backup pushed (%s users)", len(payload.get("users") or []))
                return True
    except Exception:
        logger.exception("GitHub push seed failed")
    return False
