# المرحلة 1 — تجهيز وربط Supabase وNeon وCloudinary وGemini

اقرأ البرومبت المستمر وملفات المشروع أولًا. لا تعِد إنشاء المشروع.

## الهدف
إعداد environment configuration وفحوص اتصال حقيقية وآمنة لكل مزود، مع إبقاء الخدمات مستقلة.

## الخطوات
1. راجع `.env.example` وschema الإعدادات الحالية؛ امنع قيم placeholder من أن تُعامل كأنها credentials صحيحة.
2. أضف إعدادات typed/validated في backend باستخدام المكتبة المعتمدة بالمشروع.
3. أضف فحوصًا منفصلة:
   - Supabase: تحقق من الإعدادات وJWKS discovery أو فحص metadata آمن؛ لا تعتبر نجاح HTTP وحده مصادقة مستخدم.
   - Neon: افتح اتصال PostgreSQL بسيطًا ونفّذ `SELECT 1` باستخدام pool/connection management مناسب.
   - Cloudinary: نفّذ فحص credentials بطريقة موثقة أو تحققًا آمنًا متاحًا؛ لا ترفع ملفًا تجريبيًا دون إذن.
   - Gemini: استخدم طلبًا minimal موثقًا على model مدعوم حاليًا، واحترم quota. لا تسجل request headers أو المفتاح.
4. اجعل `/health/ready` يعرض اسم الخدمة والحالة (`configured`, `connected`, `not_configured`, `error`) ورسالة عامة غير حساسة. لا يعرض host كاملًا أو connection string.
5. أضف timeout وerror handling وtests للمزودات باستخدام mocks. اختبارات CI لا تعتمد على مفاتيح حقيقية.
6. تحقق من `.gitignore` ومن أن `.env` غير متتبع بواسطة Git.
7. اكتب قائمة القيم الناقصة بأسماء environment variables فقط.

## قيود
- لا تستخدم Supabase Database؛ Neon هو التطبيق DB.
- Supabase Auth هو مزود الهوية فقط.
- لا تستخدم Cloudinary API secret من المتصفح.
- Gemini يستدعى من backend فقط.
- لا تنشئ نظامًا يبدّل بين مفاتيح عدة بغرض تجاوز حصص المزود.
- لا تخترع أسماء موديلات؛ تحقق من وثائق Gemini الحالية، وسجّل model ID المستخدم في config.
- لا تكتب القيم الحقيقية في التقرير.

## القبول
- config validation tests ناجحة.
- كل health check يعطي نتيجة صادقة.
- الاتصال بـ Neon ينجح إذا كانت DATABASE_URL صحيحة.
- اختبارات mock للمزودات ناجحة.
- الوثائق تشرح إعداد كل متغير.
- تحديث `PROJECT_STATUS.md` مع النتائج.
