import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

const rootDirectory = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const environmentVariables = new Map([
  ["SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"],
  ["SUPABASE_PUBLISHABLE_KEY", "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"],
  ["NEXT_PUBLIC_API_BASE_URL", "NEXT_PUBLIC_API_BASE_URL"],
  ["API_PROXY_TARGET", "API_PROXY_TARGET"],
]);

try {
  const rootEnvironment = readFileSync(resolve(rootDirectory, ".env"), "utf8");
  for (const line of rootEnvironment.split(/\r?\n/)) {
    const match = line.match(/^\s*(SUPABASE_URL|SUPABASE_PUBLISHABLE_KEY|NEXT_PUBLIC_API_BASE_URL|API_PROXY_TARGET)\s*=\s*(.*?)\s*$/);
    if (!match) continue;
    const [, sourceName, rawValue] = match;
    const targetName = environmentVariables.get(sourceName);
    const value = rawValue.replace(/^(["'])(.*)\1$/, "$2");
    if (targetName && value && !process.env[targetName]) process.env[targetName] = value;
  }
} catch (error) {
  if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
}

const nextConfig: NextConfig = {
  // This is the local Cloudflare WARP interface reported by Next's dev server.
  // Keep the allow-list to this exact host instead of accepting arbitrary origins.
  allowedDevOrigins: ["172.16.0.2"],
  // Keep local browser API calls same-origin. This also avoids stale CORS
  // settings in an already-running FastAPI process during local development.
  async rewrites() {
    const apiTarget = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";
    return [{ source: "/api/v1/:path*", destination: `${apiTarget}/api/v1/:path*` }];
  },
};

export default nextConfig;
