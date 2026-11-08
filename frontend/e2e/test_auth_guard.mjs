import { chromium } from "playwright";

const BASE_URL = "http://localhost:3000";

async function testAuthGuards() {
  console.log("=== STARTING AUTH GUARD & REDIRECT TESTS ===");
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const protectedRoutes = [
    { path: "/dashboard", expectedNext: "/dashboard" },
    { path: "/subjects", expectedNext: "/subjects" },
    { path: "/admin", expectedNext: "/admin" },
    { path: "/subjects/00000000-0000-0000-0000-000000000001", expectedNext: "/subjects/00000000-0000-0000-0000-000000000001" },
  ];

  for (const route of protectedRoutes) {
    console.log(`Testing unauthorized access to ${route.path}...`);
    await page.goto(`${BASE_URL}${route.path}`, { waitUntil: "networkidle" });
    const currentUrl = page.url();
    console.log(`Redirected to: ${currentUrl}`);
    const isLoginPage = currentUrl.includes("/login");
    const hasNextParam = currentUrl.includes(encodeURIComponent(route.expectedNext)) || currentUrl.includes(route.expectedNext);
    console.log(`  -> Is on login: ${isLoginPage}, has next param: ${hasNextParam}`);
    if (!isLoginPage) {
      throw new Error(`Route ${route.path} did not redirect to /login! Got: ${currentUrl}`);
    }
  }

  await browser.close();
  console.log("=== AUTH GUARD TESTS PASSED ===");
}

testAuthGuards().catch((err) => {
  console.error("Auth Guard test failed:", err);
  process.exit(1);
});
