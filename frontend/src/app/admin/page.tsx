import { redirect } from "next/navigation";
import Link from "next/link";
import { hasSupabasePublicConfig } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";
import { AdminDashboard } from "@/components/admin-dashboard";

export default async function AdminPage() {
  if (!hasSupabasePublicConfig()) {
    return (
      <main className="shell">
        <nav className="topbar">
          <Link className="brand" href="/"><span className="brand-mark">🎓</span><span>ذاكر معي</span></Link>
        </nav>
        <section className="subjects-content">
          <h1>إعداد المصادقة</h1>
          <p className="intro">يلزم إعداد Supabase قبل فتح لوحة التحكم.</p>
        </section>
      </main>
    );
  }

  const supabase = await createClient();
  const { data, error } = await supabase.auth.getClaims();
  if (error || !data?.claims) {
    redirect("/login?next=%2Fadmin");
  }

  return (
    <main className="shell">
      <AdminDashboard />
    </main>
  );
}
