# منصة المذاكرة الذكية

تطبيق قيد التطوير يضم مصادقة Supabase، API FastAPI، صلاحيات المواد وجلسات المذاكرة، مكتبة ملفات خاصة، مساعدًا يسترجع من المادة، اختبارات محفوظة، تقدمًا دراسيًا، روابط YouTube، تفريغ صوت اختياريًا، وأدوات بطاقات/مفاهيم/ملاحظات. الحالة والقيود الفعلية موضحة في `docs/IMPLEMENTATION_STATUS.md` و`docs/TEST_REPORT.md`.

## التقنية المستهدفة
- Frontend: Next.js + TypeScript
- Backend: Python + FastAPI
- Auth: Supabase Auth فقط
- Database: Neon PostgreSQL
- Vector search: pgvector داخل PostgreSQL عند الحاجة
- File storage: Cloudinary
- AI: Gemini API
- Migrations: Alembic
- Tests: pytest + اختبارات الواجهة المناسبة

## ترتيب التنفيذ
1. `prompts/00_BOOTSTRAP_NEW_PROJECT_AR.md` — إنشاء المشروع من الصفر.
2. `prompts/01_MASTER_AGENT_LOOP_AR.md` — ثبّت هذا البرومبت كتعليمات عمل مستمرة للوكيل.
3. `prompts/02_ENV_AND_PROVIDER_INTEGRATION_AR.md` — تجهيز وربط الخدمات بعد إدخال القيم الحقيقية.
4. `prompts/03_AUTH_DATA_MODEL_AND_SUBJECT_ISOLATION_AR.md` — المصادقة وقاعدة البيانات والصلاحيات.
5. `prompts/04_CLOUDINARY_UPLOAD_AND_YOUTUBE_AR.md` — الملفات وروابط YouTube.
6. `prompts/05_GEMINI_AUDIO_TRANSCRIPTION_RAG_AR.md` — Gemini والصوت والمعالجة وRAG.
7. `prompts/06_AI_AGENT_QUIZZES_ADAPTIVE_AR.md` — المساعد والاختبارات والتقدم.
8. `prompts/07_FRONTEND_UX_AND_RESILIENCE_AR.md` — الواجهة وتجربة الاستخدام.
9. `prompts/08_RELEASE_QA_AND_HANDOFF_AR.md` — فحص نهائي وتشغيل وتسليم.

## التشغيل المحلي

المتطلبات: Node.js 20.9+ وPython 3.11+.

### Backend

من PowerShell داخل `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

فحوص الصحة: `GET http://127.0.0.1:8001/health/live` و`GET http://127.0.0.1:8001/health/ready`.
الإعدادات تُقرأ من متغيرات النظام، ثم ملف `D:\ai_study\.env` و`backend/.env` إن وُجد. افحص الاتصالات الحقيقية بأمر `.venv\Scripts\python.exe scripts\check_connections.py` من مجلد `backend`. الفحص يستخدم طلبات قراءة فقط لـ Supabase وNeon وCloudinary، ويجري طلب توليد Gemini صغيرًا.

لتحديث مخطط Neon الحالي استخدم من `backend/` بعد التأكد من الفرع: `.venv\Scripts\python.exe -m alembic upgrade neon_existing_schema@head`. الفرع الأساسي الحالي مسجل في Neon باسم `production` ووصل إلى `0011_study_artifacts`. يوجد سجل migrations محلي قديم محفوظ في فرع منفصل؛ لا تستخدم `alembic upgrade head` دون تحديد الفرع، ولا تشغّل ترحيلًا على production دون موافقة مالك المشروع.

تشغيل الاختبارات من `backend/`:

```powershell
python -m pytest -vv
```

### Frontend

من PowerShell داخل `frontend/`:

```powershell
npm ci
npm run dev
```

ثم افتح `http://localhost:3000`. تحقق الجودة والبناء عبر `npm run lint` و`npm run typecheck` و`npm run build`.

تحتاج واجهة الدخول إلى `SUPABASE_URL` و`SUPABASE_PUBLISHABLE_KEY`. تستخدم مكالمات API مسارًا same-origin عبر Next rewrite إلى `API_PROXY_TARGET`، والافتراضي `http://127.0.0.1:8000`. الرفع يتطلب إعداد `CLOUDINARY_CLOUD_NAME` و`CLOUDINARY_API_KEY` و`CLOUDINARY_API_SECRET` في الخادم. إعدادات الواجهة العامة تُقرأ من `.env` المحلي في الجذر أو من متغيرات البيئة. لا تضع مفاتيح الخادم في متغيرات `NEXT_PUBLIC_*`.

تأكيد الحساب يستخدم PKCE عبر المسار `/auth/callback`. من لوحة مشروع Supabase نفسه، اضبط **Authentication → URL Configuration** وأضف عناوين callback المحلية المسموح بها: `http://localhost:3000/auth/callback`، وأضف `http://172.16.0.2:3000/auth/callback` فقط عند فتح التطبيق عبر واجهة Cloudflare WARP المحلية. استخدم عنوانًا واحدًا ثابتًا عند التسجيل والدخول حتى تبقى كوكيز الجلسة على النطاق نفسه. يجب أن يطابق `SUPABASE_JWT_ISSUER` و`SUPABASE_JWT_JWKS_URL` مشروع `SUPABASE_URL`.

يحتوي `next.config.ts` على سماح تطوير محصور في `172.16.0.2` لأن هذا العنوان هو واجهة WARP المحلية لهذا الجهاز؛ لا توسّع `allowedDevOrigins` إلى جميع المصادر.

## قواعد أمان أساسية
- لا تضع `GEMINI_API_KEY` أو `CLOUDINARY_API_SECRET` أو `DATABASE_URL` في كود الواجهة أو أي متغير `NEXT_PUBLIC_*`.
- لا تستخدم Supabase service-role key في المتصفح.
- لا تكتب الأسرار في Git أو سجلات التشغيل أو تقارير الوكيل.
- لا تدّع نجاح الربط إلا بعد اختبار اتصال حقيقي.
- لا تنفّذ حذفًا واسعًا أو تغييرات مدمرة دون شرحها وأخذ موافقة المستخدم.
- اعزل بيانات كل مادة على الخادم، وليس اعتمادًا على prompt أو إخفاء عناصر الواجهة فقط.

## القيم التي ستحتاج إدخالها لاحقًا
ملف البيئة المحلي في الجذر هو `.env`، وهو مستثنى من Git. لا تطبع محتوياته أو تضعه في commit. يحتوي `backend/.env.example` على أسماء الإعدادات المطلوبة وقيم توضيحية فقط.

في `backend/.env` يجب أن يحتوي `CORS_ORIGINS` على أصل الواجهة الفعلي بالضبط. عند فتحها من WARP استخدم `http://172.16.0.2:3000`، مع عناوين localhost اللازمة، ثم أعد تشغيل FastAPI؛ تعديل `.env` وحده لا يحدّث إعداد middleware داخل عملية بدأت بالفعل.

