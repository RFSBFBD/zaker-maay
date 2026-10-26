# دليل التشغيل وحل الأعطال

## تشغيل API محليًا

من PowerShell داخل `D:\ai_study\backend`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

إذا لم توجد البيئة الافتراضية:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## تشغيل الواجهة

من PowerShell داخل `D:\ai_study\frontend`:

```powershell
npm ci
npm run dev
```

افتح `http://localhost:3000`. Next يمرر `/api/v1/*` إلى FastAPI باستخدام `API_PROXY_TARGET`، والافتراضي `http://127.0.0.1:8001`. عند تغيير عنوان الـ API، عيّن هذا المتغير في بيئة عملية Next ثم أعد تشغيلها. لا تضع أسرار الخادم في `NEXT_PUBLIC_*`.

## فحص الاتصالات

من `backend/`:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_connections
```

الفحص الآمن يطبع حالة الخدمة فقط. لا تستخدم `Get-Content .env` ولا تنسخ أي قيمة سرية إلى سجل أو محادثة. `/health/live` يختبر عملية API فقط. `/health/ready` يوضح الإعدادات، وقد يظهر `configured_unchecked` لأن endpoint لا يجري اتصالًا مكلفًا مع كل طلب؛ فاحص الاتصالات هو اختبار المزود المنفصل.

## قاعدة البيانات والترحيلات

للتطوير فقط، وبعد اختيار قاعدة غير إنتاجية:

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade neon_existing_schema@head
```

لا تستخدم `alembic upgrade head` بسبب وجود تاريخين. افحص أسماء الفروع قبل أي ترحيل. لا تنفذ SQL حذف أو ترقية دور مستخدم مباشرة. أي ترحيل على قاعدة production يجب اختباره على فرع مؤقت ثم أخذ موافقة المالك قبل التطبيق.

## CORS وNext

- الأصل المعتمد حاليًا في Next dev هو `172.16.0.2` فقط، إضافة إلى localhost حسب `allowedDevOrigins`.
- API المباشر يطبق `CORS_ORIGINS` من البيئة عند بدء التشغيل؛ تعديل `.env` لا يغير middleware داخل عملية قائمة.
- واجهة Next تتصل عبر نفس الأصل والـ rewrite. إذا احتجت API مباشرًا، أعد تشغيل العملية المالكة وتأكد أن الأصول المحلية المطلوبة موجودة في allowlist.
- لا توقف PID مجهولًا. تحقق أولًا من اسم ومسار البرنامج. إذا لم تسمح الصلاحيات بقراءته، استخدم الطرفية/مدير العمليات الذي بدأ الخدمة.

## تسجيل الدخول والمحتوى

- اضبط Redirect URLs في Supabase لتطابق المضيف الذي يستخدمه المتصفح مثل `http://localhost:3000/auth/callback`.
- جميع الحسابات الجديدة تبدأ بدور student. أول admin لا يُعيّن من المتصفح؛ على مالك المشروع وضع سياسة bootstrap موثوقة ومحددة.
- ظهور صفحة مواد فارغة يعني غالبًا أنه لا توجد subjects أو عضوية لهذا الحساب في Neon. أضف محتوى حقيقيًا وmembership من إجراء إداري موثق؛ لا تنشئ بيانات نموذجية في قاعدة المستخدم.

## التعامل مع الميزات

- الصوت: الإرسال إلى Gemini يتطلب اختيار المربع الصريح في كل عملية رفع؛ الصيغ/الحجم/المدة لها حدود في الخادم. لا تُخترع timestamps.
- فشل Gemini: تظهر رسالة آمنة؛ لا يحفظ التطبيق مخرجات وهمية. أعد المحاولة بعد التحقق من الاتصال والحصة.
- Cloudinary: اختبارات CI تستخدم mock ولا ترفع ملفًا تجريبيًا إلى حساب حقيقي. الرفع الحقيقي يتطلب ملفًا اختاره المستخدم ويملك حق استخدامه.
- اختبار API: `backend/.venv/Scripts/python.exe -m pytest -q`.
- فحوص frontend: `npm run lint`, `npm run typecheck`, `npm run build`.

