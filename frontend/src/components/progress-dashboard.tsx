"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { apiRequest } from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import {
  GraduationCapIcon,
  BookOpenIcon,
  ClockIcon,
  BrainIcon,
  TargetIcon,
  CheckCircleIcon,
  AlertCircleIcon,
  AwardIcon,
  ChevronLeftIcon,
  SparklesIcon,
} from "@/components/icons";

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
  if (level <= 2) return { title: "مستكشف واعد", color: "var(--muted)", bg: "var(--surface-raised)" };
  if (level <= 4) return { title: "متعلم نشط", color: "var(--green)", bg: "var(--mint)" };
  if (level <= 6) return { title: "محلل مفاهيمي", color: "var(--info)", bg: "var(--info-bg)" };
  if (level <= 8) return { title: "باحث متقدم", color: "var(--orange)", bg: "var(--orange-light)" };
  return { title: "عالم متفوق", color: "var(--warning)", bg: "var(--warning-bg)" };
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
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--paper)" }}>
      <AppHeader />
      <main className="shell" style={{ flex: 1, padding: "36px 24px 60px" }}>
        <div style={{ maxWidth: 960, margin: "0 auto" }}>
          {/* Header Title Section */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16, marginBottom: 28 }}>
            <div>
              <span className="eyebrow">
                <GraduationCapIcon size={15} />
                <span>ملف الطالب والتقييم الأكاديمي الذكي</span>
              </span>
              <h1 style={{ fontSize: "clamp(24px, 3.2vw, 36px)", margin: "4px 0 10px", fontWeight: 800 }}>
                تقييمك <span style={{ color: "var(--green)" }}>الأكاديمي والمستمر</span>
              </h1>
              <p style={{ margin: 0, color: "var(--muted)", fontSize: 15, maxWidth: 620, lineHeight: 1.7 }}>
                التقييم هنا مبني على أسس التعلم العميق: انتظام جلسات التركيز، دقة الاسترجاع النشط، وعمق التفاعل والاستفسار.
              </p>
            </div>

            <div
              className="badge"
              style={{
                padding: "8px 16px",
                borderRadius: 20,
                background: badge.bg,
                color: badge.color,
                fontSize: 14,
                border: "1px solid currentColor",
                gap: 8,
              }}
            >
              <AwardIcon size={16} />
              <span>{badge.title}</span>
            </div>
          </div>

          {loading && (
            <div className="card" style={{ padding: "40px 20px", textAlign: "center", color: "var(--muted)" }}>
              جارٍ تحميل التقييم الأكاديمي…
            </div>
          )}

          {!loading && error && (
            <div className="form-error" role="alert" style={{ display: "flex", alignItems: "center", gap: 8, margin: "20px 0" }}>
              <AlertCircleIcon size={18} />
              <span>{error}</span>
            </div>
          )}

          {!loading && !error && (
            <>
              {/* Navigation Tabs */}
              <div
                style={{
                  display: "flex",
                  gap: 10,
                  margin: "24px 0 24px",
                  borderBottom: "1px solid var(--line)",
                  paddingBottom: 8,
                }}
              >
                <button
                  type="button"
                  onClick={() => setActiveTab("evaluation")}
                  className={`btn ${activeTab === "evaluation" ? "btn-primary" : "btn-ghost"}`}
                  style={{ borderRadius: 8 }}
                >
                  <TargetIcon size={16} />
                  <span>التقييم ومؤشرات الاستيعاب</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("inquiries")}
                  className={`btn ${activeTab === "inquiries" ? "btn-primary" : "btn-ghost"}`}
                  style={{ borderRadius: 8, display: "inline-flex", alignItems: "center", gap: 8 }}
                >
                  <span>استفساراتي وأسئلتي المعلقة</span>
                  {inquiriesData.unread_count > 0 && (
                    <span className="badge badge-orange" style={{ fontSize: 11 }}>
                      {inquiriesData.unread_count} جديدة
                    </span>
                  )}
                </button>
              </div>

              {/* TAB 1: Evaluation by Deep Learning Principles */}
              {activeTab === "evaluation" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
                  {/* Skill Mastery Meter Card */}
                  <div className="card" style={{ padding: "28px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                      <div>
                        <span style={{ fontSize: 13, color: "var(--muted)", fontWeight: 600 }}>
                          مستوى إتقان واستيعاب الطالب
                        </span>
                        <h3 style={{ margin: "4px 0 0", fontSize: 20, color: "var(--ink)", fontWeight: 800 }}>
                          المستوى {skillLevel} من 10 · {dashboard?.level_description || "مستوى مبتدئ في بناء المفاهيم"}
                        </h3>
                      </div>
                      <div
                        style={{
                          fontSize: 32,
                          fontWeight: 800,
                          color: "var(--green)",
                        }}
                      >
                        {skillLevel * 10}%
                      </div>
                    </div>

                    {/* Progress Bar */}
                    <div
                      style={{
                        height: 12,
                        background: "var(--line)",
                        borderRadius: 6,
                        overflow: "hidden",
                        margin: "12px 0 16px",
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          width: `${(skillLevel / 10) * 100}%`,
                          background: "var(--green)",
                          borderRadius: 6,
                          transition: "width 0.5s ease",
                        }}
                      />
                    </div>

                    {/* Personalized Study Feedback */}
                    <div
                      style={{
                        background: "var(--surface-raised)",
                        borderRadius: 10,
                        padding: "16px 18px",
                        fontSize: 14,
                        lineHeight: 1.8,
                        color: "var(--ink)",
                        borderRight: "4px solid var(--green)",
                        display: "flex",
                        alignItems: "flex-start",
                        gap: 10,
                      }}
                    >
                      <div style={{ color: "var(--green)", marginTop: 2 }}>
                        <SparklesIcon size={18} />
                      </div>
                      <div>
                        <strong>توجيه ذكي لمستواك الحالي:</strong>{" "}
                        {skillLevel <= 3
                          ? "أنت في مرحلة التأسيس واستيعاب القواعد الأولى. يُنصح بالتركيز على الشروحات المبسطة وجلسات بومودورو القصيرة (25 دقيقة) وتفعيل الرسوم التوضيحية البصرية لتثبيت الصور الذهنية."
                          : skillLevel <= 6
                          ? "مستواك متقدم وتظهر قدرة ممتازة على ربط المفاهيم. ركّز على الاختبارات القصيرة والتأصيل النظري وطرح الأسئلة الاستنتاجية على المساعد الذكي."
                          : "أداء أكاديمي استثنائي! مساعدك الذكي الآن يخاطبك بلغة أكاديمية متعمقة ويركز على النقد والتحليل والمقارنات العلمية المتقدمة."}
                      </div>
                    </div>
                  </div>

                  {/* Core Principles Breakdown Grid */}
                  <div>
                    <h3 style={{ fontSize: 18, marginBottom: 16, fontWeight: 700 }}>ركائز التقييم الأكاديمي الحقيقي</h3>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
                      {/* Principle 1: Focus consistency */}
                      <div className="card" style={{ padding: "22px" }}>
                        <div style={{ width: 40, height: 40, borderRadius: 10, background: "var(--mint)", color: "var(--green)", display: "grid", placeItems: "center", marginBottom: 12 }}>
                          <ClockIcon size={20} />
                        </div>
                        <h4 style={{ margin: "0 0 6px", fontSize: 16 }}>انتظام جلسات التركيز</h4>
                        <p style={{ margin: "0 0 14px", fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
                          المذاكرة الموزعة المستمرة بدلاً من الحشو السريع غير المجدي.
                        </p>
                        <strong style={{ fontSize: 20, color: "var(--green)" }}>
                          {formatDuration(progress?.study_seconds || 0)}
                        </strong>
                      </div>

                      {/* Principle 2: Active Recall */}
                      <div className="card" style={{ padding: "22px" }}>
                        <div style={{ width: 40, height: 40, borderRadius: 10, background: "var(--mint)", color: "var(--green)", display: "grid", placeItems: "center", marginBottom: 12 }}>
                          <BrainIcon size={20} />
                        </div>
                        <h4 style={{ margin: "0 0 6px", fontSize: 16 }}>الاسترجاع النشط والتأكيد</h4>
                        <p style={{ margin: "0 0 14px", fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
                          مدى حل الأسئلة لتأكيد الفهم واسترجاع المعلومات من الذاكرة طويلة المدى.
                        </p>
                        <strong style={{ fontSize: 20, color: "var(--green)" }}>
                          {progress?.quiz_attempts || 0} محاولات اختبار
                        </strong>
                      </div>

                      {/* Principle 3: Inquiry & Critical Thinking */}
                      <div className="card" style={{ padding: "22px" }}>
                        <div style={{ width: 40, height: 40, borderRadius: 10, background: "var(--mint)", color: "var(--green)", display: "grid", placeItems: "center", marginBottom: 12 }}>
                          <TargetIcon size={20} />
                        </div>
                        <h4 style={{ margin: "0 0 6px", fontSize: 16 }}>عمق الفضول الأكاديمي</h4>
                        <p style={{ margin: "0 0 14px", fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
                          طرح التساؤلات والبحث وطلب الرسوم البصرية لتثبيت النقاط الغامضة.
                        </p>
                        <strong style={{ fontSize: 20, color: "var(--green)" }}>
                          {inquiriesData.inquiries.length} استفسار موجه
                        </strong>
                      </div>
                    </div>
                  </div>

                  {/* Per-Subject Breakdown */}
                  {progress && progress.subjects.length > 0 && (
                    <div>
                      <h3 style={{ fontSize: 18, marginBottom: 16, fontWeight: 700 }}>تفصيل الإنجاز حسب المواد</h3>
                      <div style={{ display: "grid", gap: 12 }}>
                        {progress.subjects.map((sub) => (
                          <div
                            key={sub.subject_id}
                            className="card card-hover"
                            style={{
                              padding: "18px 22px",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              flexWrap: "wrap",
                              gap: 14,
                            }}
                          >
                            <div>
                              <h4 style={{ margin: "0 0 4px", fontSize: 16 }}>{sub.subject_name}</h4>
                              <p style={{ margin: 0, fontSize: 12.5, color: "var(--muted)" }}>
                                {sub.last_studied_at
                                  ? `آخر جلسة مذاكرة: ${new Date(sub.last_studied_at).toLocaleDateString("ar-EG")}`
                                  : "لم تبدأ بعد"}
                              </p>
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                              <span style={{ fontSize: 13.5, color: "var(--green)", fontWeight: 700, display: "flex", alignItems: "center", gap: 6 }}>
                                <ClockIcon size={15} />
                                <span>{formatDuration(sub.study_seconds)}</span>
                              </span>
                              <Link
                                href={`/subjects/${sub.subject_id}`}
                                className="btn btn-secondary btn-sm"
                              >
                                <span>متابعة المذاكرة</span>
                                <ChevronLeftIcon size={14} />
                              </Link>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: Student Inquiries */}
              {activeTab === "inquiries" && (
                <div>
                  <p style={{ color: "var(--muted)", fontSize: 14, margin: "0 0 20px", lineHeight: 1.7 }}>
                    هنا تجد كل الأسئلة التي سألتها ولم تكن متوفرة مباشرة في مراجع المادة المرفوعة، وتم توجيهها لإدارة
                    المادة لمراجعتها واعتماد إجابتها رسمياً.
                  </p>

                  {inquiriesData.inquiries.length === 0 ? (
                    <div className="card" style={{ textAlign: "center", padding: "48px 20px" }}>
                      <div style={{ width: 48, height: 48, borderRadius: "50%", background: "var(--mint)", color: "var(--green)", display: "grid", placeItems: "center", margin: "0 auto 14px" }}>
                        <CheckCircleIcon size={24} />
                      </div>
                      <h3 style={{ margin: "0 0 6px", fontSize: 18 }}>لا توجد استفسارات معلقة حتى الآن</h3>
                      <p style={{ margin: 0, color: "var(--muted)", fontSize: 14 }}>
                        كل أسئلتك كانت متوفرة بدقة ضمن ملفات ومراجع مادتك، أو أنك لم تطرح أسئلة خارج نطاق المنهج بعد.
                      </p>
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                      {inquiriesData.inquiries.map((inq) => (
                        <article
                          key={inq.id}
                          className="card"
                          style={{
                            padding: "22px",
                            borderColor: inq.status === "approved" ? "var(--green)" : "var(--line)",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: 10,
                            }}
                          >
                            <span style={{ fontWeight: 700, color: "var(--green)", fontSize: 14, display: "flex", alignItems: "center", gap: 6 }}>
                              <BookOpenIcon size={16} />
                              <span>{inq.subject_name}</span>
                            </span>
                            <span
                              className={`badge ${
                                inq.status === "approved"
                                  ? "badge-mint"
                                  : inq.status === "rejected"
                                  ? "badge-orange"
                                  : "badge-neutral"
                              }`}
                            >
                              {inq.status === "approved"
                                ? "معتمد ومجاب من الإدارة"
                                : inq.status === "rejected"
                                ? "تم الرفض (خارج المنهج)"
                                : "قيد مراجعة الإدارة"}
                            </span>
                          </div>

                          {/* Question */}
                          <h4 style={{ margin: "8px 0 12px", fontSize: 16, color: "var(--ink)", lineHeight: 1.5 }}>
                            السؤال: «{inq.question}»
                          </h4>

                          {/* Admin Official Answer */}
                          {inq.admin_answer && (
                            <div
                              style={{
                                background: "var(--mint)",
                                borderRight: "4px solid var(--green)",
                                padding: "14px 18px",
                                borderRadius: 8,
                                marginTop: 12,
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
                            <p style={{ margin: "10px 0 0", fontSize: 12.5, color: "var(--muted)" }}>
                              ملاحظة الأستاذ: {inq.admin_notes}
                            </p>
                          )}

                          {/* AI Suggested Answer */}
                          {inq.ai_suggested_answer && !inq.admin_answer && (
                            <div
                              style={{
                                background: "var(--surface-raised)",
                                padding: "12px 16px",
                                borderRadius: 8,
                                marginTop: 10,
                                fontSize: 13,
                                color: "var(--muted)",
                              }}
                            >
                              <strong>إجابة مقترحة أولية من المساعد:</strong> {inq.ai_suggested_answer.slice(0, 150)}...
                            </div>
                          )}

                          <div style={{ marginTop: 14, fontSize: 11.5, color: "var(--muted)" }}>
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
        </div>
      </main>
    </div>
  );
}
