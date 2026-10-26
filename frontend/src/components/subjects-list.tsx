"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { apiRequest } from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import {
  BookOpenIcon,
  PlusIcon,
  ClockIcon,
  FolderIcon,
} from "@/components/icons";

type Subject = { id: string; name: string; description: string | null; created_at: string };
type StudySession = { id: string; subject_id: string; planned_end_at: string; remaining_seconds: number };

function formatTime(seconds: number): string {
  const safeSeconds = Math.max(0, seconds);
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const remainder = safeSeconds % 60;
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`
    : `${minutes}:${String(remainder).padStart(2, "0")}`;
}

export function SubjectsList() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [activeSession, setActiveSession] = useState<StudySession | null>(null);
  const [durationMinutes, setDurationMinutes] = useState(25);
  const [sessionBusy, setSessionBusy] = useState(false);
  const [newSubjectName, setNewSubjectName] = useState("");
  const [newSubjectDescription, setNewSubjectDescription] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [isFormOpen, setIsFormOpen] = useState(true);

  useEffect(() => {
    let active = true;
    async function loadSubjects() {
      try {
        const supabase = createClient();
        const {
          data: { session },
          error: sessionError,
        } = await supabase.auth.getSession();
        if (sessionError || !session) throw new Error("انتهت جلسة الدخول. سجّل الدخول مجددًا.");
        const headers = { Authorization: `Bearer ${session.access_token}` };
        const [result, currentSession] = await Promise.all([
          apiRequest<Subject[]>("/api/v1/subjects", { headers }),
          apiRequest<StudySession | null>("/api/v1/study-sessions/active", { headers }).catch(() => null),
        ]);
        if (active) {
          setSubjects(result);
          setActiveSession(currentSession);
        }
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "تعذر تحميل المواد الدراسية.");
      } finally {
        if (active) setLoading(false);
      }
    }
    void loadSubjects();
    return () => {
      active = false;
    };
  }, []);

  const activeSessionId = activeSession?.id;
  useEffect(() => {
    if (!activeSessionId) return;
    const timer = window.setInterval(() => {
      setActiveSession((current) =>
        current
          ? { ...current, remaining_seconds: Math.max(0, current.remaining_seconds - 1) }
          : null
      );
    }, 1000);
    return () => window.clearInterval(timer);
  }, [activeSessionId]);

  async function getSessionHeaders(): Promise<Record<string, string>> {
    const {
      data: { session },
      error: sessionError,
    } = await createClient().auth.getSession();
    if (sessionError || !session) throw new Error("انتهت جلسة الدخول. سجّل الدخول مجددًا.");
    return { Authorization: `Bearer ${session.access_token}` };
  }

  async function startStudySession(subjectId: string) {
    setSessionBusy(true);
    setError(null);
    try {
      const headers = await getSessionHeaders();
      const session = await apiRequest<StudySession>("/api/v1/study-sessions", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ subject_id: subjectId, duration_minutes: durationMinutes }),
      });
      setActiveSession(session);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر بدء جلسة المذاكرة.");
    } finally {
      setSessionBusy(false);
    }
  }

  async function finishStudySession() {
    if (!activeSession) return;
    setSessionBusy(true);
    setError(null);
    try {
      const headers = await getSessionHeaders();
      await apiRequest(`/api/v1/study-sessions/${activeSession.id}/end`, { method: "POST", headers });
      setActiveSession(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر إنهاء الجلسة.");
    } finally {
      setSessionBusy(false);
    }
  }

  async function createSubject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!newSubjectName.trim()) return;
    setCreateBusy(true);
    setError(null);
    setNotice(null);
    try {
      const headers = await getSessionHeaders();
      const created = await apiRequest<Subject>("/api/v1/subjects", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ name: newSubjectName.trim(), description: newSubjectDescription.trim() || null }),
      });
      setSubjects((current) => [...current, created].sort((a, b) => a.name.localeCompare(b.name, "ar")));
      setNewSubjectName("");
      setNewSubjectDescription("");
      setNotice(`أُضيفت مادة «${created.name}» بنجاح! يمكنك الآن رفع الكتب والشروحات.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر إنشاء المادة.");
    } finally {
      setCreateBusy(false);
    }
  }

  async function archiveSubject(subject: Subject) {
    if (!window.confirm(`هل أنت متأكد من أرشفة مادة «${subject.name}»؟ ستبقى بياناتها محفوظة.`)) return;
    setError(null);
    setNotice(null);
    try {
      const headers = await getSessionHeaders();
      await apiRequest(`/api/v1/subjects/${subject.id}`, { method: "DELETE", headers });
      setSubjects((current) => current.filter((item) => item.id !== subject.id));
      setNotice(`أُرشفت مادة «${subject.name}» مع الاحتفاظ ببياناتها ومراجعها.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذرت أرشفة المادة.");
    }
  }

  const secondsLeft = activeSession?.remaining_seconds ?? 0;

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--paper)" }}>
      <AppHeader />

      <main className="shell" style={{ flex: 1, padding: "36px 24px 60px" }}>
        {/* Page Top Heading */}
        <div style={{ marginBottom: 30 }}>
          <span className="eyebrow" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <BookOpenIcon size={16} /> مساحة المذاكرة والتعلم
          </span>
          <h1 style={{ fontSize: "clamp(26px, 3.5vw, 38px)", fontWeight: 800, margin: "6px 0 10px", color: "var(--ink)" }}>
            موادك <span>الدراسية</span>
          </h1>
          <p className="intro" style={{ margin: 0, maxWidth: 640 }}>
            أنشئ موادك وخصص مصادر التعلم والكتب التي يشرح منها رفيقك الذكي «ذاكر معي».
          </p>
        </div>

        {loading && <p className="state-card" role="status">جارٍ تحميل موادك الدراسية ومصادرها…</p>}
        {!loading && error && <p className="state-card form-error" role="alert">{error}</p>}
        {!loading && notice && <p className="state-card form-notice" role="status">{notice}</p>}

        {/* ACTIVE STUDY SESSION BANNER */}
        {activeSession && (
          <section
            style={{
              background: "linear-gradient(135deg, var(--surface), var(--paper))",
              border: "1.5px solid var(--green)",
              borderRadius: 18,
              padding: "20px 24px",
              marginBottom: 28,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 16,
              boxShadow: "0 8px 24px rgba(45, 106, 79, 0.12)",
            }}
            aria-live="polite"
          >
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div
                style={{
                  width: 46,
                  height: 46,
                  borderRadius: 14,
                  background: "var(--mint)",
                  color: "var(--green)",
                  display: "grid",
                  placeItems: "center",
                }}
              >
                <ClockIcon size={24} />
              </div>
              <div>
                <span style={{ fontSize: 12, fontWeight: 700, color: "var(--green)", textTransform: "uppercase" }}>
                  جلسة تركيز نشطة الآن
                </span>
                <h3 style={{ margin: "2px 0 0", fontSize: 18, color: "var(--ink)", fontWeight: 800 }}>
                  {subjects.find((s) => s.id === activeSession.subject_id)?.name ?? "مادة دراسية"}
                </h3>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <span
                style={{
                  fontSize: 28,
                  fontWeight: 900,
                  fontFamily: "monospace",
                  color: "var(--orange)",
                  direction: "ltr",
                }}
              >
                {formatTime(secondsLeft)}
              </span>
              <button
                type="button"
                className="text-button"
                onClick={finishStudySession}
                disabled={sessionBusy}
                style={{
                  padding: "8px 18px",
                  borderRadius: 10,
                  border: "1px solid var(--line)",
                  background: "var(--surface)",
                  color: "#d9534f",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                إنهاء الجلسة
              </button>
            </div>
          </section>
        )}

        {/* DISTINCT NEW SUBJECT CREATION CARD (Fixes the squeezed screenshot layout) */}
        {!loading && (
          <section
            style={{
              background: "var(--surface)",
              border: "1px solid var(--line)",
              borderRadius: 20,
              padding: "28px",
              marginBottom: 36,
              boxShadow: "var(--shadow)",
            }}
            aria-labelledby="create-subject-heading"
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 20,
                borderBottom: "1px solid var(--line)",
                paddingBottom: 16,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span
                  style={{
                    width: 38,
                    height: 38,
                    borderRadius: 10,
                    background: "rgba(45, 106, 79, 0.12)",
                    color: "var(--green)",
                    display: "grid",
                    placeItems: "center",
                  }}
                >
                  <PlusIcon size={20} />
                </span>
                <div>
                  <h2 id="create-subject-heading" style={{ fontSize: 19, margin: 0, fontWeight: 800, color: "var(--ink)" }}>
                    إضافة مادة دراسية جديدة
                  </h2>
                  <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--muted)" }}>
                    أضف مادة جديدة لتبدأ برفع الملازم، المحاضرات الصوتية، وروابط الشرح فوراً.
                  </p>
                </div>
              </div>
            </div>

            <form onSubmit={createSubject} style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              {/* Responsive Inputs Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 18 }}>
                <div>
                  <label
                    htmlFor="new-subject-name"
                    style={{ display: "block", marginBottom: 7, fontSize: 13.5, fontWeight: 700, color: "var(--ink)" }}
                  >
                    اسم المادة الدراسية <span style={{ color: "var(--orange)" }}>*</span>
                  </label>
                  <input
                    id="new-subject-name"
                    required
                    maxLength={120}
                    placeholder="مثال: الرياضيات المتقدمة، علم الأحياء، الذكاء الاصطناعي…"
                    value={newSubjectName}
                    onChange={(event) => setNewSubjectName(event.target.value)}
                    style={{
                      width: "100%",
                      padding: "13px 16px",
                      borderRadius: 12,
                      border: "1.5px solid var(--line)",
                      background: "var(--paper)",
                      color: "var(--ink)",
                      fontSize: 14.5,
                      outline: "none",
                      boxSizing: "border-box",
                      transition: "border-color 0.2s, box-shadow 0.2s",
                    }}
                  />
                </div>

                <div>
                  <label
                    htmlFor="new-subject-description"
                    style={{ display: "block", marginBottom: 7, fontSize: 13.5, fontWeight: 700, color: "var(--ink)" }}
                  >
                    وصف المادة أو نبذة عن المنهج (اختياري)
                  </label>
                  <input
                    id="new-subject-description"
                    maxLength={1000}
                    placeholder="ملاحظات أو نبذة عن منهج المادة ومصادرها المعتمدة…"
                    value={newSubjectDescription}
                    onChange={(event) => setNewSubjectDescription(event.target.value)}
                    style={{
                      width: "100%",
                      padding: "13px 16px",
                      borderRadius: 12,
                      border: "1.5px solid var(--line)",
                      background: "var(--paper)",
                      color: "var(--ink)",
                      fontSize: 14.5,
                      outline: "none",
                      boxSizing: "border-box",
                      transition: "border-color 0.2s, box-shadow 0.2s",
                    }}
                  />
                </div>
              </div>

              {/* Submit Action */}
              <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12, marginTop: 4 }}>
                <button
                  type="submit"
                  disabled={createBusy || !newSubjectName.trim()}
                  className="session-start"
                  style={{
                    margin: 0,
                    padding: "12px 28px",
                    fontSize: 14.5,
                    fontWeight: 700,
                    borderRadius: 12,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <PlusIcon size={18} />
                  <span>{createBusy ? "جارٍ الإنشاء…" : "إنشاء المادة وبدء المذاكرة"}</span>
                </button>
              </div>
            </form>
          </section>
        )}

        {/* SUBJECTS TOOLBAR & PRESETS */}
        {!loading && subjects.length > 0 && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 16,
              marginBottom: 20,
              paddingBottom: 14,
              borderBottom: "1px solid var(--line)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <FolderIcon size={20} style={{ color: "var(--green)" }} />
              <h2 style={{ fontSize: 20, fontWeight: 800, margin: 0, color: "var(--ink)" }}>
                قائمة المواد المتاحة ({subjects.length})
              </h2>
            </div>

            {/* Clean Study Session Preset Selector */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                background: "var(--surface)",
                padding: "6px 14px",
                borderRadius: 12,
                border: "1px solid var(--line)",
              }}
            >
              <span style={{ fontSize: 13, color: "var(--muted)", fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
                <ClockIcon size={15} /> مدة الجلسة السريعة:
              </span>
              <div style={{ display: "flex", gap: 6 }}>
                {[15, 25, 45, 60].map((mins) => (
                  <button
                    key={mins}
                    type="button"
                    onClick={() => setDurationMinutes(mins)}
                    style={{
                      padding: "4px 10px",
                      borderRadius: 8,
                      border: "1px solid",
                      borderColor: durationMinutes === mins ? "var(--green)" : "var(--line)",
                      background: durationMinutes === mins ? "var(--green)" : "var(--paper)",
                      color: durationMinutes === mins ? "#fff" : "var(--ink)",
                      fontSize: 12.5,
                      fontWeight: 700,
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {mins} د
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* EMPTY STATE */}
        {!loading && !error && subjects.length === 0 && (
          <div
            style={{
              textAlign: "center",
              padding: "48px 24px",
              background: "var(--surface)",
              borderRadius: 20,
              border: "1px solid var(--line)",
            }}
          >
            <span
              style={{
                width: 64,
                height: 64,
                borderRadius: "50%",
                background: "rgba(45, 106, 79, 0.1)",
                color: "var(--green)",
                display: "grid",
                placeItems: "center",
                margin: "0 auto 16px",
              }}
            >
              <BookOpenIcon size={32} />
            </span>
            <h3 style={{ fontSize: 20, fontWeight: 800, margin: "0 0 8px", color: "var(--ink)" }}>
              لا توجد مواد دراسية بعد
            </h3>
            <p style={{ margin: 0, color: "var(--muted)", fontSize: 14 }}>
              أنشئ مادتك الأولى من النموذج أعلاه لتبدأ برفع الكتب والملفات والمحاضرات الصوتية!
            </p>
          </div>
        )}

        {/* SUBJECTS CARDS GRID */}
        {!loading && !error && subjects.length > 0 && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(310px, 1fr))",
              gap: 20,
            }}
          >
            {subjects.map((subject) => (
              <article
                key={subject.id}
                style={{
                  background: "var(--surface)",
                  borderRadius: 18,
                  padding: 24,
                  border: "1px solid var(--line)",
                  boxShadow: "var(--shadow)",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  gap: 16,
                  transition: "transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease",
                }}
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 700,
                        color: "var(--green)",
                        background: "var(--mint)",
                        padding: "4px 10px",
                        borderRadius: 8,
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 5,
                      }}
                    >
                      <BookOpenIcon size={13} /> مادة معتمدة
                    </span>
                    <button
                      type="button"
                      onClick={() => void archiveSubject(subject)}
                      title="أرشفة المادة"
                      style={{
                        background: "transparent",
                        border: 0,
                        cursor: "pointer",
                        fontSize: 12,
                        color: "var(--muted)",
                        padding: "4px 8px",
                        borderRadius: 6,
                      }}
                    >
                      أرشفة
                    </button>
                  </div>

                  <h3 style={{ fontSize: 19, fontWeight: 800, margin: "0 0 8px", color: "var(--ink)" }}>
                    {subject.name}
                  </h3>
                  <p
                    style={{
                      margin: 0,
                      fontSize: 13.5,
                      color: "var(--muted)",
                      lineHeight: 1.6,
                      display: "-webkit-box",
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}
                  >
                    {subject.description || "ابدأ برفع الملفات والمحاضرات ليقوم الذكاء الاصطناعي بشرحها."}
                  </p>
                </div>

                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", paddingTop: 12, borderTop: "1px solid var(--line)" }}>
                  <Link
                    href={`/subjects/${subject.id}`}
                    className="session-start"
                    style={{
                      flex: 1,
                      margin: 0,
                      padding: "10px 16px",
                      fontSize: 13.5,
                      borderRadius: 10,
                      fontWeight: 700,
                      textAlign: "center",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 6,
                    }}
                  >
                    <FolderIcon size={16} />
                    <span>مكتبة المادة والشرح</span>
                  </Link>

                  <button
                    type="button"
                    onClick={() => startStudySession(subject.id)}
                    disabled={sessionBusy || Boolean(activeSession)}
                    className="text-button"
                    style={{
                      padding: "10px 14px",
                      borderRadius: 10,
                      border: "1px solid var(--line)",
                      background: "var(--paper)",
                      color: "var(--ink)",
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <ClockIcon size={15} />
                    <span>جلسة ({durationMinutes}د)</span>
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
