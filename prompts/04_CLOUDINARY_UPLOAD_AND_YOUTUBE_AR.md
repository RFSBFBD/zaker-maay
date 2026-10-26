# المرحلة 3 — رفع الملفات إلى Cloudinary وإضافة روابط YouTube

## Cloudinary upload flow
1. نفّذ endpoint محميًا يجهز signed upload parameters للعميل.
2. التوقيع يجب أن يُنشأ server-side باستخدام `CLOUDINARY_API_SECRET`.
3. قيّد folder إلى `CLOUDINARY_FOLDER`، ولا تسمح للعميل باختيار folder عشوائي.
4. قيّد حجم الملف ونوعه وفق allowlist، مع فحص فعلي للـ MIME/extension قدر الإمكان.
5. بعد الرفع، أرسل `public_id`, `resource_type`, `bytes`, `format`, `secure_url` إلى backend ليتحقق عبر Cloudinary API أن الأصل موجود ومطابق للمستخدم والسياسة، ثم خزّن metadata فقط.
6. لا تقبل URL أو public_id من المستخدم كدليل ملكية.
7. لا تعرض API secret للواجهة. لا تجعل جميع الملفات public دون مراجعة متطلبات الخصوصية.
8. سجّل SHA-256 لمحتوى الملف إن أمكن بطريقة آمنة، واكتشف التكرار داخل النطاق الصحيح. لا تعتبر تشابه الاسم تكرارًا مؤكدًا.

## YouTube
- endpoint لإضافة URL ثم استخراج video ID عبر parser موثوق واختبار روابط youtube.com وyoutu.be.
- تحقق من البروتوكول والمضيف لمنع SSRF.
- خزّن الرابط وvideo ID وsubject_id وowner_id والبيانات المتاحة.
- استخدم embed رسميًا عند الحاجة، واحترم شروط YouTube.
- لا تنزّل فيديوهات أو تتجاوز DRM/قيود الوصول أو ترفعها إلى Cloudinary.
- لا تفترض أن transcript متاح. إن لم توجد subtitles مصرح بها/واجهة رسمية متاحة، اطلب من المستخدم رفع تسجيل أو ملف نصي يملك حق استخدامه.

## API / UX
- حالات upload: pending, uploaded, verified, failed, processing.
- أضف progress/error handling في الواجهة.
- تحقق من subject membership قبل بدء الرفع وبعده.
- اختبارات الحجم الزائد، نوع غير مسموح، signature invalid، asset غير مطابق، رابط YouTube غير صحيح، ومحاولة وصول لمادة أخرى.

## القبول
- ملف مسموح يُرفع ويُسجّل metadata.
- ملف غير مسموح يُرفض.
- فشل الرفع لا يترك resource في حالة نجاح كاذبة.
- اختبارات صلاحيات المواد ناجحة.
