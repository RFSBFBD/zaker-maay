"use client";

import { useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { hasSupabasePublicConfig } from "@/lib/supabase/config";
import { getSafeNextPath } from "@/lib/supabase/safe-next";
import { apiRequest } from "@/lib/api";

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
      <p className="form-message form-error" role="alert">
        إعدادات تسجيل الدخول غير متوفرة. تحقق من مفاتيح Supabase في ملف البيئة.
      </p>
    );
  }

  return (
    <form className="auth-form" onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <label htmlFor="email" style={{ display: "block", marginBottom: 6, fontSize: 13.5, fontWeight: 700 }}>
          البريد الإلكتروني الأكاديمي
        </label>
        <input
          id="email"
          autoComplete="email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="student@example.com"
          required
          style={{
            width: "100%",
            padding: "12px 14px",
            borderRadius: 10,
            border: "1.5px solid var(--line)",
            background: "var(--paper)",
            color: "var(--ink)",
            fontSize: 14,
            outline: "none",
          }}
        />
      </div>

      <div>
        <label htmlFor="password" style={{ display: "block", marginBottom: 6, fontSize: 13.5, fontWeight: 700 }}>
          كلمة المرور
        </label>
        <input
          id="password"
          autoComplete="current-password"
          type="password"
          minLength={6}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="••••••••"
          required
          style={{
            width: "100%",
            padding: "12px 14px",
            borderRadius: 10,
            border: "1.5px solid var(--line)",
            background: "var(--paper)",
            color: "var(--ink)",
            fontSize: 14,
            outline: "none",
          }}
        />
      </div>

      {error && (
        <div
          role="alert"
          style={{
            padding: "10px 14px",
            borderRadius: 8,
            background: "rgba(217, 83, 79, 0.12)",
            border: "1px solid rgba(217, 83, 79, 0.3)",
            color: "#d9534f",
            fontSize: 13.5,
          }}
        >
          {error}
        </div>
      )}

      <button
        className="session-start"
        type="submit"
        disabled={busy}
        style={{
          width: "100%",
          padding: "13px",
          fontSize: 15,
          fontWeight: 700,
          borderRadius: 10,
          marginTop: 4,
        }}
      >
        {busy ? "جارٍ التحقق وتجهيز الجلسة…" : "تسجيل الدخول"}
      </button>

      <p style={{ textAlign: "center", margin: "10px 0 0" }}>
        <Link href="/" className="text-button" style={{ fontSize: 13, color: "var(--muted)" }}>
          ← العودة إلى الصفحة الرئيسية
        </Link>
      </p>
    </form>
  );
}
