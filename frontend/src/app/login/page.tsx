import { Suspense } from "react";
import Link from "next/link";
import { LoginForm } from "@/components/login-form";
import { GraduationCapIcon } from "@/components/icons";

export default function LoginPage() {
  return (
    <main className="shell auth-shell" style={{ minHeight: "100vh", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "40px 16px" }}>
      <div style={{ maxWidth: 440, width: "100%", margin: "0 auto" }}>
        {/* Brand header */}
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
            <span
              style={{
                width: 44,
                height: 44,
                borderRadius: 14,
                background: "linear-gradient(135deg, var(--green), var(--green-hover))",
                color: "#fff",
                display: "grid",
                placeItems: "center",
                boxShadow: "0 8px 24px rgba(45, 106, 79, 0.25)",
              }}
            >
              <GraduationCapIcon size={26} />
            </span>
            <span style={{ fontSize: 24, fontWeight: 800, color: "var(--ink)", letterSpacing: -0.5 }}>ذاكر معي</span>
          </Link>
          <h1 style={{ fontSize: 24, fontWeight: 800, margin: "16px 0 6px", color: "var(--ink)" }}>
            تسجيل الدخول إلى مساحة دراستك
          </h1>
          <p style={{ margin: 0, fontSize: 14, color: "var(--muted)", lineHeight: 1.6 }}>
            أدخل بيانات حسابك المعتمدة لمتابعة جلسات المذاكرة والشرح الذكي.
          </p>
        </div>

        {/* Auth card */}
        <section
          style={{
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: 20,
            padding: "32px 28px",
            boxShadow: "var(--shadow)",
          }}
        >
          <Suspense fallback={<p className="state-card" role="status">جارٍ تجهيز نموذج الدخول…</p>}>
            <LoginForm />
          </Suspense>
        </section>

        <p style={{ textAlign: "center", marginTop: 24, fontSize: 13, color: "var(--muted)" }}>
          يتم تزويد الطلاب بحسابات الدخول حصرياً عبر إدارة المنصة.
        </p>
      </div>
    </main>
  );
}
