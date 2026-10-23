# بوت بيع النجوم (Telegram)

بوت بسيط: المستخدم يضغط **⭐ بيع نجوم**، يكتب الكمية، يدفع بالنجوم عبر تيليجرام، وتصل **إشعار للإدارة** بمعرّف المستخدم واسمه للتواصل وتحويل المبلغ.

## للمستخدم

1. **⭐ بيع نجوم**
2. أرسل عدد النجوم (1–10000)
3. ادفع من فاتورة تيليجرام
4. انتظر تواصل الإدارة (@Diaoeldeen افتراضياً)

## للإدارة

تصل رسالة خاصة لكل دفع: الكمية + `telegram_id` + `@username` + الاسم.

تأكد أن `ADMIN_TELEGRAM_IDS` أو `ADMIN_USERNAMES` يشمل حسابك على Render.

## التشغيل

```bash
pip install -r requirements.txt
cp .env.example .env
# BOT_TOKEN + ADMIN_IDS
python main.py
```

---

Built with [BrainDaemon](https://braindaemon.com)
