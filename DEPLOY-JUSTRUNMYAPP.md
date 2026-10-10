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

## Tips

- Prefer deploying from **GitHub** (repo root = project folder with `main.py`).
- This app runs **Telegram polling** + a small web server; the host must allow a **long-running process**, not only a static site.
- Keep persistent storage for `/app/data` or `./data` so SQLite is not wiped on restart.

Built with [BrainDaemon](https://braindaemon.com)
