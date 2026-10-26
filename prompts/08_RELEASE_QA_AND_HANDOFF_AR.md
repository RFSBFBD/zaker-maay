# المرحلة 7 — QA والتشغيل والتسليم

لا تعلن الجاهزية لمجرد أن التطبيق يفتح في المتصفح.

## 1. تشغيل نظيف
- اتبع README من بيئة نظيفة قدر الإمكان.
- أعد إنشاء البيئة الافتراضية وتثبيت dependencies من lockfiles.
- تحقق من أن `.env` غير tracked وأن ملفات الأمثلة لا تحتوي secrets حقيقية.
- شغّل migrations على قاعدة اختبار/تطوير، لا على قاعدة إنتاج دون موافقة.

## 2. الاختبارات
Backend:
- unit tests.
- integration tests مع قاعدة اختبار.
- auth/JWT tests.
- authorization وIDOR tests.
- subject isolation tests.
- upload validation tests.
- provider error/rate-limit tests.

Frontend:
- lint, typecheck, build.
- اختبارات للمسارات الأساسية حيث أمكن.
- فحص RTL وresponsive وloading/error states.

## 3. Security review
- لا secrets في Git أو client bundle أو logs.
- CORS مقيد.
- JWT signature/issuer/audience/expiry validation.
- كل endpoint خاص بالمادة يتحقق من العضوية.
- file upload محدود الحجم والنوع مع signature validation.
- rate limits للمسارات المكلفة.
- حماية من prompt injection ضمن محتوى المستندات.
- لا تعرض stack traces في production.
- راجع dependencies والـ advisories بأدوات مناسبة.

## 4. الأداء والتكلفة
- راجع pagination والفهارس.
- لا تُنشئ embeddings متكررة لنفس المحتوى دون داعٍ.
- حدّد أقصى طول للرسالة والسياق والملف.
- cache للمخرجات القابلة لإعادة الاستخدام مع invalidation صحيح.
- سجّل usage metadata، وافصل تقديرات الاستهلاك عن الفواتير المؤكدة.
- اختبر rate-limit/quota failure؛ لا تتجاوز القيود عبر مفاتيح متعددة.

## 5. التسليم
أنشئ:
- README نهائي.
- `docs/ARCHITECTURE.md`.
- `docs/ENV_SETUP_AR.md`.
- `docs/RUNBOOK_AR.md` لحل المشاكل المتكررة.
- `docs/TEST_REPORT.md` بأوامر الاختبار ونتائجها الحقيقية.
- تحديث `PROJECT_STATUS.md`.
- خطوات تشغيل محلية، وخطة نشر منفصلة لا تُنفذ دون إذن.
- قائمة known limitations وfeatures غير المكتملة.

## معيار التسليم
لكل ميزة صنّفها:
- Implemented
- Unit tested
- Integration tested
- Manually verified
- Production verified

لا تستخدم Production verified إلا بعد تحقق حقيقي على بيئة الإنتاج. اختم بتقرير صادق: ما يعمل، ما لا يعمل، ما يحتاج credentials، وما هي الخطوة التالية.
