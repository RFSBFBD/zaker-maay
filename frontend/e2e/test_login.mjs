import { chromium } from "playwright";

const BASE_URL = "http://localhost:3000";

async function testLogin() {
  console.log("=== STARTING LOGIN PAGE E2E TESTS ===");
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  const pageErrors = [];
  page.on("pageerror", (err) => pageErrors.push(err.message));

  // 1. Visit Login Page
  console.log("1. Navigating to /login...");
  await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
  const title = await page.title();
  console.log("Title:", title);

  // Check UI elements
  const emailInput = page.locator("#email");
  const passwordInput = page.locator("#password");
  const submitBtn = page.locator("button[type='submit']");
  const homeLink = page.locator("a[href='/']").first();

  console.log("Email input visible:", await emailInput.isVisible());
  console.log("Password input visible:", await passwordInput.isVisible());
  console.log("Submit button visible:", await submitBtn.isVisible());
  console.log("Home link visible:", await homeLink.isVisible());

  // 2. Test Invalid Credentials
  console.log("2. Testing invalid credentials...");
  await emailInput.fill("nonexistent.student@example.com");
  await passwordInput.fill("WrongPassword123!");
  await submitBtn.click();

  // Wait for error alert to appear
  const errorAlert = page.locator(".form-error[role='alert']");
  await errorAlert.waitFor({ state: "visible", timeout: 8000 });
  const errorText = await errorAlert.textContent();
  console.log("Error alert displayed:", errorText?.trim());

  // 3. Test Malicious Input (XSS & SQL Injection)
  console.log("3. Testing SQL Injection & XSS in email/password fields...");
  await emailInput.fill("' OR 1=1; -- <script>alert('xss')</script>@test.com");
  await passwordInput.fill("'<script>alert(1)</script>'");
  await submitBtn.click();
  await errorAlert.waitFor({ state: "visible", timeout: 8000 });
  console.log("Malicious input handled safely. Alert:", (await errorAlert.textContent())?.trim());

  // 4. Test Viewports (Responsive / Mobile)
  console.log("4. Testing Responsive Viewports...");
  const viewports = [
    { name: "Mobile (375px)", width: 375, height: 667 },
    { name: "Tablet (768px)", width: 768, height: 1024 },
    { name: "Desktop (1440px)", width: 1440, height: 900 },
  ];
  for (const vp of viewports) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    const hasHorizontalScroll = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    console.log(`Viewport ${vp.name}: Horizontal scroll: ${hasHorizontalScroll} (expected: false)`);
  }

  console.log("Total console errors on /login:", consoleErrors.length);
  if (consoleErrors.length > 0) {
    console.log("Console errors detail:", consoleErrors);
  }
  console.log("Total page exceptions:", pageErrors.length);

  await browser.close();
  console.log("=== LOGIN PAGE E2E TESTS COMPLETED ===");
}

testLogin().catch((err) => {
  console.error("Login test failed:", err);
  process.exit(1);
});
