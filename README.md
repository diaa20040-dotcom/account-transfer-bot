# بوت الفيزا (Telegram)

بوت تليجرام مبسّط: **طلب فيزا** (15 نقطة أو 15 نجمة)، **الإحالات** (نقطة لكل إحالة مكتملة)، ولوحة إدارة في تيليجرام.

## للمستخدم

- **💳 طلب فيزا**: اختر الدفع بالنقاط أو بالنجوم → تُسلَّم فيزا عشوائية من المخزون فوراً (بدون تكرار).
- **📦 مخزون الفيز (إدارة)**: أضف الفيزات (واحدة لكل رسالة، أو عدة فيزات مفصولة بـ `---`).
- **👥 الإحالات**: رابط `t.me/BOT?start=ref_TELEGRAM_ID` — نقطة بعد اشتراك المُحال في القناة الإجبارية (إن وُجدت).
- **🌐 اللغة**: عربي / English.

## التشغيل

```bash
cd account-transfer-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# عدّل .env: BOT_TOKEN، ADMIN_TELEGRAM_IDS
python main.py
```

## الإدارة

من الخاص: زر **لوحة الإدارة** → طلبات الفيزا، مستخدمون، إحالة، إذاعة، اشتراك إجباري، نسخ احتياطي.

## الاستضافة

**Render + GitHub:** عبّئ `BOT_TOKEN` و`DATABASE_URL` (يفضّل Postgres) ثم Manual Deploy.

---

Built with [BrainDaemon](https://braindaemon.com)
