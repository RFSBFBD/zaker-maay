import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const BASE_URL = "http://localhost:3000";
const SCREENSHOTS_DIR = path.resolve("frontend/e2e/screenshots");

if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

async function runRealUserVisualExperience() {
  console.log("====================================================================");
  console.log("   تجربة المستخدم الحقيقية بالكامل مع التقاط صور الشاشات الفعلية   ");
  console.log("====================================================================");

  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });
  const page = await context.newPage();

  try {
    // 1. الصفحة الرئيسية (Landing Page)
    console.log("1. فتح الصفحة الرئيسية كزائر...");
    await page.goto(`${BASE_URL}/`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    const p1 = path.join(SCREENSHOTS_DIR, "01_landing_page.png");
    await page.screenshot({ path: p1, fullPage: false });
    console.log("   ✓ تم حفظ صورة الصفحة الرئيسية:", p1);

    // 2. صفحة تسجيل الدخول (Login Page)
    console.log("2. الانتقال إلى صفحة تسجيل الدخول...");
    await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    const p2 = path.join(SCREENSHOTS_DIR, "02_login_page.png");
    await page.screenshot({ path: p2, fullPage: false });
    console.log("   ✓ تم حفظ صورة صفحة تسجيل الدخول:", p2);

    // 3. كتابة البيانات وتسجيل الدخول كطالب
    console.log("3. إدخال البريد الأكاديمي وكلمة المرور...");
    await page.fill("input#email", "mohamedhatemmubarak@gmail.com");
    await page.fill("input#password", "123456789");
    await page.click("button[type='submit']");
    await page.waitForURL(/.*(subjects|dashboard)/, { timeout: 12000 });
    await page.waitForTimeout(1500);

    // 4. صفحة المواد الدراسية (Subjects Catalog)
    console.log("4. الوصول إلى صفحة المواد الدراسية...");
    await page.goto(`${BASE_URL}/subjects`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    const p3 = path.join(SCREENSHOTS_DIR, "03_subjects_page.png");
    await page.screenshot({ path: p3, fullPage: false });
    console.log("   ✓ تم حفظ صورة صفحة المواد الدراسية:", p3);

    // 5. فتح مادة OOP والتفاعل مع الشرح الذكي (AI Chat)
    console.log("5. فتح مادة البرمجة كائنية التوجه OOP ومحادثة المساعد الذكي...");
    await page.goto(`${BASE_URL}/subjects/f5ddd060-c6a8-4e5d-a7e3-f6d60ab82fbc`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);

    const chatInput = page.locator("textarea, input[type='text']").last();
    await chatInput.fill("اشرح لي باختصار أهمية الـ Encapsulation في البرمجة كائنية التوجه.");
    const sendBtn = page.locator("button[type='submit']").last();
    await sendBtn.click();

    console.log("   -> جاري انتظار إجابة المساعد الذكي Gemini...");
    await page.waitForTimeout(8000);

    const p4 = path.join(SCREENSHOTS_DIR, "04_subject_chat_ai_response.png");
    await page.screenshot({ path: p4, fullPage: false });
    console.log("   ✓ تم التقاط صورة محادثة المساعد الذكي وإجابته الموثقة:", p4);

    // 6. تصفح البطاقات التعليمية (Flashcards)
    console.log("6. الانتقال إلى تبويب البطاقات التعليمية وقلب البطاقة...");
    const flashcardsTab = page.locator("button, [role='tab']").filter({ hasText: "البطاقات التعليمية" }).first();
    await flashcardsTab.click();
    await page.waitForTimeout(1500);

    const flipBtn = page.locator("button").filter({ hasText: "قلب البطاقة" }).or(page.locator("button").filter({ hasText: "إظهار الإجابة" })).first();
    if (await flipBtn.isVisible()) {
      await flipBtn.click();
      await page.waitForTimeout(600);
    }
    const p5 = path.join(SCREENSHOTS_DIR, "05_subject_flashcards_flip.png");
    await page.screenshot({ path: p5, fullPage: false });
    console.log("   ✓ تم التقاط صورة البطاقات التعليمية:", p5);

    // 7. لوحة المتابعة والتقدم الأكاديمي (Dashboard)
    console.log("7. فتح لوحة التقدم وساعات المذاكرة...");
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    const p6 = path.join(SCREENSHOTS_DIR, "06_dashboard_progress.png");
    await page.screenshot({ path: p6, fullPage: false });
    console.log("   ✓ تم التقاط صورة لوحة التقدم:", p6);

    console.log("\n====================================================================");
    console.log("   اكتمل اختبار تجربة المستخدم الحقيقية بنجاح 100%!                ");
    console.log("====================================================================");
  } finally {
    await browser.close();
  }
}

runRealUserVisualExperience().catch((err) => {
  console.error("خطأ في تشغيل تجربة المستخدم:", err);
  process.exit(1);
});
