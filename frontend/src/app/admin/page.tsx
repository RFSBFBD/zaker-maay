import { redirect } from "next/navigation";
import Link from "next/link";
import { hasSupabasePublicConfig } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";
import { AdminDashboard } from "@/components/admin-dashboard";
import { AppHeader } from "@/components/app-header";
import { AlertCircleIcon } from "@/components/icons";

export default async function AdminPage() {
  if (!hasSupabasePublicConfig()) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--paper)" }}>
        <AppHeader />
        <main className="shell" style={{ flex: 1, padding: "48px 0" }}>
          <div className="card" style={{ maxWidth: 540, margin: "40px auto", textAlign: "center", padding: "36px 24px" }}>
            <div style={{ width: 48, height: 48, borderRadius: "50%", background: "var(--warning-bg)", color: "var(--warning)", display: "grid", placeItems: "center", margin: "0 auto 16px" }}>
              <AlertCircleIcon size={24} />
            </div>
            <h1 style={{ fontSize: 22, fontWeight: 800, margin: "0 0 10px" }}>إعداد المصادقة مطلوب</h1>
            <p style={{ margin: "0 0 20px", color: "var(--muted)", fontSize: 14 }}>
              يلزم إعداد Supabase قبل فتح لوحة التحكم الإدارية.
            </p>
            <Link href="/" className="btn btn-secondary">
              العودة للرئيسية
            </Link>
          </div>
        </main>
      </div>
    );
  }

  const supabase = await createClient();
  const { data, error } = await supabase.auth.getClaims();
  if (error || !data?.claims) {
    redirect("/login?next=%2Fadmin");
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--paper)" }}>
      <AppHeader />
      <main className="shell-wide" style={{ flex: 1, padding: "32px 24px 60px" }}>
        <AdminDashboard />
      </main>
    </div>
  );
}
