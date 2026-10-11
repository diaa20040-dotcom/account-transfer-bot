# استضافة البوت مع قاعدة بيانات دائمة (Neon + Render)

SQLite على Render **تُمسح** عند إعادة تشغيل السيرفر. الحل: **PostgreSQL** على [Neon](https://neon.tech) (خطة مجانية) + نفس استضافة Render للبوت.

## 1) إنشاء قاعدة على Neon

1. سجّل على https://neon.tech (مجاني).
2. **New Project** → اختر اسمًا → المنطقة الأقرب لك.
3. من لوحة المشروع افتح **Connection details**.
4. انسخ **Connection string** (يفضّل **Pooled** إن وُجد).
   - يبدأ عادة بـ `postgresql://...` أو `postgres://...`
   - البوت يدعم الاثنين تلقائيًا.

## 2) ربط Render

1. افتح خدمة البوت على Render → **Environment**.
2. عدّل أو أضف:
   - **`DATABASE_URL`** = الصق رابط Neon كامل (سطر واحد).
3. احفظ → **Manual Deploy** → Deploy latest commit.

## 3) التحقق

بعد ما يصبح الخدمة **Live**، افتح في المتصفح:

`https://account-transfer-bot.onrender.com/health`

يجب أن ترى `"database": "postgres"`.

إذا **ما** ظهر حقل `database` أو كان `sqlite` → راجع `DATABASE_URL` ثم **Manual Deploy** لآخر commit على `main`.

## 4) أول تشغيل على Postgres

- إذا القاعدة **فاضية**، البوت يستورد تلقائيًا من `startup_seed.json` على GitHub (مرة واحدة).
- أو من الإدارة: **♻️ جلب من GitHub**.

بعدها **النقاط والأسعار والطلبات تبقى** حتى مع Redeploy.

## 5) متغيرات مهمة على Render

| المتغير | مطلوب |
|---------|--------|
| `BOT_TOKEN` | نعم |
| `DATABASE_URL` | نعم (Neon) |
| `ADMIN_IDS` | نعم |
| `GITHUB_BACKUP_TOKEN` | اختياري (نسخة احتياطية على GitHub) |

## 6) لو الـ Deploy فشل بعد ربط Postgres

- من **Neon** → مشروع **Qiest** → **Branches** → **production** → **Reset data** (أو أنشئ branch جديد).
- على Render: **Manual Deploy** لآخر commit على `main`.
- في `DATABASE_URL` شيل `&channel_binding=require` لو ظهر خطأ اتصال.

## 7) لا ترجع لـ SQLite على Render

لا تضع `sqlite://...` في `DATABASE_URL` على السحابة — ستعود مشكلة اختفاء البيانات.

---

Built with [BrainDaemon](https://braindaemon.com)
