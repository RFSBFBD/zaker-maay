# حالة المشروع

- آخر تحديث: 2026-10-25
- المرحلة: تنفيذ ودمج المراحل 00–08؛ ليست جاهزة للإطلاق الإنتاجي الكامل حتى تدخل بيانات المواد والعضويات ويُختبر دخول المالك.
- Git: لا يوجد مستودع في مجلد المشروع.
- Runtime: Python 3.11.9، Node.js 24.15.0، npm 11.12.1.
- الأسرار: `.env` في جذر المشروع ومحمي في `.gitignore`; لم تُعرض قيمه.
- اتصالات حية: Supabase Auth/JWKS وNeon وCloudinary وGemini كلها `connected` عبر `scripts.check_connections`.
- قاعدة Neon: الفرع الأساسي المسمى production على `0011_study_artifacts`. migration `0011` اختُبرت بفرع مؤقت ثم طُبقت بموافقة المستخدم؛ الجدول والفهرس موجودان ولا توجد artifacts. counts: profile واحد student؛ subjects/members/resources/chunks/sessions/quizzes فارغة.
- Backend: 76 tests passed؛ تحذير SQLAlchemy واحد معروف في اختبار duplicate membership.
- Frontend: Next.js 16.4.3؛ lint/typecheck/build ناجحة. `/dashboard` يعرض تقدمًا محسوبًا من API.
- تكامل الواجهة: Next rewrite يمرر `/api/v1/*` من نفس الأصل إلى `API_PROXY_TARGET` الافتراضي `127.0.0.1:8000`. اختبار فعلي عبر build server أعاد 401 المتوقع لطلب بلا bearer، ما يثبت وصوله إلى API.
- CORS: API المستمع على 8000 ما زال يقبل localhost فقط. PID 7468 ظاهر، لكن اسم/مسار العملية غير متاحين؛ لم يتم إيقاف عملية مجهولة. الواجهة لا تعتمد على CORS بعد تشغيل Next الجديد.
- الميزات: auth + صلاحيات مادة، جلسات، رفع Cloudinary عبر الخادم، معالجة ملفات PDF/TXT/DOCX، RAG BM25 مع citations، مساعد Gemini، MCQ وحفظ النتائج، progress API/UI، روابط YouTube، audio transcript باختيار صريح، flashcards/concept maps/notes مع cache.
- غير مكتمل: لا مواد فعلية، واجهة admin لإنشاء/أرشفة المواد والعضويات عبر UUID، لكن لا bootstrap للدور؛ لا محادثات محفوظة، لا short-answer أو توصيات تكيفية، لا OCR ولا embeddings، ولا timestamps للصوت.
- الملفات التفصيلية: `docs/IMPLEMENTATION_STATUS.md`, `docs/TEST_REPORT.md`, `docs/ARCHITECTURE.md`, `docs/RUNBOOK_AR.md`.

## تشغيل محلي حالي

- النسخة القديمة على 8000 لا تزال موجودة وبها OpenAPI قديم (21 مسارًا)؛ لم تُوقف لعدم إمكانية التحقق من المالك.
- نسخة المشروع الحالية تعمل على 8001، وNext dev يعمل على `http://localhost:3000` مع proxy إلى 8001.
- API current OpenAPI يحتوي 25 مسارًا؛ `/` أعاد 200؛ المسارات المحمية عبر proxy أعادت 401 متوقعًا للمجهول.
- CORS على النسخة الحالية 8001 اجتاز origins المحلية الثلاثة ورفض origin خارجيًا.

