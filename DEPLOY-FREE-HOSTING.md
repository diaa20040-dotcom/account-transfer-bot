# استضافة مجانية / سهلة للبوت

## لا أستطيع تسجيل الدخول لحسابك

لا يمكن لأي مساعد فتح حسابك على Render أو Railway أو غيرها (خصوصية وأمان). التالي يأخذ **5–10 دقائق** منك مرة واحدة.

## البوت شغال الآن (مؤقت)

على سيرفر التطوير لهذا المشروع — **ليس استضافة 24/7 دائمة**. للتشغيل الدائم استخدم أحد الخيارات تحت.

---

## الخيار 1 — Render (الأسهل — من GitHub بنقرة) ⭐

### رابط سريع (Deploy Blueprint)

1. افتح (من الموبايل أو الكمبيوتر، بعد تسجيل الدخول في Render بحساب GitHub):

   **https://render.com/deploy?repo=https://github.com/diaa20040-dotcom/account-transfer-bot**

2. Render يقرأ ملف `render.yaml` تلقائياً.
3. عند الطلب، أضف **Environment Variables** (Secret) ثم **Apply**:

### أو يدوياً

1. سجّل مجاناً على [render.com](https://render.com) (بحساب GitHub).
2. **New** → **Blueprint** → اختر مستودع `account-transfer-bot`.
3. أضف **Environment Variables** (Secret):
   - `BOT_TOKEN` — من BotFather
   - `ADMIN_IDS` — رقم تيليجرام (مثل `8823377492`)
   - `ADMIN_TELEGRAM_USERNAMES` — `Diaoeldeen`
   - `ADMIN_PASSWORD` — باسورد قوي
   - `SECRET_KEY` — نص عشوائي طويل
4. **Deploy**.

ملف `render.yaml` جاهز في المستودع.

**تنبيه:** الخطة المجانية على Render قد **تنام** بعد فترة بدون طلبات — البوت قد يتأخر في الرد. للتشغيل الدائم استخدم خطة مدفوعة صغيرة أو VPS.

**قاعدة البيانات:** `sqlite` على Render قد **تُمسح** عند إعادة النشر على المجاني. للإنتاج استخدم لاحقاً Postgres مجاني (Neon) وغيّر `DATABASE_URL`.

---

## الخيار 2 — VPS رخيص (~4–5$/شهر)

أنسب للبوت + SQLite + تشغيل 24/7:

```bash
git clone https://github.com/diaa20040-dotcom/account-transfer-bot.git
cd account-transfer-bot
cp .env.example .env
# عدّل .env
docker build -t transfer-bot .
docker run -d --restart unless-stopped -p 8765:8765 --env-file .env -v botdata:/app/data transfer-bot
```

---

## JustRunMyApp

فشل سابقاً (خطأ **137** = ذاكرة قليلة). لا يُنصح به لهذا البوت إلا بخطة أعلى RAM.

---

## بعد النشر

- جرّب `/start` و `/admin`
- فعّل **Stars** في BotFather للشحن
- البوت **أدمن** في قناة الاشتراك الإجباري

Built with [BrainDaemon](https://braindaemon.com)
