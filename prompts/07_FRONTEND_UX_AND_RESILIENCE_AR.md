# المرحلة 6 — واجهة الاستخدام العربية وتجربة موثوقة

## الصفحات
- تسجيل الدخول/إنشاء حساب.
- Dashboard: المواد والإحصاءات الأساسية.
- صفحة مادة: resources وYouTube links ومحادثة tutor.
- مكتبة الملفات وحالات المعالجة.
- رفع الملفات.
- صفحة الاختبارات والنتائج.
- صفحة التقدم وخطة المراجعة.
- صفحة إعدادات بسيطة.

## UX
- العربية RTL افتراضيًا، مع قابلية إضافة الإنجليزية.
- light/dark mode.
- حالات loading/empty/error/success واضحة.
- أخطاء الشبكة لا تمسح إدخالات المستخدم.
- تأكيد قبل العمليات المدمرة.
- عرض حالة processing مع polling محدود أو mechanism بسيط مناسب.
- رسائل خطأ للمستخدم لا تعرض stack traces أو secrets.
- لا تضع بيانات حساسة في localStorage؛ استخدم نمط جلسة Supabase الموصى به للـ framework الحالي.

## Integration
- استخدم API client موحدًا مع timeout وtyped responses.
- أرسل access token للـ backend عبر الطريقة المعتمدة، مع التعامل الصحيح مع refresh/expiry.
- لا تعتبر عناصر الواجهة وسيلة صلاحيات.
- لا تستخدم mock data في المسارات التي تدّعي أنها متصلة.
- افحص responsive layouts على شاشة ضيقة وسطح المكتب.
- اختبر accessibility الأساسية: labels, keyboard navigation, focus states, contrast.

## القبول
- مسار تسجيل الدخول والمواد والرفع والمحادثة والاختبار يعمل عبر API حقيقي عند ضبط الخدمات.
- حالات الخطأ لا تؤدي إلى crash.
- lint/typecheck/build ناجحة.
- توثيق طريقة تشغيل frontend وbackend معًا.
