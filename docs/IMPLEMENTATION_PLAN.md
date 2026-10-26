# خطة التنفيذ

## المرحلة 0 — Bootstrap
- إنشاء مستودع نظيف به `frontend/`, `backend/`, `docs/`, `prompts/`.
- Next.js + TypeScript للواجهة، FastAPI للـ API.
- `/health/live` و`/health/ready` مع فصل liveness عن readiness.
- إعدادات environment validation، logging، CORS محدود، pytest، lint/type-check.
- README وتعليمات تشغيل محلية وملف حالة.

## المرحلة 1 — إعداد البيئة والاتصالات
- تحميل القيم من environment variables.
- فحوص اتصال مستقلة لـ Supabase Auth وNeon وCloudinary وGemini.
- لا تطبع secrets. أظهر حالة الخدمة ورسالة آمنة فقط.
- فشل إعداد خدمة اختيارية لا يجب أن يكسر health/liveness.

## المرحلة 2 — Auth
- Supabase Auth للمصادقة فقط.
- الواجهة تستخدم publishable key.
- backend يتحقق من JWT على كل endpoint محمي، ويتحقق من issuer/audience/expiry/signature.
- لا تثق في role قادم من body أو local storage.

## المرحلة 3 — قاعدة البيانات
- SQLAlchemy + Alembic.
- users/profiles, subjects, subject_memberships, resources, youtube_links, study_sessions, conversations, messages, quizzes, attempts, progress_events.
- قيود وفهارس وملكية واضحة، timestamps UTC.
- pgvector فقط إذا كان متاحًا ومدعومًا في Neon الحالي.

## المرحلة 4 — المواد والعزل
- لكل مادة عضوية واضحة.
- جميع الاستعلامات المقيّدة بالمادة تمر عبر صلاحيات الخادم.
- لا يمكن لطالب الوصول إلى مادة غير عضو فيها بتغيير ID.
- اختبارات IDOR وعزل RAG.

## المرحلة 5 — الملفات والفيديو
- Cloudinary signed upload flow.
- تحقق server-side من الحجم والنوع والمالك، وتخزين metadata.
- كشف التكرار عبر SHA-256 بعد معالجة الملف عند إمكان ذلك.
- YouTube: تخزين URL وvideo ID وmetadata؛ لا تنزّل أو تعِد استضافة فيديو محمي.
- لا تدّع إمكانية transcript من أي رابط؛ استخدم مصادر نصية مصرح بها أو اطلب رفع تسجيل يملكه المستخدم.

## المرحلة 6 — Gemini والصوت والمعالجة
- عميل Gemini من backend فقط.
- نموذج واختيارات capability configurable.
- معالجة صوتية مع فحص الأنواع والحجم والمدة والحدود الحالية.
- timestamps فقط إذا وفّرها النموذج/المعالجة فعليًا؛ وإلا صرّح بأنها غير متاحة أو تقديرية.
- تخزين jobs وحالات الفشل وإعادة المحاولة الآمنة.

## المرحلة 7 — RAG
- استخراج النص وتقسيمه إلى chunks وربط كل chunk بـ resource_id وsubject_id.
- embeddings مرة واحدة لكل نسخة محتوى محسوبة hash عند الإمكان.
- كل retrieval مقيّد بـ subject_id ومصرّح به server-side.
- استشهادات بالمصدر والصفحة/الوقت عندما تكون متوفرة.
- عند عدم كفاية المصادر، يوضح المساعد ذلك ولا يختلق إجابة.

## المرحلة 8 — المساعد والاختبارات
- محادثة داخل المادة الحالية فقط.
- إنشاء quizzes من مواد مصرح بها، وتصحيح مع تفسير.
- حفظ النتائج والتقدم ونقاط الضعف.
- أي أداة agent تنفذ تغييرات أو عمليات مؤثرة تحتاج validation وصلاحيات واضحة.

## المرحلة 9 — UX
- تسجيل دخول، dashboard، مواد، مكتبة، محادثة، رفع، روابط فيديو، اختبارات، تقدم.
- حالات loading/empty/error/offline.
- دعم العربية RTL والإنجليزية عند الحاجة، وlight/dark mode.
- لا تعتمد الواجهة على بيانات وهمية بعد ربط backend.

## المرحلة 10 — QA/Release
- unit/integration/e2e حسب النطاق.
- migrations على قاعدة اختبار أولًا.
- فحص secrets وdependencies وCORS وauthorization.
- توثيق env وrunbook ونسخ احتياطي/استعادة.
- لا تعتبر المشروع جاهزًا قبل اجتياز قائمة القبول.
