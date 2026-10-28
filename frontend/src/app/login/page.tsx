import { Suspense } from "react";
import Link from "next/link";
import { LoginForm } from "@/components/login-form";
import { GraduationCapIcon, ShieldIcon } from "@/components/icons";

export default function LoginPage() {
  return (
    <main
      className="shell"
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: "48px 16px",
      }}
    >
      <div style={{ maxWidth: 420, width: "100%", margin: "0 auto" }}>
        {/* Brand Header */}
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <Link href="/" className="brand" style={{ display: "inline-flex", marginBottom: 16 }}>
            <span className="brand-mark" style={{ width: 44, height: 44, borderRadius: 12 }}>
              <GraduationCapIcon size={26} />
            </span>
            <span style={{ fontSize: 24, fontWeight: 800 }}>ذاكر معي</span>
          </Link>
          <h1 style={{ fontSize: 24, fontWeight: 800, margin: "0 0 8px", color: "var(--ink)" }}>
            تسجيل الدخول إلى حسابك
          </h1>
          <p style={{ margin: 0, fontSize: 14, color: "var(--muted)", lineHeight: 1.6 }}>
            أدخل بريدك الأكاديمي وكلمة المرور لمتابعة المذاكرة.
          </p>
        </div>

        {/* Auth Card */}
        <section className="card" style={{ padding: "32px 28px" }}>
          <Suspense fallback={<div className="state-card">جارٍ تجهيز نموذج الدخول…</div>}>
            <LoginForm />
          </Suspense>
        </section>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6, marginTop: 24, fontSize: 13, color: "var(--muted)" }}>
          <ShieldIcon size={15} />
          <span>يتم تزويد الطلاب بحسابات الدخول حصرياً عبر إدارة المنصة.</span>
        </div>
      </div>
    </main>
  );
}
