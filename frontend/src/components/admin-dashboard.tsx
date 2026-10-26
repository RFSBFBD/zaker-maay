"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { apiRequest } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { AppHeader } from "@/components/app-header";

type Analytics = {
  total_users: number;
  active_users_24h: number;
  active_users_7d: number;
  students_count: number;
  admins_count: number;
  total_subjects: number;
  total_resources: number;
  total_storage_bytes: number;
  total_study_sessions: number;
  total_quiz_attempts: number;
  total_study_artifacts: number;
  total_youtube_links: number;
  average_quiz_score: number;
  task_models: Record<string, string>;
};

type UserItem = {
  id: string;
  auth_user_id: string;
  email: string | null;
  display_name: string | null;
  role: "student" | "admin";
  skill_level: number;
  created_at: string;
  last_active_at: string | null;
  subjects_count: number;
  quizzes_count: number;
};

type AIConfig = {
  task_type: string;
  task_label: string;
  model_name: string;
  has_custom_api_key: boolean;
  temperature: number;
  max_output_tokens: number;
  is_active: boolean;
  description: string | null;
  updated_at: string | null;
};

type AdminInquiryItem = {
  id: string;
  subject_id: string;
  subject_name: string;
  student_id: string;
  student_email: string | null;
  student_name: string | null;
  question: string;
  ai_suggested_answer: string | null;
  status: "pending" | "approved" | "rejected";
  admin_answer: string | null;
  admin_notes: string | null;
  created_at: string;
  answered_at: string | null;
};

type AgentSkillItem = {
  id: string;
  title: string;
  description: string | null;
  source_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 بايت";
  const k = 1024;
  const sizes = ["بايت", "كيلوبايت", "ميغابايت", "غيغابايت"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "لم يسجل بعد";
  const date = new Date(iso);
  return date.toLocaleDateString("ar-EG", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getActiveStatus(iso: string | null): { label: string; className: string } {
  if (!iso) return { label: "غير نشط", className: "badge-inactive" };
  const diffHours = (Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60);
  if (diffHours < 1) return { label: "نشط الآن 🟢", className: "badge-active" };
  if (diffHours < 24) return { label: "نشط اليوم", className: "badge-active" };
  if (diffHours < 168) return { label: "خلال أسبوع", className: "badge-inactive" };
  return { label: "غير نشط", className: "badge-inactive" };
}

export function AdminDashboard() {
  const [tab, setTab] = useState<"analytics" | "users" | "ai" | "inquiries" | "skills">("analytics");
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [aiConfigs, setAiConfigs] = useState<AIConfig[]>([]);
  const [inquiries, setInquiries] = useState<AdminInquiryItem[]>([]);
  const [skills, setSkills] = useState<AgentSkillItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Inquiry Response state
  const [activeInquiry, setActiveInquiry] = useState<AdminInquiryItem | null>(null);
  const [adminAnswerInput, setAdminAnswerInput] = useState("");
  const [adminNotesInput, setAdminNotesInput] = useState("");

  // Skills GitHub Ingestion state
  const [githubUrlInput, setGithubUrlInput] = useState("");
  const [skillTitleInput, setSkillTitleInput] = useState("");
  const [ingestingSkill, setIngestingSkill] = useState(false);

  // Editing AI Config state
  const [editingConfig, setEditingConfig] = useState<AIConfig | null>(null);
  const [modelInput, setModelInput] = useState("");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [tempInput, setTempInput] = useState(0.2);
  const [tokensInput, setTokensInput] = useState(2000);
  const [descInput, setDescInput] = useState("");
  const [testResult, setTestResult] = useState<string | null>(null);

  const getHeaders = useCallback(async () => {
    const {
      data: { session },
      error: sessionError,
    } = await createClient().auth.getSession();
    if (sessionError || !session) throw new Error("انتهت الجلسة. سجّل الدخول مجدداً.");
    return { Authorization: `Bearer ${session.access_token}` };
  }, []);

  const loadData = useCallback(async () => {
    try {
      const headers = await getHeaders();
      const me = await apiRequest<{ id: string; email: string; role: string }>("/api/v1/auth/me", { headers });
      if (me.role !== "admin") {
        setError("⛔ عذراً، هذا المسار مخصص لمدير المنصة (Admin) فقط. لا تملك صلاحية الوصول. جاري تحويلك للصفحة الرئيسية...");
        setTimeout(() => {
          window.location.replace("/");
        }, 1500);
        return;
      }
      const [analyticsData, usersData, aiData, inqData, skillsData] = await Promise.all([
        apiRequest<Analytics>("/api/v1/admin/analytics", { headers }),
        apiRequest<UserItem[]>("/api/v1/admin/users", { headers }),
        apiRequest<AIConfig[]>("/api/v1/admin/ai-configs", { headers }),
        apiRequest<AdminInquiryItem[]>("/api/v1/inquiries/admin/all", { headers }).catch(() => []),
        apiRequest<AgentSkillItem[]>("/api/v1/admin/skills", { headers }).catch(() => []),
      ]);
      setAnalytics(analyticsData);
      setUsers(usersData);
      setAiConfigs(aiData);
      setInquiries(inqData);
      setSkills(skillsData);
      setError(null);
    } catch {
      setError("⛔ عذراً، لا تملك صلاحية مدير المنصة (Admin). جاري تحويلك للصفحة الرئيسية...");
      setTimeout(() => {
        window.location.replace("/");
      }, 1500);
    } finally {
      setLoading(false);
    }
  }, [getHeaders]);

  useEffect(() => {
    let mounted = true;
    void (async () => {
      if (mounted) {
        await loadData();
      }
    })();
    return () => {
      mounted = false;
    };
  }, [loadData]);

  async function handleRoleChange(user: UserItem) {
    const newRole = user.role === "admin" ? "student" : "admin";
    const confirmMsg =
      newRole === "admin"
        ? `هل تريد ترقية المستخدم (${user.email || user.id}) إلى مسؤول (Admin)؟`
        : `هل تريد تخفيض صلاحية (${user.email || user.id}) إلى طالب؟`;
    if (!window.confirm(confirmMsg)) return;

    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const headers = await getHeaders();
      const updated = await apiRequest<UserItem>(`/api/v1/admin/users/${user.id}/role`, {
        method: "PATCH",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ role: newRole }),
      });
      setUsers((prev) => prev.map((u) => (u.id === user.id ? updated : u)));
      setNotice(`تم تغيير دور المستخدم إلى ${newRole === "admin" ? "مسؤول" : "طالب"}.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر تعديل دور المستخدم.");
    } finally {
      setBusy(false);
    }
  }

  function startEditConfig(cfg: AIConfig) {
    setEditingConfig(cfg);
    setModelInput(cfg.model_name);
    setApiKeyInput("");
    setTempInput(cfg.temperature);
    setTokensInput(cfg.max_output_tokens);
    setDescInput(cfg.description || "");
    setTestResult(null);
  }

  async function handleSaveConfig(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingConfig) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const headers = await getHeaders();
      const updated = await apiRequest<AIConfig>(`/api/v1/admin/ai-configs/${editingConfig.task_type}`, {
        method: "PUT",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          model_name: modelInput.trim(),
          api_key: apiKeyInput.trim() || undefined,
          temperature: tempInput,
          max_output_tokens: tokensInput,
          description: descInput.trim() || undefined,
        }),
      });
      setAiConfigs((prev) => prev.map((c) => (c.task_type === updated.task_type ? updated : c)));
      setNotice(`تم تحديث إعدادات نموذج (${updated.task_label}) بنجاح.`);
      setEditingConfig(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر حفظ إعدادات النموذج.");
    } finally {
      setBusy(false);
    }
  }

  async function handleTestModel() {
    if (!modelInput.trim()) return;
    setBusy(true);
    setTestResult(null);
    try {
      const headers = await getHeaders();
      const res = await apiRequest<{ ok: boolean; model: string; message: string }>("/api/v1/admin/ai-configs/test", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          model_name: modelInput.trim(),
          api_key: apiKeyInput.trim() || undefined,
        }),
      });
      setTestResult(res.ok ? `✅ ${res.message}` : `❌ ${res.message}`);
    } catch (cause) {
      setTestResult(`❌ خطأ في الاختبار: ${cause instanceof Error ? cause.message : "تعذر الاتصال"}`);
    } finally {
      setBusy(false);
    }
  }

  async function handleRespondInquiry(status: "approved" | "rejected") {
    if (!activeInquiry) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const headers = await getHeaders();
      const updated = await apiRequest<AdminInquiryItem>(
        `/api/v1/inquiries/admin/${activeInquiry.id}/respond`,
        {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({
            status,
            admin_answer: adminAnswerInput.trim() || undefined,
            admin_notes: adminNotesInput.trim() || undefined,
          }),
        }
      );
      setInquiries((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setNotice(
        status === "approved"
          ? "✅ تم اعتماد إجابة السؤال وإشعار الطالب بها بنجاح!"
          : "❌ تم رفض السؤال وتنبيه الطالب."
      );
      setActiveInquiry(null);
      setAdminAnswerInput("");
      setAdminNotesInput("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر الرد على استفسار الطالب.");
    } finally {
      setBusy(false);
    }
  }

  async function handleIngestSkill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!githubUrlInput.trim()) return;
    setIngestingSkill(true);
    setError(null);
    setNotice(null);
    try {
      const headers = await getHeaders();
      const newSkill = await apiRequest<AgentSkillItem>("/api/v1/admin/skills/ingest-github", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          github_url: githubUrlInput.trim(),
          title: skillTitleInput.trim() || undefined,
        }),
      });
      setSkills((prev) => [newSkill, ...prev]);
      setGithubUrlInput("");
      setSkillTitleInput("");
      setNotice(`✅ تم استيراد مهارة «${newSkill.title}» بنجاح وإضافتها لطبقة معارف الوكيل الذكي!`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر استيراد المهارة من GitHub. تحقق من الرابط وصلاحية الوصول.");
    } finally {
      setIngestingSkill(false);
    }
  }

  async function handleToggleSkill(skill: AgentSkillItem) {
    setBusy(true);
    setError(null);
    try {
      const headers = await getHeaders();
      const updated = await apiRequest<AgentSkillItem>(`/api/v1/admin/skills/${skill.id}`, {
        method: "PATCH",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !skill.is_active }),
      });
      setSkills((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      setNotice(`تم ${updated.is_active ? "تفعيل" : "تعطيل"} مهارة «${updated.title}».`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر تغيير حالة المهارة.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteSkill(skill: AgentSkillItem) {
    if (!window.confirm(`هل أنت متأكد من حذف مهارة «${skill.title}» من معارف الوكيل؟`)) return;
    setBusy(true);
    setError(null);
    try {
      const headers = await getHeaders();
      await apiRequest(`/api/v1/admin/skills/${skill.id}`, {
        method: "DELETE",
        headers,
      });
      setSkills((prev) => prev.filter((s) => s.id !== skill.id));
      setNotice(`تم حذف مهارة «${skill.title}».`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر حذف المهارة.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <AppHeader />
      <div className="shell">
        <section className="subjects-content">
          <p className="eyebrow">🛡️ لوحة الإدارة والتحكم</p>
          <h1>
            إدارة <span>المنصة والذكاء الاصطناعي</span>
          </h1>
          <p className="intro">
            متابعة إحصاءات الاستخدام، الرد على أسئلة الطلاب المعلقة، وإدارة وتوزيع نماذج الذكاء الاصطناعي لتقليل التوكنز.
          </p>

          {loading && <p className="state-card" role="status">جارٍ التحقق من الصلاحيات وتحميل بيانات المنصة…</p>}
          {!loading && error && (
            <div
              className="state-card form-error"
              role="alert"
              style={{ textAlign: "center", padding: "32px 20px", borderRadius: 12 }}
            >
              <h2 style={{ color: "#9b3f32", margin: "0 0 10px", fontSize: 22 }}>⛔ صلاحيات الوصول غير كافية</h2>
              <p style={{ fontSize: 16, margin: "0 0 16px" }}>{error}</p>
              <Link href="/" className="session-start" style={{ display: "inline-block", margin: "0 auto" }}>
                العودة إلى الصفحة الرئيسية الآن
              </Link>
            </div>
          )}
          {!loading && notice && <p className="state-card form-notice" role="status">{notice}</p>}

          {!loading && !error && (
            <>
              {/* Tabs */}
              <div className="admin-tabs" role="tablist">
                <button
                  className={`admin-tab-btn ${tab === "analytics" ? "active" : ""}`}
                  onClick={() => setTab("analytics")}
                  type="button"
                >
                  📊 تحليلات المنصة والاستخدام
                </button>
                <button
                  className={`admin-tab-btn ${tab === "inquiries" ? "active" : ""}`}
                  onClick={() => setTab("inquiries")}
                  type="button"
                  style={{
                    color: inquiries.some((i) => i.status === "pending") ? "#d9534f" : undefined,
                    fontWeight: 700,
                  }}
                >
                  ❓ أسئلة الطلاب المعلقة ({inquiries.filter((i) => i.status === "pending").length})
                </button>
                <button
                  className={`admin-tab-btn ${tab === "users" ? "active" : ""}`}
                  onClick={() => setTab("users")}
                  type="button"
                >
                  👥 إدارة الطلاب والمستخدمين ({users.length})
                </button>
                <button
                  className={`admin-tab-btn ${tab === "ai" ? "active" : ""}`}
                  onClick={() => setTab("ai")}
                  type="button"
                >
                  ⚡ توجيه النماذج والـ API ({aiConfigs.length})
                </button>
                <button
                  className={`admin-tab-btn ${tab === "skills" ? "active" : ""}`}
                  onClick={() => setTab("skills")}
                  type="button"
                >
                  🧠 معارف ومهارات الوكيل ({skills.length})
                </button>
              </div>

              {/* TAB 1: ANALYTICS */}
              {tab === "analytics" && analytics && (
                <div>
                  <div className="admin-metrics-grid">
                    <article className="admin-metric-card">
                      <span>إجمالي الطلاب والمسؤولين</span>
                      <strong>{analytics.total_users}</strong>
                      <small>
                        {analytics.students_count} طالب · {analytics.admins_count} مسؤول
                      </small>
                    </article>
                    <article className="admin-metric-card">
                      <span>النشطون آخر 24 ساعة</span>
                      <strong>{analytics.active_users_24h}</strong>
                      <small>آخر 7 أيام: {analytics.active_users_7d}</small>
                    </article>
                    <article className="admin-metric-card">
                      <span>المواد الدراسية المنشأة</span>
                      <strong>{analytics.total_subjects}</strong>
                      <small>مواد فعالة للطلاب</small>
                    </article>
                    <article className="admin-metric-card">
                      <span>المصادر والملفات المرفوعة</span>
                      <strong>{analytics.total_resources}</strong>
                      <small>مساحة التخزين: {formatBytes(analytics.total_storage_bytes)}</small>
                    </article>
                    <article className="admin-metric-card">
                      <span>جلسات المذاكرة المنجزة</span>
                      <strong>{analytics.total_study_sessions}</strong>
                      <small>جلسات تركيز الطلاب</small>
                    </article>
                    <article className="admin-metric-card">
                      <span>محاولات حل الاختبارات</span>
                      <strong>{analytics.total_quiz_attempts}</strong>
                      <small>متوسط النجاح: {analytics.average_quiz_score}%</small>
                    </article>
                    <article className="admin-metric-card">
                      <span>روابط يوتيوب الدراسية</span>
                      <strong>{analytics.total_youtube_links}</strong>
                      <small>مقاطع تعليمية موثقة</small>
                    </article>
                    <article className="admin-metric-card">
                      <span>استفسارات الطلاب المعلقة</span>
                      <strong style={{ color: inquiries.some((i) => i.status === "pending") ? "#d9534f" : undefined }}>
                        {inquiries.filter((i) => i.status === "pending").length}
                      </strong>
                      <small>
                        نسبة الحل:{" "}
                        {inquiries.length > 0
                          ? Math.round(
                              ((inquiries.length - inquiries.filter((i) => i.status === "pending").length) /
                                inquiries.length) *
                                100
                            )
                          : 100}
                        %
                      </small>
                    </article>
                    <article className="admin-metric-card">
                      <span>مهارات الوكيل الذكي (GitHub)</span>
                      <strong>{skills.filter((s) => s.is_active).length}</strong>
                      <small>من إجمالي {skills.length} مهارات مفعلة</small>
                    </article>
                  </div>

                  <div className="upload-panel">
                    <h2>توزيع النماذج النشطة في الخلفية</h2>
                    <p className="privacy-note">
                      يقوم الـ Agent بتوزيع المهام تلقائياً على النماذج التالية لتقليل التكلفة واستهلاك التوكنز:
                    </p>
                    <div className="admin-ai-grid" style={{ marginTop: 12 }}>
                      {Object.entries(analytics.task_models).map(([task, model]) => (
                        <div key={task} className="admin-ai-card" style={{ padding: 14 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span style={{ fontWeight: 600 }}>{task}</span>
                            <span className="token-badge">{model}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: INQUIRIES REVIEW & RESPONSE */}
              {tab === "inquiries" && (
                <div>
                  <p className="intro" style={{ margin: "10px 0 20px" }}>
                    هنا تظهر أسئلة الطلاب التي وجهها المساعد الذكي للإدارة نظراً لعدم توفرها المباشر في المراجع المرفوعة.
                    يمكنك اعتماد وإضافة إجابة معتمدة، أو رفض السؤال إذا كان خارج المنهج.
                  </p>

                  {/* Response Modal / Box if an inquiry is selected */}
                  {activeInquiry && (
                    <section
                      className="upload-panel"
                      style={{
                        background: "var(--paper)",
                        border: "2px solid var(--green)",
                        marginBottom: 24,
                      }}
                    >
                      <h3 style={{ margin: "0 0 10px", fontSize: 18 }}>
                        ✍️ الرد على استفسار الطالب في مادة «{activeInquiry.subject_name}»
                      </h3>
                      <p style={{ margin: "0 0 10px", fontSize: 13, color: "var(--muted)" }}>
                        الطالب: {activeInquiry.student_email || activeInquiry.student_name || "طالب"} · تاريخ السؤال:{" "}
                        {formatDate(activeInquiry.created_at)}
                      </p>
                      <div
                        style={{
                          padding: "12px 16px",
                          background: "#fff",
                          borderRadius: 8,
                          marginBottom: 14,
                          border: "1px solid var(--line)",
                        }}
                      >
                        <strong style={{ display: "block", fontSize: 13, color: "var(--muted)" }}>
                          نص سؤال الطالب:
                        </strong>
                        <p style={{ margin: "4px 0 0", fontSize: 15, fontWeight: 600 }}>{activeInquiry.question}</p>
                      </div>

                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          void handleRespondInquiry("approved");
                        }}
                      >
                        <label style={{ display: "block", marginBottom: 6, fontWeight: 600, fontSize: 14 }}>
                          الإجابة الرسمية المعتمدة (ستصل للطالب في إشعاراته فوراً):
                        </label>
                        <textarea
                          rows={4}
                          required
                          value={adminAnswerInput}
                          onChange={(e) => setAdminAnswerInput(e.target.value)}
                          placeholder="اكتب الإجابة التعليمية المعتمدة هنا لتظهر للطالب في لوحته وإشعاراته…"
                          style={{
                            width: "100%",
                            padding: "12px",
                            borderRadius: 8,
                            border: "1px solid var(--line)",
                            background: "#fff",
                            font: "inherit",
                            fontSize: 14,
                            marginBottom: 12,
                          }}
                        />

                        <label style={{ display: "block", marginBottom: 6, fontWeight: 600, fontSize: 13 }}>
                          ملاحظة إضافية للطالب (اختياري):
                        </label>
                        <input
                          type="text"
                          value={adminNotesInput}
                          onChange={(e) => setAdminNotesInput(e.target.value)}
                          placeholder="مثال: يرجى مراجعة الفصل الثالث لمزيد من التفاصيل"
                          style={{
                            width: "100%",
                            padding: "10px 12px",
                            borderRadius: 8,
                            border: "1px solid var(--line)",
                            background: "#fff",
                            font: "inherit",
                            fontSize: 13,
                            marginBottom: 16,
                          }}
                        />

                        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                          <button
                            type="submit"
                            disabled={busy || !adminAnswerInput.trim()}
                            className="session-start"
                            style={{
                              margin: 0,
                              background: "var(--green)",
                              color: "#fff",
                              padding: "10px 20px",
                            }}
                          >
                            {busy ? "جارٍ الإرسال…" : "✅ اعتماد وإرسال الإجابة الرسمية للطالب"}
                          </button>

                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => void handleRespondInquiry("rejected")}
                            className="session-start"
                            style={{
                              margin: 0,
                              background: "#d9534f",
                              borderColor: "#d9534f",
                              color: "#fff",
                              padding: "10px 20px",
                            }}
                          >
                            ❌ رفض السؤال (خارج نطاق المقرر)
                          </button>

                          <button
                            type="button"
                            className="text-button"
                            onClick={() => setActiveInquiry(null)}
                          >
                            إلغاء
                          </button>
                        </div>
                      </form>
                    </section>
                  )}

                  {inquiries.length === 0 ? (
                    <p className="state-card">لا توجد أي أسئلة معلقة من الطلاب حالياً. كافّة الأسئلة مستوفاة! 🎉</p>
                  ) : (
                    <div className="admin-table-container">
                      <table className="admin-table">
                        <thead>
                          <tr>
                            <th>المادة الدراسية</th>
                            <th>الطالب</th>
                            <th>السؤال</th>
                            <th>الحالة</th>
                            <th>تاريخ السؤال</th>
                            <th>الإجراء</th>
                          </tr>
                        </thead>
                        <tbody>
                          {inquiries.map((inq) => (
                            <tr key={inq.id}>
                              <td>
                                <strong>{inq.subject_name}</strong>
                              </td>
                              <td>
                                <span style={{ fontSize: 13 }}>{inq.student_email || inq.student_name || "طالب"}</span>
                              </td>
                              <td style={{ maxWidth: 300 }}>
                                <p style={{ margin: 0, fontSize: 13, overflowWrap: "anywhere" }}>{inq.question}</p>
                                {inq.admin_answer && (
                                  <small style={{ color: "var(--green)", display: "block", marginTop: 4 }}>
                                    ✓ تمت الإجابة: {inq.admin_answer.slice(0, 60)}...
                                  </small>
                                )}
                              </td>
                              <td>
                                <span
                                  className={`badge-role ${
                                    inq.status === "approved"
                                      ? "badge-admin"
                                      : inq.status === "rejected"
                                      ? "badge-student"
                                      : "badge-student"
                                  }`}
                                  style={{
                                    color:
                                      inq.status === "approved"
                                        ? "#2a7e43"
                                        : inq.status === "rejected"
                                        ? "#9b3f32"
                                        : "#b45309",
                                    background:
                                      inq.status === "approved"
                                        ? "#e7f0e5"
                                        : inq.status === "rejected"
                                        ? "#fff0ed"
                                        : "#fff8ec",
                                  }}
                                >
                                  {inq.status === "approved"
                                    ? "معتمد ومجاب"
                                    : inq.status === "rejected"
                                    ? "مرفوض"
                                    : "قيد الانتظار ⏳"}
                                </span>
                              </td>
                              <td>{formatDate(inq.created_at)}</td>
                              <td>
                                <button
                                  className="session-start"
                                  style={{ margin: 0, padding: "5px 12px", fontSize: 12 }}
                                  onClick={() => {
                                    setActiveInquiry(inq);
                                    setAdminAnswerInput(inq.admin_answer || inq.ai_suggested_answer || "");
                                    setAdminNotesInput(inq.admin_notes || "");
                                  }}
                                >
                                  {inq.status === "pending" ? "مراجعة والرد" : "تعديل الرد"}
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: USERS MANAGEMENT */}
              {tab === "users" && (
                <div>
                  <div className="upload-panel" style={{ margin: "0 0 20px" }}>
                    <h2>إدارة الحسابات وصلاحيات الوصول</h2>
                    <p className="privacy-note">
                      يمكنك متابعة نشاط الدخول الفعلي وتغيير رتبة المستخدمين بين (طالب) و(مسؤول).
                    </p>
                  </div>

                  <div className="admin-table-container">
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>المستخدم</th>
                          <th>الدور / الصلاحية</th>
                          <th>حالة النشاط</th>
                          <th>آخر ظهور</th>
                          <th>تاريخ الانضمام</th>
                          <th>المواد المنشأة</th>
                          <th>الاختبارات</th>
                          <th>الإجراء</th>
                        </tr>
                      </thead>
                      <tbody>
                        {users.map((u) => {
                          const status = getActiveStatus(u.last_active_at);
                          return (
                            <tr key={u.id}>
                              <td>
                                <strong>{u.email || "بدون بريد"}</strong>
                                {u.display_name && <small style={{ display: "block" }}>{u.display_name}</small>}
                              </td>
                              <td>
                                <span className={`badge-role ${u.role === "admin" ? "badge-admin" : "badge-student"}`}>
                                  {u.role === "admin" ? "مسؤول (Admin)" : "طالب (Student)"}
                                </span>
                              </td>
                              <td>
                                <span className={status.className}>{status.label}</span>
                              </td>
                              <td>{formatDate(u.last_active_at)}</td>
                              <td>{formatDate(u.created_at)}</td>
                              <td>{u.subjects_count}</td>
                              <td>{u.quizzes_count}</td>
                              <td>
                                <button
                                  className="text-button"
                                  style={{ fontSize: 13 }}
                                  disabled={busy}
                                  onClick={() => void handleRoleChange(u)}
                                >
                                  {u.role === "admin" ? "تخفيض لطالب" : "ترقية لمسؤول"}
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* TAB 4: AI MODELS CONFIG */}
              {tab === "ai" && (
                <div>
                  <div className="upload-panel" style={{ margin: "0 0 20px" }}>
                    <h2>إدارة وتوزيع نماذج الذكاء الاصطناعي (AI Router)</h2>
                    <p className="privacy-note">
                      لكل مهمة داخل المنصة يمكنك تعيين نموذج Gemini مختلف ومفتاح API مخصص وحدود توكنز للتحكم الكامل في
                      الجودة والتكلفة.
                    </p>
                  </div>

                  {editingConfig && (
                    <section className="upload-panel" style={{ border: "2px solid var(--green)", marginBottom: 24 }}>
                      <h3 style={{ margin: "0 0 10px" }}>تعديل مهمة: {editingConfig.task_label}</h3>
                      <form onSubmit={handleSaveConfig} style={{ display: "grid", gap: 12 }}>
                        <div>
                          <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>اسم النموذج (Model):</label>
                          <input
                            required
                            value={modelInput}
                            onChange={(e) => setModelInput(e.target.value)}
                            placeholder="مثال: gemini-3.5-flash, gemini-3.5-flash-lite"
                            style={{
                              width: "100%",
                              padding: "10px",
                              border: "1px solid var(--line)",
                              borderRadius: 6,
                            }}
                          />
                        </div>

                        <div>
                          <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>
                            مفتاح Gemini API خاص (اختياري - اتركه فارغاً للاعتماد على المفتاح العام):
                          </label>
                          <input
                            type="password"
                            value={apiKeyInput}
                            onChange={(e) => setApiKeyInput(e.target.value)}
                            placeholder={editingConfig.has_custom_api_key ? "مفتاح خاص مُعيّن حالياً" : "المفتاح العام للمنصة"}
                            style={{
                              width: "100%",
                              padding: "10px",
                              border: "1px solid var(--line)",
                              borderRadius: 6,
                            }}
                          />
                        </div>

                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                          <div>
                            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>
                              درجة الحرارة (Temperature: 0.0 إلى 1.0):
                            </label>
                            <input
                              type="number"
                              step="0.05"
                              min="0"
                              max="1"
                              value={tempInput}
                              onChange={(e) => setTempInput(Number(e.target.value))}
                              style={{
                                width: "100%",
                                padding: "10px",
                                border: "1px solid var(--line)",
                                borderRadius: 6,
                              }}
                            />
                          </div>

                          <div>
                            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>
                              الحد الأقصى للتوكنز (Max Tokens):
                            </label>
                            <input
                              type="number"
                              min="100"
                              max="16000"
                              value={tokensInput}
                              onChange={(e) => setTokensInput(Number(e.target.value))}
                              style={{
                                width: "100%",
                                padding: "10px",
                                border: "1px solid var(--line)",
                                borderRadius: 6,
                              }}
                            />
                          </div>
                        </div>

                        <div>
                          <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>وصف المهمة:</label>
                          <input
                            value={descInput}
                            onChange={(e) => setDescInput(e.target.value)}
                            style={{
                              width: "100%",
                              padding: "10px",
                              border: "1px solid var(--line)",
                              borderRadius: 6,
                            }}
                          />
                        </div>

                        {testResult && (
                          <p
                            style={{
                              padding: "8px 12px",
                              borderRadius: 6,
                              background: testResult.startsWith("✅") ? "#e7f0e5" : "#fff0ed",
                              fontSize: 13,
                              margin: "4px 0",
                            }}
                          >
                            {testResult}
                          </p>
                        )}

                        <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
                          <button className="session-start" type="submit" disabled={busy}>
                            {busy ? "جارٍ الحفظ…" : "حفظ التعديلات"}
                          </button>
                          <button
                            type="button"
                            className="session-start"
                            style={{ margin: 0 }}
                            onClick={() => void handleTestModel()}
                            disabled={busy || !modelInput.trim()}
                          >
                            اختبار اتصال النموذج الآن
                          </button>
                          <button
                            type="button"
                            className="text-button"
                            onClick={() => setEditingConfig(null)}
                          >
                            إلغاء
                          </button>
                        </div>
                      </form>
                    </section>
                  )}

                  <div className="admin-ai-grid">
                    {aiConfigs.map((cfg) => (
                      <article className="admin-ai-card" key={cfg.task_type}>
                        <h3>
                          <span>{cfg.task_label}</span>
                          <span className="token-badge">{cfg.model_name}</span>
                        </h3>
                        <p>{cfg.description || "تكوين مخصص لمعالجة هذه المهمة بالباك إند."}</p>

                        <div className="admin-ai-meta">
                          <div>
                            <span>نوع المهمة:</span>
                            <strong>{cfg.task_type}</strong>
                          </div>
                          <div>
                            <span>مفتاح API:</span>
                            <strong>{cfg.has_custom_api_key ? "مفتاح خاص 🔑" : "المفتاح العام"}</strong>
                          </div>
                          <div>
                            <span>درجة الحرارة (Temp):</span>
                            <strong>{cfg.temperature}</strong>
                          </div>
                          <div>
                            <span>حد التوكنز:</span>
                            <strong>{cfg.max_output_tokens}</strong>
                          </div>
                        </div>

                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginTop: 8,
                          }}
                        >
                          <span style={{ fontSize: 12, color: "var(--muted)" }}>
                            {cfg.updated_at ? `آخر تحديث: ${formatDate(cfg.updated_at)}` : "إعداد افتراضي"}
                          </span>
                          <button
                            className="session-start"
                            style={{ margin: 0, padding: "6px 14px" }}
                            onClick={() => startEditConfig(cfg)}
                          >
                            تعديل النموذج / الـ API
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              )}

              {/* TAB 5: AGENT SKILLS & GITHUB INGESTION */}
              {tab === "skills" && (
                <div>
                  <p className="intro" style={{ margin: "10px 0 20px" }}>
                    زوّد الوكيل الذكي بمهارات تدريسية واستراتيجيات شرح متقدمة مستوردة مباشرة من مستودعات GitHub، مع نظام
                    التعلم الذاتي المستمر من إجابات الإدارة السابقة.
                  </p>

                  {/* GitHub Ingestion Form */}
                  <section
                    className="upload-panel"
                    style={{
                      background: "var(--paper)",
                      border: "2px dashed var(--green)",
                      marginBottom: 24,
                    }}
                  >
                    <h3 style={{ margin: "0 0 10px", fontSize: 18, color: "var(--ink)" }}>
                      📥 استيراد وتدريب مهارة جديدة من GitHub
                    </h3>
                    <p style={{ fontSize: 13, color: "var(--muted)", margin: "0 0 14px" }}>
                      أدخل رابط ملف المهارة (Markdown / Text) على GitHub مثل ملف README أو SKILL.md ليقوم النظام بتحليله
                      وحقنه في توجيهات المساعد الذكي.
                    </p>
                    <form onSubmit={handleIngestSkill} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                      <div>
                        <label style={{ display: "block", marginBottom: 6, fontWeight: 600, fontSize: 13 }}>
                          رابط الملف على GitHub (GitHub File URL):
                        </label>
                        <input
                          type="url"
                          required
                          placeholder="https://github.com/owner/repo/blob/main/skills/socratic_method.md"
                          value={githubUrlInput}
                          onChange={(e) => setGithubUrlInput(e.target.value)}
                          style={{
                            width: "100%",
                            padding: "10px 14px",
                            border: "1px solid var(--line)",
                            borderRadius: 8,
                            fontSize: 14,
                            direction: "ltr",
                            fontFamily: "monospace",
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ display: "block", marginBottom: 6, fontWeight: 600, fontSize: 13 }}>
                          عنوان المهارة (اختياري - يتم استخراجه تلقائياً إن تُرِك فارغاً):
                        </label>
                        <input
                          type="text"
                          placeholder="مثال: أسلوب الحوار السقراطي للتبسيط"
                          value={skillTitleInput}
                          onChange={(e) => setSkillTitleInput(e.target.value)}
                          style={{
                            width: "100%",
                            padding: "10px 14px",
                            border: "1px solid var(--line)",
                            borderRadius: 8,
                            fontSize: 14,
                          }}
                        />
                      </div>
                      <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
                        <button
                          type="submit"
                          className="session-start"
                          disabled={ingestingSkill || !githubUrlInput.trim()}
                          style={{ margin: 0, padding: "10px 24px" }}
                        >
                          {ingestingSkill ? "جارٍ جلب المهارة وتدريب الوكيل…" : "🚀 استيراد وحقن المهارة"}
                        </button>
                      </div>
                    </form>
                  </section>

                  {/* Continuous Self-Learning Card */}
                  <div
                    style={{
                      background: "rgba(100, 140, 90, 0.08)",
                      border: "1px solid var(--green)",
                      borderRadius: 12,
                      padding: "16px 20px",
                      marginBottom: 24,
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 14,
                    }}
                  >
                    <span style={{ fontSize: 28 }}>💡</span>
                    <div>
                      <strong style={{ display: "block", fontSize: 15, marginBottom: 4, color: "var(--ink)" }}>
                        حلقة التعلم والتطوير الذاتي للوكيل (Continuous Self-Learning Loop)
                      </strong>
                      <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: "var(--muted)" }}>
                        الوكيل الذكي يتعلم باستمرار من الإدارة: كل إجابة تقوم باعتمادها في تبويب «أسئلة الطلاب المعلقة»
                        تُحقن تلقائياً في موجه النظام (System Instructions) كأمثلة تعليمية مرجعية (Few-Shot Reference
                        Examples)، مما يكسب الوكيل المعرفة التراكمية لطريقة الإجابة الدقيقة دون الحاجة لإعادة تدريب.
                      </p>
                    </div>
                  </div>

                  {/* Skills List */}
                  <h3 style={{ fontSize: 18, margin: "20px 0 12px" }}>
                    المهارات المحقونة حالياً ({skills.length}):
                  </h3>

                  {skills.length === 0 ? (
                    <p className="state-card">لم يتم استيراد مهارات خارجية بعد. أضف أول مهارة من النموذج أعلاه.</p>
                  ) : (
                    <div className="admin-ai-grid">
                      {skills.map((skill) => (
                        <article
                          key={skill.id}
                          className="admin-ai-card"
                          style={{
                            borderLeft: skill.is_active ? "4px solid var(--green)" : "4px solid var(--line)",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                            <h3 style={{ margin: 0, fontSize: 16 }}>
                              <span>{skill.title}</span>
                            </h3>
                            <span
                              style={{
                                fontSize: 11,
                                padding: "3px 8px",
                                borderRadius: 12,
                                fontWeight: 700,
                                background: skill.is_active ? "#e7f0e5" : "#f0f0f0",
                                color: skill.is_active ? "#2e6930" : "#777",
                              }}
                            >
                              {skill.is_active ? "نشطة ومحقونة 🟢" : "معطلة مؤقتاً ⚪"}
                            </span>
                          </div>

                          <p style={{ fontSize: 13, color: "var(--muted)", margin: "8px 0" }}>
                            {skill.description || "مهارة تعليمية مستوردة من GitHub."}
                          </p>

                          {skill.source_url && (
                            <div style={{ fontSize: 12, margin: "6px 0" }}>
                              <a
                                href={skill.source_url}
                                target="_blank"
                                rel="noreferrer"
                                style={{ color: "var(--green)", textDecoration: "underline" }}
                              >
                                🔗 عرض المصدر على GitHub
                              </a>
                            </div>
                          )}

                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginTop: 14,
                              paddingTop: 10,
                              borderTop: "1px solid var(--line)",
                            }}
                          >
                            <span style={{ fontSize: 11, color: "var(--muted)" }}>
                              {formatDate(skill.created_at)}
                            </span>
                            <div style={{ display: "flex", gap: 8 }}>
                              <button
                                type="button"
                                className="session-start"
                                style={{
                                  margin: 0,
                                  padding: "5px 12px",
                                  fontSize: 12,
                                  background: skill.is_active ? "#f5f5f5" : "var(--green)",
                                  color: skill.is_active ? "#333" : "#fff",
                                }}
                                onClick={() => void handleToggleSkill(skill)}
                                disabled={busy}
                              >
                                {skill.is_active ? "تعطيل" : "تفعيل"}
                              </button>
                              <button
                                type="button"
                                className="text-button"
                                style={{
                                  color: "#9b3f32",
                                  fontSize: 12,
                                  padding: "4px 8px",
                                }}
                                onClick={() => void handleDeleteSkill(skill)}
                                disabled={busy}
                              >
                                حذف
                              </button>
                            </div>
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
      </div>
    </>
  );
}
