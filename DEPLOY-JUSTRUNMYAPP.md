# Deploy on JustRunMyApp / Runny

## Start command

```bash
python3 main.py
```

(or `bash start.sh`)

## Required environment variables

| Variable | Example / notes |
|----------|-----------------|
| `BOT_TOKEN` | From @BotFather |
| `ADMIN_IDS` | Your Telegram numeric ID, e.g. `8823377492` |
| `DATABASE_URL` | `sqlite:////app/data/bot.db` (Docker) or `sqlite:///./data/bot.db` |
| `ADMIN_PASSWORD` | Strong password for web admin |
| `SECRET_KEY` | Long random string for sessions |
| `ADMIN_TELEGRAM_USERNAMES` | `Diaoeldeen` (optional, for bot admin panel) |
| `PORT` | Set automatically on most hosts (default `8765`) |

## Health check

HTTP `GET /health` → `{"status":"ok"}`

## If build fails with exit **137** (OOM)

The free tier has little RAM. Use:

| Variable | Value |
|----------|--------|
| `ENABLE_WEB_ADMIN` | `false` (bot + `/health` only; manage via `/admin` in Telegram) |
| `SKIP_PIP_ON_START` | `1` (do not run `pip install` on every boot) |

Start command: `python3 main.py` (not `bash start.sh` unless you need install).

## Tips

- Prefer deploying from **GitHub** (repo root = project folder with `main.py`).
- This app runs **Telegram polling** + a small web server; the host must allow a **long-running process**, not only a static site.
- Keep persistent storage for `/app/data` or `./data` so SQLite is not wiped on restart.
- Upload **without** `.venv` folder (use the GitHub zip, not a folder copied from your PC with venv inside).

Built with [BrainDaemon](https://braindaemon.com)
