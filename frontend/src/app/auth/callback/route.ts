import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { getSafeNextPath } from "@/lib/supabase/safe-next";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  if (!code) {
    return NextResponse.redirect(new URL("/login?authError=callback", request.url));
  }

  const supabase = await createClient();
  try {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (error) {
      return NextResponse.redirect(new URL("/login?authError=callback", request.url));
    }
  } catch {
    return NextResponse.redirect(new URL("/login?authError=callback", request.url));
  }

  const destination = getSafeNextPath(request.nextUrl.searchParams.get("next"));
  return NextResponse.redirect(new URL(destination, request.url));
}
