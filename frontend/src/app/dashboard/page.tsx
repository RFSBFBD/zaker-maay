import { redirect } from "next/navigation";
import Link from "next/link";
import { hasSupabasePublicConfig } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";
import { ProgressDashboard } from "@/components/progress-dashboard";

export default async function DashboardPage() {
  if (!hasSupabasePublicConfig()) {
    return <main className="shell"><nav className="topbar"><Link className="brand" href="/"><span className="brand-mark">🎓</span><span>ذاكر معي</span></Link></nav><section className="subjects-content"><h1>إعداد تسجيل الدخول</h1><p className="intro">يلزم إعداد Supabase قبل عرض تقدم الدراسة.</p></section></main>;
  }
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getClaims();
  if (error || !data?.claims) redirect("/login?next=%2Fdashboard");
  return <main className="shell"><ProgressDashboard /></main>;
}
