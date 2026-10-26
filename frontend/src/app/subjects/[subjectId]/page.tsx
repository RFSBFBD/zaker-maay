import { redirect } from "next/navigation";
import { hasSupabasePublicConfig } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";
import { SubjectPageContent } from "@/components/subject-page-content";

export default async function SubjectPage({ params }: { params: Promise<{ subjectId: string }> }) {
  const { subjectId } = await params;

  // Ensure Supabase config exists
  if (!hasSupabasePublicConfig()) {
    return (
      <main className="shell">
        <p className="state-card">يلزم إعداد Supabase قبل فتح مكتبة المادة.</p>
      </main>
    );
  }

  const supabase = await createClient();
  const { data, error } = await supabase.auth.getClaims();
  if (error || !data?.claims) {
    redirect(`/login?next=${encodeURIComponent(`/subjects/${subjectId}`)}`);
    return null; // unreachable but satisfies TypeScript
  }

  return (
    <main className="shell">
      <SubjectPageContent subjectId={subjectId} />
    </main>
  );
}
