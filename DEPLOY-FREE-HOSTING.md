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

**تنبيه:** الخطة المجانية على Render قد **تنام** بعد فترة بدون طلبات. البوت يستخدم **Webhook** تلقائياً عندما يكون `RENDER_EXTERNAL_URL` موجوداً (Render يضيفه بنفسه) — أي رسالة من تيليجرام تُوقِظ السيرفر وتصل فوراً. أول رد بعد نوم طويل قد يتأخر **30–60 ثانية** (إقلاع الحاوية).

إذا ظهر **Deployed** لكن البوت لا يرد: من Render → الخدمة → **Manual Deploy** → **Clear build cache & deploy**، ثم راقب **Logs** لسطر `Webhook mode:`.

**قاعدة البيانات (مهم):** على Render المجاني ملف SQLite **يُمسح مع كل Deploy** — الرصيد والطلبات تروح.

### الحل الدائم — PostgreSQL مجاني (Neon) ⭐

1. سجّل على [neon.tech](https://neon.tech) (مجاني).
2. أنشئ مشروع → انسخ **Connection string** (مثل `postgresql://user:pass@.../neondb?sslmode=require`).
3. في Render → الخدمة → **Environment** → أضف:
   - `DATABASE_URL` = نفس الرابط (يبدأ بـ `postgresql://`)
4. **Deploy latest** مرة واحدة.

البوت يدعم PostgreSQL تلقائياً — بعدها النشر ما يمسح البيانات.

**بدون Neon:** قبل كل Deploy: `/admin` → **📥 نسخة احتياطية** — وبعد النشر **📤 استعادة نسخة**.

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

## تحديث الكود بدون خسارة البيانات

1. من البوت: `/admin` → **📥 نسخة احتياطية** — احفظ ملف JSON على تليفونك.
2. على Render: **Manual Deploy** → **Deploy latest commit** (تجنب *Clear build cache* إلا لو في مشكلة).
3. لو الرصيد أو المستخدمين اختفوا بعد النشر: `/admin` → **📤 استعادة نسخة** وأرسل نفس الملف.

**Restart service** فقط = آمن، البيانات تفضل. **Deploy** على المجاني قد يمسح SQLite أحياناً — النسخة الاحتياطية تحميك.

## بعد النشر

- جرّب `/start` و `/admin`
- فعّل **Stars** في BotFather للشحن
- البوت **أدمن** في قناة الاشتراك الإجباري

Built with [BrainDaemon](https://braindaemon.com)
