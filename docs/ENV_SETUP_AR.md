# إعداد ملفات البيئة

1. انسخ `frontend/.env.local.example` إلى `frontend/.env.local`.
2. انسخ `backend/.env.example` إلى `backend/.env`.
3. أدخل القيم الحقيقية من لوحات مزودي الخدمة.
4. اترك المتغيرات الاختيارية غير مهيأة بدل وضع قيم وهمية تبدو حقيقية.
5. لا تشارك ملفات `.env` ولا ترفعها إلى Git.
6. بعد تغيير المتغيرات، أعد تشغيل خادم التطوير.
7. لا تشارك screenshots تحتوي مفاتيح أو connection strings.

تأكد أن:
- `NEXT_PUBLIC_*` يحتوي فقط قيمًا عامة مخصصة للعميل.
- `DATABASE_URL` و`CLOUDINARY_API_SECRET` و`GEMINI_API_KEY` server-side فقط.
- قيمة `SUPABASE_URL` هي URL المشروع الصحيح.
- connection string الخاصة بـ Neon تتطلب SSL وفق إعداد المزود.
