# المرحلة 2 — Supabase Auth وNeon schema وعزل المواد

## الهدف
مصادقة موثوقة ومخطط قاعدة بيانات يدعم منصة المذاكرة مع عزل صلاحيات المواد.

## Auth
1. استخدم Supabase Auth للـ signup/login/logout/session refresh.
2. في الواجهة، استخدم publishable key فقط.
3. في backend، تحقق من توقيع JWT وissuer وaudience وexpiry وفق طريقة Supabase الموثقة الحالية (JWKS أو آلية موثقة مكافئة).
4. لا تقبل `user_id` من body كهوية موثوقة؛ استخرج subject من token بعد التحقق.
5. أضف dependency واحدة موحدة لـ `current_user`.
6. لا تستخدم service-role key في frontend.
7. اختبر token مفقود/منتهي/توقيع خاطئ/issuer خاطئ.

## Schema مبدئي
صمّم SQLAlchemy models وAlembic migrations للكيانات الضرورية:
- profiles (id يطابق Supabase Auth user UUID)
- subjects
- subject_memberships (user_id, subject_id, role, created_at)
- resources (owner_id, subject_id, storage_provider, public metadata, content_hash, processing_status)
- youtube_links (subject_id, owner_id, video_id, url, title metadata optional)
- study_sessions (user_id, subject_id, started_at, ends_at, status)
- conversations (user_id, subject_id)
- messages (conversation_id, role, content, citations JSON)
- quizzes, quiz_questions, quiz_attempts
- progress_events

لا تضف أعمدة كثيرة بلا استخدام. استخدم UUIDs وUTC timestamps وقيود foreign keys وفهارس مناسبة. عالج حذف المستخدم/المادة وفق سياسة موثقة؛ لا تنفذ cascade مدمرًا دون فهم أثره.

## Authorization
- لكل endpoint يتعامل مع مادة، تحقق أن المستخدم عضو مسموح له بها.
- كل query للموارد/المحادثات/المصادر تقيّد بـ `subject_id` مصرح به.
- لا تعتمد على frontend filtering.
- امنع IDOR: جرّب تبديل subject_id/resource_id/conversation_id في الطلبات.
- دور admin لا يُقبل من client payload. حدّد مصدر role موثوقًا وسياسة تغييره.
- إن كانت المادة خاصة بصاحبها في MVP، أنشئ membership للمالك تلقائيًا.

## Study session
- أضف منطق جلسة مذاكرة اختيارية قابلة للضبط. لا تفرض قفلًا يمنع الطالب من تغيير المادة إلا إذا كان هذا السلوك مطلوبًا ومختبرًا.
- وقت البداية والنهاية مصدره الخادم، وليس ساعة المتصفح.
- امنع الجلسات المتداخلة إذا كانت قاعدة العمل المختارة تتطلب ذلك، باستخدام transaction/constraint مناسب.

## القبول
- Alembic upgrade على قاعدة تطوير ناجح.
- CRUD محدود للمواد والمكتبة يمر عبر auth + authorization.
- اختبارات ملكية وعزل وIDOR ناجحة.
- لا تُخزن كلمات مرور المستخدمين في Neon.
- توثيق طريقة إنشاء المستخدم الأول وسياسة admin دون hardcoding.
