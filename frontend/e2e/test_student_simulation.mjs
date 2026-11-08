import { chromium } from "playwright";

const BASE_URL = "http://localhost:3000";

async function runStudentSimulation() {
  console.log("=== STARTING REAL STUDENT JOURNEY SIMULATION ===");
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
    }
  });

  try {
    // -------------------------------------------------------------
    // Step 1: Student visits landing page
    // -------------------------------------------------------------
    console.log("Step 1: Student visits landing page...");
    await page.goto(`${BASE_URL}/`, { waitUntil: "networkidle" });
    const title = await page.title();
    console.log("  -> Page title:", title);

    // Verify brand mark and text
    const brandText = await page.locator(".brand").first().innerText();
    console.log("  -> Brand found:", brandText.replace(/\n/g, " "));

    // -------------------------------------------------------------
    // Step 2: Student tests theme switcher (Light / Dark mode)
    // -------------------------------------------------------------
    console.log("Step 2: Student tests Theme Switcher...");
    const themeBtn = page.locator("button[aria-label*='الوضع']").first();
    const initialTheme = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
    console.log("  -> Initial data-theme:", initialTheme);

    await themeBtn.click();
    await page.waitForTimeout(300);
    const toggledTheme = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
    console.log("  -> Toggled data-theme:", toggledTheme);
    if (initialTheme === toggledTheme) {
      throw new Error(`Theme did not toggle: was ${initialTheme}, now ${toggledTheme}`);
    }

    // Toggle back
    await themeBtn.click();
    await page.waitForTimeout(200);

    // -------------------------------------------------------------
    // Step 3: Student clicks "ابدأ المذاكرة وسجل الدخول الآن" CTA button
    // -------------------------------------------------------------
    console.log("Step 3: Student clicks primary CTA button...");
    const ctaButton = page.locator('a[href="/login"]').first();
    await ctaButton.click();
    await page.waitForURL(/.*login/);
    console.log("  -> Correctly navigated to login page:", page.url());

    // -------------------------------------------------------------
    // Step 4: Student examines login form
    // -------------------------------------------------------------
    console.log("Step 4: Student examines and tests login form...");
    const emailInput = page.locator("input#email");
    const passwordInput = page.locator("input#password");
    const submitBtn = page.locator("button[type='submit']");

    // Empty fields check
    await submitBtn.click();
    // HTML5 validation requires email
    const emailValidity = await emailInput.evaluate((el) => el.checkValidity());
    console.log("  -> Empty email field flagged as invalid by HTML5:", !emailValidity);

    // Invalid login attempt
    console.log("Step 5: Student attempts login with incorrect credentials...");
    await emailInput.fill("nonexistent.student@example.com");
    await passwordInput.fill("WrongPassword123!");
    await submitBtn.click();

    // Expect friendly Arabic error alert
    const alertLocator = page.locator(".form-error[role='alert']");
    await alertLocator.waitFor({ state: "visible", timeout: 8000 });
    const alertMsg = await alertLocator.innerText();
    console.log("  -> Error message displayed:", alertMsg.trim());

    // -------------------------------------------------------------
    // Step 6: Test student navigation back to home and explore feature sections
    // -------------------------------------------------------------
    console.log("Step 6: Student returns to home page via brand link...");
    await page.locator('a[href="/"]').first().click();
    await page.waitForURL(`${BASE_URL}/`);

    // Check features grid
    const featureCards = await page.locator(".feature-card").count();
    console.log("  -> Feature cards count on landing page:", featureCards);

    // Check FAQ accordion if present
    const faqItems = await page.locator(".faq-item, details, .pricing-card").count();
    console.log("  -> Interactive cards/items found:", faqItems);

    // -------------------------------------------------------------
    // Step 7: Viewport responsiveness across all student device sizes
    // -------------------------------------------------------------
    console.log("Step 7: Testing responsive viewports for mobile/tablet/desktop...");
    const viewports = [
      { name: "iPhone SE (375px)", width: 375, height: 667 },
      { name: "iPhone 14 (390px)", width: 390, height: 844 },
      { name: "Pixel 7 (414px)", width: 414, height: 896 },
      { name: "iPad Mini (768px)", width: 768, height: 1024 },
      { name: "iPad Pro (1024px)", width: 1024, height: 1366 },
      { name: "Desktop (1440px)", width: 1440, height: 900 },
    ];

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.waitForTimeout(200);

      const hasHorizontalScroll = await page.evaluate(() => {
        return document.documentElement.scrollWidth > window.innerWidth;
      });

      console.log(`  -> Viewport ${vp.name}: width=${vp.width}px, horizontal overflow=${hasHorizontalScroll}`);
      if (hasHorizontalScroll) {
        throw new Error(`Accidental horizontal overflow detected at viewport ${vp.name}!`);
      }
    }

    console.log("Step 8: Console error tally during student session...");
    console.log("  -> Total console errors:", consoleErrors.length);
    if (consoleErrors.length > 0) {
      console.log("  -> Error details:", consoleErrors);
    }

    console.log("=== REAL STUDENT JOURNEY SIMULATION PASSED ===");
  } finally {
    await browser.close();
  }
}

runStudentSimulation().catch((err) => {
  console.error("SIMULATION FAILED:", err);
  process.exit(1);
});
