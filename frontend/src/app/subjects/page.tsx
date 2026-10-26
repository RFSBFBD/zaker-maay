import { redirect } from "next/navigation";
import Link from "next/link";
import { SubjectsList } from "@/components/subjects-list";
import { hasSupabasePublicConfig } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";

export default function SubjectsPage() {
  if (!hasSupabasePublicConfig()) {
    return <main className="shell"><nav className="topbar"><Link className="brand" href="/"><span className="brand-mark">🎓</span><span>ذاكر معي</span></Link></nav><section className="subjects-content"><h1>إعداد تسجيل الدخول</h1><p className="intro">يلزم إعداد رابط Supabase ومفتاح النشر العام قبل فتح المواد.</p></section></main>;
  }
  return <ProtectedSubjects />;
}

async function ProtectedSubjects() {
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getClaims();
  if (error || !data?.claims) redirect("/login?next=%2Fsubjects");
  return <main className="shell"><SubjectsList /></main>;
}
