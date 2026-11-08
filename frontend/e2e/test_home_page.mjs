import { chromium } from "playwright";

const BASE_URL = "http://localhost:3000";

async function testHomePage() {
  console.log("=== STARTING HOME PAGE E2E TESTS ===");
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto(BASE_URL, { waitUntil: "networkidle" });

  // 1. Check AppHeader elements
  const brand = page.locator(".brand").first();
  console.log("Brand text:", (await brand.textContent())?.trim());

  const themeToggle = page.locator("button[aria-label*='الوضع']");
  console.log("Theme toggle exists:", await themeToggle.isVisible());

  // Check initial theme
  const initialTheme = await page.evaluate(() => document.documentElement.dataset.theme);
  console.log("Initial theme:", initialTheme);

  // Click theme toggle
  await themeToggle.click();
  const toggledTheme = await page.evaluate(() => document.documentElement.dataset.theme);
  console.log("Toggled theme:", toggledTheme);
  if (initialTheme === toggledTheme) {
    throw new Error("Theme did not toggle!");
  }

  // Toggle back
  await themeToggle.click();
  const restoredTheme = await page.evaluate(() => document.documentElement.dataset.theme);
  console.log("Restored theme:", restoredTheme);

  // 2. Check Motivational Tip Cards
  const tipCard = page.locator("article, section").filter({ hasText: "الاسترجاع النشط" }).first();
  console.log("Motivational section exists:", await tipCard.isVisible());

  // 3. Test responsive design across all required viewports:
  // 375px, 390px, 414px, 768px, 1024px, 1440px
  const viewports = [
    { width: 375, height: 667, name: "iPhone SE (375px)" },
    { width: 390, height: 844, name: "iPhone 12/13/14 (390px)" },
    { width: 414, height: 896, name: "iPhone XR/11 (414px)" },
    { width: 768, height: 1024, name: "iPad Portrait (768px)" },
    { width: 1024, height: 768, name: "iPad Landscape / Laptop (1024px)" },
    { width: 1440, height: 900, name: "Desktop (1440px)" },
  ];

  for (const vp of viewports) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    const hasOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    console.log(`Viewport ${vp.name}: Horizontal overflow: ${hasOverflow}`);
    if (hasOverflow) {
      throw new Error(`Horizontal overflow detected on ${vp.name}!`);
    }
  }

  console.log("Console errors on home page:", consoleErrors.length);
  await browser.close();
  console.log("=== HOME PAGE E2E TESTS PASSED ===");
}

testHomePage().catch((err) => {
  console.error("Home Page test failed:", err);
  process.exit(1);
});
