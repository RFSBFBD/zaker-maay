"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { apiRequest } from "@/lib/api";
import { AppHeader } from "@/components/app-header";

type SubjectProgress = {
  subject_id: string;
  subject_name: string;
  study_seconds: number;
  quiz_attempts: number;
  quiz_average_percent: number | null;
  last_studied_at: string | null;
};

type Progress = {
  study_seconds: number;
  quiz_attempts: number;
  quiz_average_percent: number | null;
  subjects: SubjectProgress[];
};

type DashboardInfo = {
  skill_level: number;
  level_description: string;
  total_subjects: number;
  total_resources: number;
};

type InquiryItem = {
  id: string;
  subject_id: string;
  subject_name: string;
  question: string;
  ai_suggested_answer: string | null;
  status: "pending" | "approved" | "rejected";
  admin_answer: string | null;
  admin_notes: string | null;
  is_read: boolean;
  created_at: string;
  answered_at: string | null;
};

type InquiriesResponse = {
  inquiries: InquiryItem[];
  unread_count: number;
};

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours > 0 ? `${hours} ساعة و ${minutes} دقيقة` : `${minutes} دقيقة`;
}

function getSkillBadge(level: number) {
  if (level <= 2) return { title: "مستكشف واعد 🌱", color: "#668270" };
  if (level <= 4) return { title: "متعلم نشط 📚", color: "#315f50" };
  if (level <= 6) return { title: "محلل مفاهيمي 🔍", color: "#2563eb" };
  if (level <= 8) return { title: "باحث متقدم 🎯", color: "#7c3aed" };
  return { title: "عالم متفوق 👑", color: "#d97706" };
}

export function ProgressDashboard() {
  const [progress, setProgress] = useState<Progress | null>(null);
  const [dashboard, setDashboard] = useState<DashboardInfo | null>(null);
  const [inquiriesData, setInquiriesData] = useState<InquiriesResponse>({ inquiries: [], unread_count: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"evaluation" | "inquiries">("evaluation");

  useEffect(() => {
    let active = true;
    async function loadData() {
      try {
        const {
          data: { session },
          error: sessionError,
        } = await createClient().auth.getSession();
        if (sessionError || !session) throw new Error("انتهت جلسة الدخول. سجّل الدخول مجددًا.");
        const headers = { Authorization: `Bearer ${session.access_token}` };
        const [result, dashboardResult, inqResult] = await Promise.all([
          apiRequest<Progress>("/api/v1/progress/me", { headers }),
          apiRequest<DashboardInfo>("/api/v1/progress/me/dashboard", { headers }).catch(() => null),
          apiRequest<InquiriesResponse>("/api/v1/inquiries/me", { headers }).catch(() => ({
            inquiries: [],
            unread_count: 0,
          })),
        ]);
        if (active) {
          setProgress(result);
          setDashboard(dashboardResult);
          setInquiriesData(inqResult);
        }
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "تعذر تحميل لوحة التقدم والتقييم.");
      } finally {
        if (active) setLoading(false);
      }
    }
    void loadData();
    return () => {
      active = false;
    };
  }, []);

  const skillLevel = dashboard?.skill_level || 1;
  const badge = getSkillBadge(skillLevel);

  return (
    <>
      <AppHeader />
      <section className="subjects-content" aria-labelledby="progress-title" style={{ maxWidth: 960 }}>
        <p className="eyebrow">🎓 ملف الطالب والتقييم الأكاديمي الذكي</p>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h1 id="progress-title" style={{ margin: "6px 0 10px" }}>
              تقييمك <span>الأكاديمي والمستمر</span>
            </h1>
            <p className="intro" style={{ margin: 0 }}>
              التقييم هنا مبني على أسس التعلم العميق: انتظام جلسات التركيز، دقة الاسترجاع النشط، وعمق التفاعل والاستفسار.
            </p>
          </div>
          <span
            style={{
              padding: "8px 18px",
              borderRadius: 20,
              background: "rgba(49, 95, 80, 0.12)",
              color: badge.color,
              fontWeight: 700,
              fontSize: 15,
              border: `1px solid ${badge.color}`,
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            {badge.title}
          </span>
        </div>

        {loading && <p className="state-card" role="status">جارٍ تحميل التقييم الأكاديمي…</p>}
        {!loading && error && <p className="state-card form-error" role="alert">{error}</p>}

        {!loading && !error && (
          <>
            {/* Navigation Tabs between Evaluation & Inquiries */}
            <div style={{ display: "flex", gap: 10, margin: "28px 0 20px", borderBottom: "1px solid var(--line)", paddingBottom: 8 }}>
              <button
                type="button"
                onClick={() => setActiveTab("evaluation")}
                style={{
                  padding: "10px 20px",
                  borderRadius: 8,
                  border: 0,
                  cursor: "pointer",
                  fontWeight: 600,
                  fontSize: 14,
                  background: activeTab === "evaluation" ? "var(--green)" : "transparent",
                  color: activeTab === "evaluation" ? "#fff" : "var(--muted)",
                  transition: "all 0.2s",
                }}
              >
                📊 التقييم ومؤشرات الاستيعاب
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("inquiries")}
                style={{
                  padding: "10px 20px",
                  borderRadius: 8,
                  border: 0,
                  cursor: "pointer",
                  fontWeight: 600,
                  fontSize: 14,
                  background: activeTab === "inquiries" ? "var(--green)" : "transparent",
                  color: activeTab === "inquiries" ? "#fff" : "var(--muted)",
                  transition: "all 0.2s",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <span>📬 استفساراتي وأسئلتي المعلقة</span>
                {inquiriesData.unread_count > 0 && (
                  <span
                    style={{
                      background: "#d9534f",
                      color: "#fff",
                      fontSize: 11,
                      padding: "2px 6px",
                      borderRadius: 10,
                      fontWeight: 700,
                    }}
                  >
                    {inquiriesData.unread_count} جديدة
                  </span>
                )}
              </button>
            </div>

            {/* TAB 1: Evaluation by Deep Learning Principles */}
            {activeTab === "evaluation" && (
              <div>
                {/* Skill Mastery Meter Card */}
                <div
                  className="skill-level-section"
                  style={{
                    background: "var(--surface, #fff)",
                    border: "1px solid var(--line)",
                    borderRadius: 16,
                    padding: "26px",
                    marginBottom: 24,
                    boxShadow: "0 4px 16px rgba(0,0,0,0.03)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                    <div>
                      <span style={{ fontSize: 13, color: "var(--muted)", fontWeight: 600 }}>
                        مستوى إتقان واستيعاب الطالب
                      </span>
                      <h3 style={{ margin: "4px 0 0", fontSize: 22, color: "var(--ink)", fontWeight: 800 }}>
                        المستوى {skillLevel} من 10 · {dashboard?.level_description || "مستوى مبتدئ في بناء المفاهيم"}
                      </h3>
                    </div>
                    <div
                      style={{
                        fontSize: 32,
                        fontWeight: 900,
                        color: "var(--green)",
                        fontFamily: "'DM Sans', sans-serif",
                      }}
                    >
                      {skillLevel * 10}%
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div
                    style={{
                      height: 14,
                      background: "var(--line)",
                      borderRadius: 8,
                      overflow: "hidden",
                      margin: "12px 0 16px",
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        width: `${(skillLevel / 10) * 100}%`,
                        background: "linear-gradient(90deg, var(--green), #5da086)",
                        borderRadius: 8,
                        transition: "width 0.5s ease",
                      }}
                    />
                  </div>

                  {/* Personalized Study Feedback */}
                  <div
                    style={{
                      background: "var(--paper)",
                      borderRadius: 10,
                      padding: "14px 18px",
                      fontSize: 14,
                      lineHeight: 1.8,
                      color: "var(--ink)",
                      borderRight: "4px solid var(--green)",
                    }}
                  >
                    <strong>💡 توجيه ذكي لمستواك الحالي:</strong>{" "}
                    {skillLevel <= 3
                      ? "أنت في مرحلة التأسيس واستيعاب القواعد الأولى. يُنصح بالتركيز على الشروحات المبسطة وجلسات بومودورو القصيرة (25 دقيقة) وتفعيل الرسوم التوضيحية البصرية لتثبيت الصور الذهنية."
                      : skillLevel <= 6
                      ? "مستواك متقدم وتظهر قدرة ممتازة على ربط المفاهيم. ركّز على الاختبارات القصيرة والتأصيل النظري وطرح الأسئلة الاستنتاجية على المساعد الذكي."
                      : "أداء أكاديمي استثنائي! مساعدك الذكي الآن يخاطبك بلغة أكاديمية متعمقة ويركز على النقد والتحليل والمقارنات العلمية المتقدمة."}
                  </div>
                </div>

                {/* Core Principles Breakdown Grid */}
                <h3 style={{ fontSize: 18, marginBottom: 14 }}>🎯 ركائز التقييم الأكاديمي الحقيقي</h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14, marginBottom: 32 }}>
                  {/* Principle 1: Focus consistency */}
                  <div
                    style={{
                      background: "var(--surface, #fff)",
                      border: "1px solid var(--line)",
                      borderRadius: 12,
                      padding: "20px",
                    }}
                  >
                    <span style={{ fontSize: 24, display: "block", marginBottom: 6 }}>⏱️</span>
                    <h4 style={{ margin: "0 0 6px", fontSize: 16 }}>انتظام جلسات التركيز</h4>
                    <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
                      المذاكرة الموزعة المستمرة بدلاً من الحشو السريع غير المجدي.
                    </p>
                    <strong style={{ fontSize: 20, color: "var(--green)" }}>
                      {formatDuration(progress?.study_seconds || 0)}
                    </strong>
                  </div>

                  {/* Principle 2: Active Recall */}
                  <div
                    style={{
                      background: "var(--surface, #fff)",
                      border: "1px solid var(--line)",
                      borderRadius: 12,
                      padding: "20px",
                    }}
                  >
                    <span style={{ fontSize: 24, display: "block", marginBottom: 6 }}>🧠</span>
                    <h4 style={{ margin: "0 0 6px", fontSize: 16 }}>الاسترجاع النشط والتأكيد</h4>
                    <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
                      مدى حل الأسئلة لتأكيد الفهم واسترجاع المعلومات من الذاكرة طويلة المدى.
                    </p>
                    <strong style={{ fontSize: 20, color: "var(--green)" }}>
                      {progress?.quiz_attempts || 0} محاولات اختبار
                    </strong>
                  </div>

                  {/* Principle 3: Inquiry & Critical Thinking */}
                  <div
                    style={{
                      background: "var(--surface, #fff)",
                      border: "1px solid var(--line)",
                      borderRadius: 12,
                      padding: "20px",
                    }}
                  >
                    <span style={{ fontSize: 24, display: "block", marginBottom: 6 }}>🔍</span>
                    <h4 style={{ margin: "0 0 6px", fontSize: 16 }}>عمق الفضول الأكاديمي</h4>
                    <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
                      طرح التساؤلات والبحث وطلب الرسوم البصرية لتثبيت النقاط الغامضة.
                    </p>
                    <strong style={{ fontSize: 20, color: "var(--green)" }}>
                      {inquiriesData.inquiries.length} استفسار موجه
                    </strong>
                  </div>
                </div>

                {/* Per-Subject Breakdown */}
                {progress && progress.subjects.length > 0 && (
                  <div>
                    <h3 style={{ fontSize: 18, marginBottom: 14 }}>📚 تفصيل الإنجاز حسب المواد</h3>
                    <div style={{ display: "grid", gap: 10 }}>
                      {progress.subjects.map((sub) => (
                        <div
                          key={sub.subject_id}
                          style={{
                            background: "var(--surface, #fff)",
                            border: "1px solid var(--line)",
                            borderRadius: 10,
                            padding: "16px 20px",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            flexWrap: "wrap",
                            gap: 12,
                          }}
                        >
                          <div>
                            <h4 style={{ margin: "0 0 4px", fontSize: 16 }}>{sub.subject_name}</h4>
                            <p style={{ margin: 0, fontSize: 12, color: "var(--muted)" }}>
                              {sub.last_studied_at
                                ? `آخر جلسة مذاكرة: ${new Date(sub.last_studied_at).toLocaleDateString("ar-EG")}`
                                : "لم تبدأ بعد"}
                            </p>
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                            <span style={{ fontSize: 13, color: "var(--green)", fontWeight: 600 }}>
                              ⏱️ {formatDuration(sub.study_seconds)}
                            </span>
                            <Link
                              href={`/subjects/${sub.subject_id}`}
                              className="session-start"
                              style={{ margin: 0, padding: "6px 14px", fontSize: 12 }}
                            >
                              متابعة المذاكرة ←
                            </Link>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: Student Inquiries (Out-of-scope Questions submitted to Admin) */}
            {activeTab === "inquiries" && (
              <div>
                <p style={{ color: "var(--muted)", fontSize: 14, margin: "0 0 20px", lineHeight: 1.7 }}>
                  هنا تجد كل الأسئلة التي سألتها ولم تكن متوفرة مباشرة في مراجع المادة المرفوعة، وتم توجيهها لإدارة
                  المادة لمراجعتها واعتماد إجابتها رسمياً.
                </p>

                {inquiriesData.inquiries.length === 0 ? (
                  <div className="state-card" style={{ textAlign: "center", padding: "40px 20px" }}>
                    <span style={{ fontSize: 36, display: "block", marginBottom: 8 }}>✨</span>
                    <strong>لا توجد استفسارات معلقة حتى الآن!</strong>
                    <p style={{ margin: "6px 0 0", color: "var(--muted)", fontSize: 14 }}>
                      كل أسئلتك كانت متوفرة بدقة ضمن ملفات ومراجع مادتك، أو أنك لم تطرح أسئلة خارج نطاق المنهج بعد.
                    </p>
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                    {inquiriesData.inquiries.map((inq) => (
                      <article
                        key={inq.id}
                        style={{
                          background: "var(--surface, #fff)",
                          border: inq.status === "approved" ? "1px solid var(--green)" : "1px solid var(--line)",
                          borderRadius: 12,
                          padding: "20px",
                          boxShadow: "0 2px 8px rgba(0,0,0,0.03)",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginBottom: 8,
                          }}
                        >
                          <span style={{ fontWeight: 700, color: "var(--green)", fontSize: 14 }}>
                            📚 {inq.subject_name}
                          </span>
                          <span
                            style={{
                              fontSize: 12,
                              fontWeight: 600,
                              padding: "3px 10px",
                              borderRadius: 12,
                              background:
                                inq.status === "approved"
                                  ? "#e7f0e5"
                                  : inq.status === "rejected"
                                  ? "#fff0ed"
                                  : "#fff8ec",
                              color:
                                inq.status === "approved"
                                  ? "#2a7e43"
                                  : inq.status === "rejected"
                                  ? "#9b3f32"
                                  : "#b45309",
                              border: "1px solid currentColor",
                            }}
                          >
                            {inq.status === "approved"
                              ? "✅ معتمد ومجاب من الإدارة"
                              : inq.status === "rejected"
                              ? "❌ تم الرفض (خارج المنهج)"
                              : "⏳ قيد مراجعة الإدارة"}
                          </span>
                        </div>

                        {/* Question */}
                        <h4 style={{ margin: "6px 0 10px", fontSize: 16, color: "var(--ink)" }}>
                          السؤال: «{inq.question}»
                        </h4>

                        {/* Admin Official Answer */}
                        {inq.admin_answer && (
                          <div
                            style={{
                              background: "rgba(49, 95, 80, 0.08)",
                              borderRight: "4px solid var(--green)",
                              padding: "12px 16px",
                              borderRadius: 8,
                              marginTop: 10,
                            }}
                          >
                            <strong style={{ display: "block", color: "var(--green)", fontSize: 13, marginBottom: 4 }}>
                              الإجابة الرسمية المعتمدة من إدارة المادة:
                            </strong>
                            <p style={{ margin: 0, fontSize: 14, lineHeight: 1.7, color: "var(--ink)" }}>
                              {inq.admin_answer}
                            </p>
                          </div>
                        )}

                        {/* Admin Notes */}
                        {inq.admin_notes && (
                          <p style={{ margin: "8px 0 0", fontSize: 12, color: "var(--muted)" }}>
                            ملاحظة الأستاذ: {inq.admin_notes}
                          </p>
                        )}

                        {/* AI Suggested Answer */}
                        {inq.ai_suggested_answer && !inq.admin_answer && (
                          <div
                            style={{
                              background: "var(--paper)",
                              padding: "10px 14px",
                              borderRadius: 8,
                              marginTop: 8,
                              fontSize: 13,
                              color: "var(--muted)",
                            }}
                          >
                            <strong>إجابة مقترحة أولية من المساعد:</strong> {inq.ai_suggested_answer.slice(0, 150)}...
                          </div>
                        )}

                        <div style={{ marginTop: 12, fontSize: 11, color: "var(--muted)" }}>
                          تاريخ السؤال: {new Date(inq.created_at).toLocaleDateString("ar-EG")}
                          {inq.answered_at && ` · تم الرد: ${new Date(inq.answered_at).toLocaleDateString("ar-EG")}`}
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </section>
    </>
  );
}
