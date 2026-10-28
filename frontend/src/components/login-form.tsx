"use client";

import { useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { hasSupabasePublicConfig } from "@/lib/supabase/config";
import { getSafeNextPath } from "@/lib/supabase/safe-next";
import { apiRequest } from "@/lib/api";
import { AlertCircleIcon, ChevronLeftIcon, UserIcon } from "@/components/icons";

export function LoginForm() {
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(() =>
    searchParams.get("authError") === "callback"
      ? "تعذر تأكيد الحساب. تأكد من صحة بياناتك أو تواصل مع إدارة المنصة."
      : null
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const supabase = createClient();
      const nextPath = getSafeNextPath(searchParams.get("next"));
      const result = await supabase.auth.signInWithPassword({ email: email.trim(), password });

      if (result.error) {
        if (result.error.message === "Invalid login credentials") {
          throw new Error("البريد الإلكتروني أو كلمة المرور غير صحيحة.");
        }
        if (result.error.message === "Email not confirmed") {
          throw new Error("الحساب قيد المراجعة أو يتطلب تأكيد البريد الإلكتروني.");
        }
        if (result.error.message === "Invalid API key") {
          throw new Error("تعذر الاتصال بخدمة تسجيل الدخول. تحقق من إعدادات Supabase.");
        }
        throw result.error;
      }

      if (result.data.session) {
        try {
          const profile = await apiRequest<{ id: string; email: string; role: string; display_name: string | null }>(
            "/api/v1/auth/me",
            { headers: { Authorization: `Bearer ${result.data.session.access_token}` } }
          );
          if (profile && typeof window !== "undefined") {
            localStorage.setItem("zaker_profile", JSON.stringify(profile));
          }
        } catch {
          // ignore cache error
        }
      }

      window.location.replace(nextPath);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر إكمال تسجيل الدخول.");
    } finally {
      setBusy(false);
    }
  }

  if (!hasSupabasePublicConfig()) {
    return (
      <div className="form-error" role="alert" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <AlertCircleIcon size={18} />
        <span>إعدادات تسجيل الدخول غير متوفرة. تحقق من مفاتيح Supabase في ملف البيئة.</span>
      </div>
    );
  }

  return (
    <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div>
        <label htmlFor="email" style={{ display: "block", marginBottom: 6, fontSize: 13.5, fontWeight: 700, color: "var(--ink)" }}>
          البريد الإلكتروني الأكاديمي
        </label>
        <input
          id="email"
          autoComplete="email"
          type="email"
          className="input-field"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="student@example.com"
          required
        />
      </div>

      <div>
        <label htmlFor="password" style={{ display: "block", marginBottom: 6, fontSize: 13.5, fontWeight: 700, color: "var(--ink)" }}>
          كلمة المرور
        </label>
        <input
          id="password"
          autoComplete="current-password"
          type="password"
          className="input-field"
          minLength={6}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="••••••••"
          required
        />
      </div>

      {error && (
        <div
          role="alert"
          className="form-error"
          style={{ display: "flex", alignItems: "center", gap: 8 }}
        >
          <AlertCircleIcon size={18} />
          <span>{error}</span>
        </div>
      )}

      <button
        className="btn btn-primary btn-lg"
        type="submit"
        disabled={busy}
        style={{ width: "100%", marginTop: 4 }}
      >
        <UserIcon size={18} />
        <span>{busy ? "جارٍ التحقق وتجهيز الجلسة…" : "تسجيل الدخول"}</span>
      </button>

      <p style={{ textAlign: "center", margin: "8px 0 0" }}>
        <Link href="/" className="text-button" style={{ fontSize: 13, color: "var(--muted)" }}>
          <span>العودة إلى الصفحة الرئيسية</span>
          <ChevronLeftIcon size={14} />
        </Link>
      </p>
    </form>
  );
}
