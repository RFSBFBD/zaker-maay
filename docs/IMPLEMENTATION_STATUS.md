# حالة التنفيذ الفعلية

آخر تحديث: 2026-10-25. الحالة أدناه مبنية على فحوص هذه الجولة وعلى الملفات الفعلية. لا توجد بيانات اعتماد أو قيم `.env` في هذا التقرير.

## التقنيات

- الواجهة: Next.js 16.4.3 / React 19 / TypeScript، عربية RTL.
- API: FastAPI 0.162.0 / Python 3.11 / SQLAlchemy 2 / Alembic.
- المصادقة: Supabase Auth مع SSR وPKCE، والتحقق من JWT عبر JWKS في API.
- قاعدة التطبيق: Neon PostgreSQL. فحوص اتصال القراءة أكدت اتصال الفرع المسمى `production`.
- تخزين الملفات: Cloudinary على الخادم.
- الذكاء الاصطناعي: Gemini `gemini-3.5-flash-lite`.
- لا يوجد Git repository في جذر workspace. ملف `.env` مستثنى من `.gitignore` ولم تُعرض قيمه.

## مصفوفة المراحل

| المجال | المنفذ | تحقق هذه الجولة | المتبقي |
|---|---|---|---|
| الإعداد والمزودون | إعداد typed وإخفاء بيانات الاتصال، health endpoints، فاحص اتصالات | Supabase Auth وNeon وCloudinary وGemini: `connected` من فحص حي؛ فحص health المحلي 200 | health يعرض `configured_unchecked` عند عدم تنفيذ فحص مزود متزامن، وهذا وصف إعداد وليس نجاح اتصال |
| Auth والصلاحيات | Supabase signup/login/logout/callback، ملف طالب تلقائي، JWT توقيع/issuer/audience/expiry، عضوية مادة server-side | مجموعة API كاملة تشمل JWT والرفض دون bearer؛ فحوص JWKS حية | لا يوجد اختبار دخول بشري هذه الجولة؛ الملف الوحيد على Neon دوره `student`؛ تعيين admin الأول يحتاج إجراء مالك موثق |
| Neon schema | نماذج التطبيق وترحيلات توافقية غير هدامة | الفرع الأساسي اسمه `production`؛ Alembic `0011_study_artifacts`؛ جدول الأدوات وفهرسه موجودان؛ عدد الصفوف الجديدة 0 | قاعدة المحتوى خالية من المواد والعضويات والموارد والجلسات والاختبارات؛ يلزم إضافة محتوى وعضوية حقيقية |
| المواد والجلسات | عضوية وعزل API، CRUD إداري، أرشفة آمنة؛ مؤقت جلسة يعتمد الخادم | اختبارات API كاملة؛ منع الوصول غير المصرح | أُضيفت واجهة admin مشروطة بالدور لإنشاء/أرشفة المواد وإضافة عضوية عبر UUID؛ لا يوجد bootstrap للدور ولا إدارة/بحث للمستخدمين؛ لا مواد للطالب الحالي |
| Cloudinary | رفع Backend محمي، قيود نوع/حجم، SHA-256، metadata، روابط خاصة | اتصال usage حي؛ اختبارات المسار تستخدم mocks ولا ترفع بيانات مستخدم | لم يُجر رفع فعلي لملف؛ لا signed direct-upload |
| المصادر/RAG | PDF/TXT/DOCX، chunks، بحث BM25 مع قيد المادة، citations | اختبارات معالجة وعزل؛ Gemini live generation | لا OCR ولا embeddings/vector retrieval؛ لا محادثات محفوظة |
| الاختبارات والتقدم | MCQ، حفظ المحاولات وتصحيحها، endpoint تقدم الطالب | اختبارات backend؛ أضيفت صفحة `/dashboard` لعرض التقدم الحقيقي | لا توجد short-answer أو توصيات مراجعة تكيفية |
| أدوات الدراسة | روابط YouTube مسموحة النطاق؛ بطاقات وخريطة مفاهيم وملاحظات محفوظة؛ تفريغ صوت بموافقة checkbox واضحة | API tests، ترحيلات؛ Gemini live أنشأ 8 بطاقات من نص اصطناعي؛ لا ملف صوت شخصي أُرسل | لا timestamps؛ لا معالجة خلفية للملفات الطويلة؛ لا transcript لمقاطع YouTube |
| تشغيل المتصفح/CORS | Next API same-origin rewrite إلى FastAPI؛ `allowedDevOrigins` محصور بـ `172.16.0.2` | build server تجريبي على 3001 مرر الطلب إلى FastAPI وأعاد 401 متوقعًا للمجهول | خدمة 8000 الموجودة ترد لـ localhost فقط، وPID 7468 لا يكشف اسم/مسار العملية؛ لا توقفها. proxy يقلل اعتماد الواجهة على CORS، وتظل إعادة تشغيل المالك لازمة إذا احتجت الاتصال المباشر |
| QA والتسليم | توثيق architecture/runbook/test report؛ lint/typecheck/build واختبارات | Backend 76 passed؛ frontend lint/typecheck/build ناجحة؛ اتصال المزودين حي | لا E2E بشري أو responsive/accessibility visual review؛ لا تحقق production للرفع أو تسجيل الدخول |

## تعديلات هذه الجولة

- روابط YouTube آمنة: parser يقبل نطاقات YouTube الرسمية فقط، ولا يجلب عنوان المستخدم ولا ينزل الفيديو.
- تفريغ صوت opt-in: يرسل المستخدم التسجيل إلى Gemini فقط بعد تحديد مربع موافقة غير محدد افتراضيًا؛ يرفض صيغ/مدد/أحجام خارج الحد ويحفظ التفريغ وبياناته دون timestamps مخترعة.
- أدوات تعليمية محفوظة في Neon، scoped بالمادة مع cache مبني على hash المحتوى والنموذج وإصدار prompt.
- صفحة تقدم `/dashboard` من بيانات API الفعلية.
- Next rewrite للمسار `/api/v1/*` إلى `API_PROXY_TARGET` (افتراضيًا loopback)، حتى تكون مكالمات المتصفح same-origin. لا تتغير حماية JWT.
- ترحيل `0011_study_artifacts` أُعد واختُبر على فرع Neon مؤقت ثم طُبق على فرع `production` بعد موافقة المستخدم. تم تسجيل revision `0011_study_artifacts` والتحقق منه. الجدول جديد وفارغ؛ لم تُحذف بيانات.

## أوامر ونتائج التحقق

- `backend/.venv/Scripts/python.exe -m pytest -q`: 76 passed. تحذير SQLAlchemy واحد من اختبار duplicate membership، لا فشل.
- `npm run lint`: ناجح.
- `npm run typecheck`: ناجح.
- `npm run build`: ناجح على Next.js 16.4.3، ويشمل `/dashboard`.
- `backend/.venv/Scripts/python.exe -m scripts.check_connections`: `supabase_auth`, `database`, `cloudinary`, `gemini` كلها `connected`.
- Gemini live: إنتاج 8 بطاقات تعليمية عربية من مقتطف اختباري اصطناعي فقط.
- اختبار proxy: طلب `GET /api/v1/subjects` عبر Next على 3001 وصل إلى FastAPI وأعاد `401 Authentication required` بلا bearer (الحماية متوقعة).
- migrations محليًا: `alembic upgrade neon_existing_schema@head` على SQLite مؤقت وصل إلى `0011_study_artifacts`.
- فحص Neon بعد الترحيل: `alembic_version=0011_study_artifacts`، الجدول والفهرس موجودان، `study_artifacts=0`. `profiles=1` بدور student، وكل من subjects/subject_members/resources/resource_chunks/study_sessions/study_quizzes فارغ.

## متطلبات تشغيل ما زالت تحتاج المالك

1. أضف المواد والمحتوى وربط المستخدمين بها؛ لا يمكن اختراع منهج حقيقي أو عضوية من الكود.
2. عيّن أول admin من إجراء موثوق في Neon/Supabase بعد تحديد هوية المالك؛ لا يرفع التطبيق دور الطالب تلقائيًا.
3. أعد تشغيل العملية التي تملك 8000 من الطرفية/مدير العمليات الذي بدأها إذا أردت أن تقرأ CORS الحالي. واجهة Next تستخدم proxy same-origin بعد إعادة تشغيل Next لتطبيق الإعداد.
4. اختبار تسجيل الدخول الحقيقي يتطلب تسجيل المالك في المتصفح، وإعداد Redirect URLs في Supabase للمضيف المحلي المستخدم.
5. الرفع الحي يتطلب ملفًا يختاره المالك ويملك حق استخدامه؛ لم يُرفع أي ملف في الاختبارات.

## تشغيل محلي لهذه الجلسة

- API الأصلي على 8000 يحتوي build أقدم (OpenAPI 21 مسارًا) ومالك PID غير قابل للتعرف؛ تُرك دون إيقاف.
- شُغّلت نسخة workspace الحالية على `127.0.0.1:8001` (25 مسار OpenAPI بما فيها study artifacts وYouTube وprogress).
- شُغّلت Next dev على `127.0.0.1:3000` مع `API_PROXY_TARGET=http://127.0.0.1:8001`.
- `GET /` أعاد 200، و`/api/v1/subjects` عبر proxy أعاد 401 للمجهول، ومسار study-artifacts أعاد 401 بدل 404؛ الاختبار يثبت وصول proxy للمسارات الجديدة.
- preflight على API 8001: origins localhost و127.0.0.1 و172.16.0.2 كلها 200؛ `http://evil.example` أعاد 400.

