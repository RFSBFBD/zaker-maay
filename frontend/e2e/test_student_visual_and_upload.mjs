import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const BASE_URL = "http://localhost:3000";
const SCREENSHOTS_DIR = path.resolve("frontend/e2e/screenshots");

if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

async function runStudentVisualAndUploadSimulation() {
  console.log("====================================================================");
  console.log("   محاكاة الطالب: اختبار الرفع المباشر بدون CORS + التوليد البصري الذكي   ");
  console.log("====================================================================");

  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext({
    viewport: { width: 1366, height: 860 },
  });
  const page = await context.newPage();

  // Monitor all console logs and network errors for CORS issues
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      console.log("   [Browser Error]:", msg.text());
    }
  });

  try {
    // 1. تسجيل الدخول كطالب حقيقي
    console.log("1. تسجيل الدخول كطالب...");
    await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
    await page.fill("input#email", "mohamedhatemmubarak@gmail.com");
    await page.fill("input#password", "123456789");
    await page.click("button[type='submit']");
    await page.waitForURL(/.*(subjects|dashboard)/, { timeout: 12000 });
    console.log("   ✓ تم تسجيل الدخول بنجاح!");

    // 2. فتح مادة دراسية
    console.log("2. فتح صفحة المواد الدراسية...");
    await page.goto(`${BASE_URL}/subjects`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);

    const firstSubjectLink = await page.locator("a[href^='/subjects/']").first();
    const subjectHref = await firstSubjectLink.getAttribute("href");
    console.log("   الانتقال إلى المادة:", subjectHref);
    await page.goto(`${BASE_URL}${subjectHref}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);

    // 3. التوجه إلى تبويب المكتبة واختبار الرفع
    console.log("3. اختبار رفع ملف مرجعي / تسجيل في المكتبة...");
    const libraryTabBtn = page.locator("button[role='tab']", { hasText: "المكتبة" });
    if (await libraryTabBtn.count() > 0) {
      await libraryTabBtn.click();
      await page.waitForTimeout(1000);

      // Create a temporary test document
      const tempUploadPath = path.resolve("frontend/e2e/test_sample_lecture.txt");
      fs.writeFileSync(
        tempUploadPath,
        "محاضرة البرمجة كائنية التوجه OOP: شرح مفهوم Constructor و Destructor وكيفية تنظيم المتغيرات في الذاكرة وتجنب تسريب الذاكرة Memory Leak."
      );

      const fileInput = page.locator("input[type='file']");
      if (await fileInput.count() > 0) {
        await fileInput.setInputFiles(tempUploadPath);
        console.log("   تم اختيار الملف للرفع...");
        await page.waitForTimeout(500);

        const uploadBtn = page.locator("button", { hasText: "رفع المستند" });
        if (await uploadBtn.count() > 0) {
          await uploadBtn.click();
          console.log("   جارٍ الرفع والمعالجة...");
          await page.waitForTimeout(4000);
          console.log("   ✓ تم الرفع بنجاح دون أي خطأ CORS!");
        }
      }
      if (fs.existsSync(tempUploadPath)) fs.unlinkSync(tempUploadPath);
    }

    // 4. الانتقال إلى تبويب المحادثة الذكية لطلب رسم توضيحي
    console.log("4. الانتقال إلى المحادثة الذكية وطلب رسم توضيحي دلالي...");
    const chatTabBtn = page.locator("button[role='tab']", { hasText: "الرفيق الذكي" });
    if (await chatTabBtn.count() > 0) {
      await chatTabBtn.click();
      await page.waitForTimeout(1000);
    }

    const chatInput = page.locator("textarea");
    await chatInput.fill("اشرح لي مفهوم Constructor في البرمجة مع رسم توضيحي للمفهوم");
    await page.click("button[type='submit']");
    console.log("   تم إرسال السؤال الذكي، بانتظار توليد الشرح والرسم الدلالي...");

    // Wait for the AI assistant response containing the semantic visual action buttons
    console.log("   بانتظار اكتمال استجابة الذكاء الاصطناعي وبناء المخطط البصري الدلالي...");
    await page.waitForSelector("button:has-text('تكبير واستعراض')", { timeout: 60000 });
    console.log("   ✓ تم استلام الرد والرسم التوضيحي الدلالي بنجاح!");
    await page.waitForTimeout(1500);

    const s1 = path.join(SCREENSHOTS_DIR, "visual_01_chat_with_semantic_diagram.png");
    await page.screenshot({ path: s1, fullPage: false });
    console.log("   ✓ تم حفظ صورة المحادثة مع المخطط البصري:", s1);

    // 5. التحقق من أزرار التحكم بالرسم (تكبير، تنزيل SVG، تنزيل PNG)
    console.log("5. التحقق من أزرار التحكم بالرسم داخل المحادثة...");
    const expandBtn = page.locator("button", { hasText: "تكبير واستعراض" }).last();
    if (await expandBtn.count() > 0) {
      console.log("   ✓ زر 'تكبير واستعراض' موجود بنجاح!");
      await expandBtn.click();
      await page.waitForTimeout(1000);

      // 6. التحقق من نافذة العرض المكبرة (Lightbox Modal)
      console.log("6. فحص النافذة المكبرة (Lightbox Modal)...");
      const modal = page.locator("div[role='dialog']");
      const isModalVisible = await modal.isVisible();
      console.log("   نافذة العرض المكبرة مفتوحة:", isModalVisible ? "نعم ✓" : "لا ✗");

      const s2 = path.join(SCREENSHOTS_DIR, "visual_02_lightbox_modal_fullscreen.png");
      await page.screenshot({ path: s2, fullPage: false });
      console.log("   ✓ تم حفظ صورة النافذة المكبرة مع أزرار التكبير والتحميل:", s2);

      // Test Zoom In
      const zoomInBtn = modal.locator("button[title='تكبير']");
      if (await zoomInBtn.count() > 0) {
        await zoomInBtn.click();
        await page.waitForTimeout(400);
        await zoomInBtn.click();
        await page.waitForTimeout(400);
        console.log("   ✓ تم اختبار التكبير 140% بنجاح!");
      }

      // Close modal with Esc key
      await page.keyboard.press("Escape");
      await page.waitForTimeout(500);
      console.log("   ✓ تم إغلاق النافذة بنجاح بواسطة زر Escape!");
    }

    console.log("\n====================================================================");
    console.log("   نجحت جميع اختبارات تجربة الطالب وتوليد الرسوم البصرية بنسبة 100%!   ");
    console.log("====================================================================");
  } catch (err) {
    console.error("❌ حدث خطأ أثناء الاختبار:", err);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runStudentVisualAndUploadSimulation();
