"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppHeader } from "@/components/app-header";
import { createClient } from "@/lib/supabase/client";
import { apiRequest } from "@/lib/api";
import {
  GraduationCapIcon,
  BookOpenIcon,
  SparklesIcon,
  ClockIcon,
  ShieldIcon,
  FolderIcon,
  ChartBarIcon,
} from "@/components/icons";

type UserProfile = {
  id: string;
  email: string | null;
  display_name: string | null;
  role: "student" | "admin";
  skill_level: number;
};

type SubjectItem = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
};

const MOTIVATIONAL_TIPS = [
  {
    quote: "«سر التفوق ليس في طول ساعات السهر، بل في عمق التركيز واسترجاع المفاهيم.»",
    tip: "استخدم تقنية الاسترجاع النشط (Active Recall) واختبر نفسك عبر تبويب «اختبر فهمك» لترسيخ المعلومات.",
    icon: "🎯",
    badge: "الاسترجاع النشط",
  },
  {
    quote: "«قسم المادة الكبيرة إلى أهداف صغيرة، وسترى الصعب يصبح سهلاً وممتعاً خطوة بخطوة.»",
    tip: "اطلب من رفيقك ومساعدك الذكي شرح المفاهيم المعقدة برسم توضيحي أو تشبيه من الحياة الواقعية.",
    icon: "💡",
    badge: "التفكيك الذكي",
  },
  {
    quote: "«الاستمرارية الهادئة تصنع المعجزات؛ ٢٥ دقيقة تركيز يومياً تصنع فارقاً تراكمياً هائلاً.»",
    tip: "اضبط مؤقت بومودورو للتركيز الآن واقضِ وقتاً نقياً مع درس واحد دون أي مشتتات.",
    icon: "⏱️",
    badge: "إدارة الوقت",
  },
  {
    quote: "«المعرفة التي تلخصها وتختبرها بنفسك ترسخ في الذاكرة بنسبة ٨٠٪ مقارنة بالقراءة العابرة.»",
    tip: "راجع البطاقات التعليمية (Flashcards) لتثبيت المصطلحات والقوانين الأساسية في دقائق معدودة.",
    icon: "🧠",
    badge: "تثبيت الذاكرة",
  },
  {
    quote: "«كل سؤال تطرحه اليوم يضيء لك فكرة غامضة؛ اسأل رفيقك الذكي دون أي تردد.»",
    tip: "لا يوجد سؤال بديهي في العلم؛ وإذا لم تجد الإجابة في مراجعك فستجيبك الإدارة فوراً.",
    icon: "🚀",
    badge: "الفضول الأكاديمي",
  },
];

export default function Home() {
  const [sessionUser, setSessionUser] = useState<UserProfile | null>(() => {
    if (typeof window !== "undefined") {
      try {
        const cached = localStorage.getItem("zaker_profile");
        if (cached) return JSON.parse(cached);
      } catch {}
    }
    return null;
  });
  const [subjects, setSubjects] = useState<SubjectItem[]>([]);
  const [loading, setLoading] = useState(() => {
    if (typeof window !== "undefined") {
      try {
        if (localStorage.getItem("zaker_profile")) return false;
      } catch {}
    }
    return true;
  });
  const [tipIndex, setTipIndex] = useState(0);

  // Rotate tips automatically every 7 seconds
  useEffect(() => {
    const timer = setInterval(() => {
      setTipIndex((prev) => (prev + 1) % MOTIVATIONAL_TIPS.length);
    }, 7000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let active = true;
    async function initHome() {
      try {
        const {
          data: { session },
        } = await createClient().auth.getSession();

        if (session && active) {
          const headers = { Authorization: `Bearer ${session.access_token}` };
          const [me, subjectsList] = await Promise.all([
            apiRequest<UserProfile>("/api/v1/auth/me", { headers }).catch(() => null),
            apiRequest<SubjectItem[]>("/api/v1/subjects", { headers }).catch(() => []),
          ]);

          if (active) {
            if (me) {
              setSessionUser(me);
              try {
                localStorage.setItem("zaker_profile", JSON.stringify(me));
              } catch {}
            }
            setSubjects(subjectsList);
          }
        } else {
          if (active) {
            setSessionUser(null);
            setSubjects([]);
            try {
              localStorage.removeItem("zaker_profile");
            } catch {}
          }
        }
      } catch {
        if (active) {
          setSessionUser(null);
          setSubjects([]);
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void initHome();
    return () => {
      active = false;
    };
  }, []);

  const activeTip = MOTIVATIONAL_TIPS[tipIndex];

  // While evaluating auth on very first unauthenticated visit, show graceful branded pulse
  if (loading && !sessionUser) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--paper)" }}>
        <AppHeader />
        <main
          className="shell"
          style={{
            flex: 1,
            padding: "80px 0",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 14,
                background: "var(--mint)",
                color: "var(--green)",
                display: "grid",
                placeItems: "center",
                fontSize: 24,
                animation: "pulseIcon 1.5s infinite ease-in-out",
              }}
            >
              🎓
            </div>
            <span style={{ fontSize: 14, color: "var(--muted)", fontWeight: 600 }}>
              جارٍ تهيئة مساحتك الدراسية في ذاكر معي…
            </span>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--paper)" }}>
      {/* Global Unified Header */}
      <AppHeader />

      <main className="shell" style={{ flex: 1, paddingBottom: 60 }}>
        {/* =========================================================================
            STATE 1: LOGGED-IN STUDENT WORKSPACE & MOTIVATION HUB
           ========================================================================= */}
        {sessionUser ? (
          <div style={{ paddingTop: 36, display: "flex", flexDirection: "column", gap: 36 }}>
            {/* Student Welcome Header Card */}
            <div
              style={{
                background: "linear-gradient(135deg, rgba(45, 106, 79, 0.08), rgba(216, 243, 220, 0.12))",
                border: "1px solid rgba(45, 106, 79, 0.25)",
                borderRadius: 22,
                padding: "32px 28px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: 20,
                boxShadow: "0 6px 20px rgba(0,0,0,0.03)",
              }}
            >
              <div>
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "4px 14px",
                    borderRadius: 20,
                    background: "rgba(45, 106, 79, 0.15)",
                    color: "var(--green)",
                    fontSize: 13,
                    fontWeight: 700,
                    marginBottom: 10,
                  }}
                >
                  <span>🎓</span>
                  <span>مساحتك الدراسية الذكية</span>
                </div>
                <h1
                  style={{
                    fontSize: "clamp(24px, 3vw, 36px)",
                    fontWeight: 800,
                    margin: "0 0 8px",
                    color: "var(--ink)",
                    lineHeight: 1.3,
                  }}
                >
                  أهلاً بك مجدداً،{" "}
                  <span style={{ color: "var(--green)" }}>
                    {sessionUser.display_name || sessionUser.email?.split("@")[0] || "يا بطل"}
                  </span>
                  ! 👋
                </h1>
                <p style={{ margin: 0, fontSize: 15, color: "var(--muted)", maxWidth: 560, lineHeight: 1.6 }}>
                  جاهز لجلسة مذاكرة واستيعاب جديدة اليوم؟ رفيقك الذكي مجهز بكافة كتبك ومذكراتك لشرح أي درس أو اختبار
                  فهمك.
                </p>
              </div>

              {/* Fast Action Buttons */}
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                <Link
                  href="/subjects"
                  className="session-start"
                  style={{
                    margin: 0,
                    padding: "13px 26px",
                    fontSize: 15,
                    borderRadius: 12,
                    fontWeight: 700,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    boxShadow: "0 4px 16px rgba(45, 106, 79, 0.25)",
                  }}
                >
                  <BookOpenIcon size={18} />
                  <span>🚀 ابدأ المذاكرة وتصفح المواد</span>
                </Link>

                <Link
                  href="/dashboard"
                  className="text-button"
                  style={{
                    padding: "12px 22px",
                    fontSize: 14.5,
                    borderRadius: 12,
                    border: "1.5px solid var(--green)",
                    background: "var(--surface)",
                    color: "var(--green)",
                    fontWeight: 700,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <ChartBarIcon size={18} />
                  <span>📊 إدارة ومتابعة تقدمي (صفحة الطالب)</span>
                </Link>
              </div>
            </div>

            {/* ROTATING MOTIVATIONAL QUOTE & SMART STUDY TIP (WITH SMOOTH ANIMATION) */}
            <section
              style={{
                background: "var(--surface)",
                border: "1px solid var(--line)",
                borderRadius: 20,
                padding: "26px 28px",
                boxShadow: "var(--shadow)",
                position: "relative",
                overflow: "hidden",
                transition: "all 0.3s ease",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 16,
                  borderBottom: "1px solid var(--line)",
                  paddingBottom: 12,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 22 }}>{activeTip.icon}</span>
                  <strong style={{ fontSize: 16, color: "var(--ink)" }}>محطة التحفيز اليومية</strong>
                  <span
                    style={{
                      fontSize: 11,
                      padding: "2px 10px",
                      borderRadius: 12,
                      background: "var(--mint)",
                      color: "var(--green)",
                      fontWeight: 700,
                    }}
                  >
                    {activeTip.badge}
                  </span>
                </div>

                {/* Tip Navigation Controls */}
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  {MOTIVATIONAL_TIPS.map((_, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setTipIndex(idx)}
                      style={{
                        width: tipIndex === idx ? 24 : 8,
                        height: 8,
                        borderRadius: 4,
                        border: 0,
                        background: tipIndex === idx ? "var(--green)" : "var(--line)",
                        cursor: "pointer",
                        transition: "all 0.3s ease",
                        padding: 0,
                      }}
                      title={`نصيحة ${idx + 1}`}
                    />
                  ))}
                </div>
              </div>

              {/* Animated Content Wrapper */}
              <div
                key={tipIndex}
                style={{
                  animation: "fadeIn 0.5s ease",
                  display: "flex",
                  flexDirection: "column",
                  gap: 10,
                }}
              >
                <blockquote
                  style={{
                    margin: 0,
                    fontSize: 17.5,
                    fontWeight: 700,
                    color: "var(--ink)",
                    lineHeight: 1.6,
                    fontStyle: "italic",
                  }}
                >
                  {activeTip.quote}
                </blockquote>
                <p
                  style={{
                    margin: 0,
                    fontSize: 14,
                    color: "var(--muted)",
                    lineHeight: 1.7,
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <span style={{ color: "var(--green)", fontWeight: 700 }}>💡 نصيحة المذاكرة:</span>
                  <span>{activeTip.tip}</span>
                </p>
              </div>
            </section>

            {/* ACTIVE SUBJECTS QUICK JUMP SECTION */}
            <section>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 16,
                }}
              >
                <div>
                  <h2 style={{ fontSize: 20, margin: "0 0 4px", fontWeight: 700, color: "var(--ink)" }}>
                    📚 موادك الدراسية النشطة ({subjects.length})
                  </h2>
                  <span style={{ fontSize: 13, color: "var(--muted)" }}>
                    استأنف شرح الدروس، أو راجع البطاقات والاختبارات التفاعلية بنقرة واحدة.
                  </span>
                </div>

                <Link
                  href="/subjects"
                  className="text-button"
                  style={{
                    fontSize: 13.5,
                    fontWeight: 600,
                    color: "var(--green)",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                  }}
                >
                  <span>عرض وإدارة جميع المواد</span>
                  <span>←</span>
                </Link>
              </div>

              {subjects.length === 0 ? (
                <div
                  style={{
                    background: "var(--surface)",
                    border: "1.5px dashed var(--line)",
                    borderRadius: 18,
                    padding: "40px 20px",
                    textAlign: "center",
                  }}
                >
                  <span style={{ fontSize: 40, display: "block", marginBottom: 12 }}>📖</span>
                  <h3 style={{ margin: "0 0 6px", fontSize: 17, color: "var(--ink)" }}>لم تضف أي مادة دراسية بعد</h3>
                  <p style={{ margin: "0 0 16px", fontSize: 13.5, color: "var(--muted)" }}>
                    أنشئ مادتك الأولى لتبدأ برفع الملازم، تفريغ المحاضرات الصوتية، والتفاعل مع رفيقك الذكي.
                  </p>
                  <Link
                    href="/subjects"
                    className="session-start"
                    style={{ margin: "0 auto", padding: "10px 22px", fontSize: 14 }}
                  >
                    ➕ إنشاء مادة جديدة وبدء المذاكرة
                  </Link>
                </div>
              ) : (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                    gap: 18,
                  }}
                >
                  {subjects.slice(0, 3).map((sub) => (
                    <div
                      key={sub.id}
                      style={{
                        background: "var(--surface)",
                        border: "1px solid var(--line)",
                        borderRadius: 16,
                        padding: "20px",
                        boxShadow: "var(--shadow)",
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "space-between",
                        gap: 14,
                        transition: "transform 0.2s, box-shadow 0.2s",
                      }}
                    >
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                          <span
                            style={{
                              width: 36,
                              height: 36,
                              borderRadius: 10,
                              background: "rgba(45, 106, 79, 0.12)",
                              color: "var(--green)",
                              display: "grid",
                              placeItems: "center",
                              fontSize: 16,
                            }}
                          >
                            📖
                          </span>
                          <h3
                            style={{
                              margin: 0,
                              fontSize: 16,
                              fontWeight: 700,
                              color: "var(--ink)",
                              lineHeight: 1.4,
                            }}
                          >
                            {sub.name}
                          </h3>
                        </div>
                        <p
                          style={{
                            margin: 0,
                            fontSize: 13,
                            color: "var(--muted)",
                            lineHeight: 1.6,
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                            overflow: "hidden",
                          }}
                        >
                          {sub.description || "مادة دراسية مجهزة بملفات الشرح والمساعد الذكي."}
                        </p>
                      </div>

                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          borderTop: "1px solid var(--line)",
                          paddingTop: 12,
                        }}
                      >
                        <Link
                          href={`/subjects/${sub.id}`}
                          className="session-start"
                          style={{
                            margin: 0,
                            padding: "6px 16px",
                            fontSize: 13,
                            fontWeight: 600,
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                          }}
                        >
                          <span>💬</span>
                          <span>محادثة الشرح</span>
                        </Link>

                        <Link
                          href={`/subjects/${sub.id}`}
                          className="text-button"
                          style={{ fontSize: 12.5, color: "var(--muted)" }}
                        >
                          المكتبة والاختبارات ←
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        ) : (
          /* =========================================================================
             STATE 2: GUEST / BEFORE LOGIN (HIGH-END PROFESSIONAL PRESENTATION HERO)
             ========================================================================= */
          <>
            {/* HERO SECTION */}
            <section
              style={{
                padding: "64px 0 48px",
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                gap: 48,
                alignItems: "center",
              }}
              className="hero-grid"
            >
              <div>
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "6px 16px",
                    borderRadius: 24,
                    background: "rgba(45, 106, 79, 0.1)",
                    color: "var(--green)",
                    fontSize: 13.5,
                    fontWeight: 700,
                    marginBottom: 22,
                    border: "1px solid rgba(45, 106, 79, 0.2)",
                  }}
                >
                  <SparklesIcon size={16} />
                  <span>رفيقك الأكاديمي الذكي الموثق من مراجعك الخاصة</span>
                </div>

                <h1
                  style={{
                    fontSize: "clamp(32px, 4.4vw, 52px)",
                    lineHeight: 1.35,
                    fontWeight: 900,
                    margin: "0 0 20px",
                    color: "var(--ink)",
                    letterSpacing: -0.3,
                  }}
                >
                  المذاكرة لم تعد معركة شاقة.
                  <br />
                  افهم أسرع، وتذكر أطول مع <span style={{ color: "var(--green)" }}>«ذاكر معي»</span>.
                </h1>

                <p
                  style={{
                    fontSize: 16.5,
                    lineHeight: 1.85,
                    color: "var(--muted)",
                    margin: "0 0 32px",
                    maxWidth: 540,
                  }}
                >
                  ارفع كتبك ومذكراتك وتسجيلات محاضراتك الصوتية، ودع رفيقك ومساعدك الذكي يشرح أصعب المسائل لك خطوة بخطوة،
                  مع رسوم توضيحية بصرية وجلسات بومودورو واختبارات تفاعلية مستندة لمراجعك فقط.
                </p>

                <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center" }}>
                  <Link
                    href="/login"
                    className="session-start"
                    style={{
                      margin: 0,
                      padding: "14px 32px",
                      fontSize: 16,
                      borderRadius: 12,
                      boxShadow: "0 8px 24px rgba(45, 106, 79, 0.25)",
                      fontWeight: 700,
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <BookOpenIcon size={18} />
                    <span>ابدأ المذاكرة وسجل الدخول الآن</span>
                  </Link>

                  <a
                    href="#how-it-works"
                    className="text-button"
                    style={{
                      padding: "13px 22px",
                      fontSize: 15,
                      borderRadius: 12,
                      border: "1px solid var(--line)",
                      background: "var(--surface)",
                      color: "var(--ink)",
                      fontWeight: 600,
                    }}
                  >
                    استكشف كيف تعمل المنصة
                  </a>
                </div>

                {/* Quick Value Badges */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                    gap: 12,
                    marginTop: 40,
                    paddingTop: 24,
                    borderTop: "1px solid var(--line)",
                  }}
                >
                  <div>
                    <strong style={{ fontSize: 20, color: "var(--green)", display: "block" }}>٣ أضعاف</strong>
                    <span style={{ fontSize: 12.5, color: "var(--muted)" }}>سرعة استيعاب المفاهيم</span>
                  </div>
                  <div>
                    <strong style={{ fontSize: 20, color: "var(--green)", display: "block" }}>٠٪ هلوسة</strong>
                    <span style={{ fontSize: 12.5, color: "var(--muted)" }}>شرح موثق من مراجعك</span>
                  </div>
                  <div>
                    <strong style={{ fontSize: 20, color: "var(--green)", display: "block" }}>تفريغ فوري</strong>
                    <span style={{ fontSize: 12.5, color: "var(--muted)" }}>للمحاضرات الصوتية</span>
                  </div>
                </div>
              </div>

              {/* Interactive Simulation Workstation Window */}
              <div
                style={{
                  background: "var(--surface)",
                  borderRadius: 22,
                  border: "1px solid var(--line)",
                  boxShadow: "var(--shadow)",
                  overflow: "hidden",
                  position: "relative",
                }}
              >
                {/* Window Mac Header Bar */}
                <div
                  style={{
                    padding: "12px 18px",
                    background: "var(--paper)",
                    borderBottom: "1px solid var(--line)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div style={{ display: "flex", gap: 7, alignItems: "center" }}>
                    <span
                      style={{
                        width: 11,
                        height: 11,
                        borderRadius: "50%",
                        background: "#ff5f56",
                        display: "inline-block",
                      }}
                    />
                    <span
                      style={{
                        width: 11,
                        height: 11,
                        borderRadius: "50%",
                        background: "#ffbd2e",
                        display: "inline-block",
                      }}
                    />
                    <span
                      style={{
                        width: 11,
                        height: 11,
                        borderRadius: "50%",
                        background: "#27c93f",
                        display: "inline-block",
                      }}
                    />
                  </div>
                  <span style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>
                    الفيزياء الكهرومغناطيسية · مادة دراسية
                  </span>
                  <span
                    style={{
                      fontSize: 11,
                      padding: "3px 8px",
                      borderRadius: 10,
                      background: "var(--mint)",
                      color: "var(--green)",
                      fontWeight: 700,
                    }}
                  >
                    مستوى 4
                  </span>
                </div>

                {/* Simulated Chat Feed */}
                <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
                  {/* Student message */}
                  <div
                    style={{
                      alignSelf: "flex-start",
                      background: "var(--green)",
                      color: "#fff",
                      padding: "10px 16px",
                      borderRadius: "14px 14px 4px 14px",
                      fontSize: 13.5,
                      maxWidth: "88%",
                      lineHeight: 1.6,
                    }}
                  >
                    اشرح لي قاعدة اليد اليمنى في المجال المغناطيسي بمخطط توضيحي بسيط.
                  </div>

                  {/* AI Companion response with SVG vector */}
                  <div
                    style={{
                      alignSelf: "flex-end",
                      background: "var(--paper)",
                      color: "var(--ink)",
                      padding: "14px 18px",
                      borderRadius: "14px 14px 14px 4px",
                      fontSize: 13,
                      border: "1px solid var(--line)",
                      maxWidth: "96%",
                      lineHeight: 1.7,
                    }}
                  >
                    <p style={{ margin: "0 0 10px" }}>
                      أهلاً بك! قاعدة اليد اليمنى تحدد اتجاه المجال المغناطيسي (B) حول سلك يمر به تيار كهربائي (I):
                    </p>

                    {/* SVG Vector Graphic */}
                    <div
                      style={{
                        background: "#ffffff",
                        borderRadius: 10,
                        padding: "10px 14px",
                        border: "1px solid var(--line)",
                        marginBottom: 8,
                      }}
                    >
                      <svg viewBox="0 0 340 110" style={{ width: "100%", height: "auto", display: "block" }}>
                        <line
                          x1="170"
                          y1="100"
                          x2="170"
                          y2="15"
                          stroke="#2d6a4f"
                          strokeWidth="5"
                          strokeLinecap="round"
                        />
                        <polygon points="170,8 164,22 176,22" fill="#2d6a4f" />
                        <text x="190" y="24" fill="#2d6a4f" fontSize="12" fontWeight="bold">
                          التيار (I ↑)
                        </text>

                        <ellipse
                          cx="170"
                          cy="55"
                          rx="75"
                          ry="24"
                          fill="none"
                          stroke="#e07a5f"
                          strokeWidth="2"
                          strokeDasharray="4 3"
                        />
                        <polygon points="245,55 240,48 244,62" fill="#e07a5f" />
                        <text x="255" y="60" fill="#e07a5f" fontSize="11" fontWeight="bold">
                          المجال (B ↻)
                        </text>

                        <ellipse
                          cx="170"
                          cy="75"
                          rx="55"
                          ry="18"
                          fill="none"
                          stroke="#52b788"
                          strokeWidth="1.5"
                          strokeDasharray="3 3"
                        />
                      </svg>
                    </div>

                    <small style={{ color: "var(--muted)", display: "block", fontSize: 11.5 }}>
                      [S1] ملزمة الفيزياء الحديثة — صفحة 64
                    </small>
                  </div>

                  {/* Active Pomodoro floating status */}
                  <div
                    style={{
                      padding: "9px 14px",
                      borderRadius: 12,
                      background: "rgba(224, 122, 95, 0.12)",
                      border: "1px solid var(--orange)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      fontSize: 12.5,
                    }}
                  >
                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <ClockIcon size={14} style={{ color: "var(--orange)" }} />
                      <span>جلسة تركيز جارية</span>
                    </span>
                    <strong style={{ color: "var(--orange)", direction: "ltr" }}>21:15 دقيقة متبقية</strong>
                  </div>
                </div>
              </div>
            </section>

            {/* FEATURES GRID */}
            <section style={{ padding: "60px 0 40px" }}>
              <div style={{ textAlign: "center", maxWidth: 640, margin: "0 auto 40px" }}>
                <span className="eyebrow">مميزات صُممت لراحتك وتفوقك</span>
                <h2 style={{ fontSize: 32, margin: "6px 0 12px", fontWeight: 800, color: "var(--ink)" }}>
                  كل ما تحتاجه لتذاكر <span>بأعلى كفاءة ومرونة</span>
                </h2>
                <p style={{ color: "var(--muted)", fontSize: 16 }}>
                  منصة «ذاكر معي» تحوّل ساعات المذاكرة المرهقة إلى جلسات تركيز ممتعة ومثمرة وموثقة من كتبك.
                </p>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                  gap: 20,
                }}
              >
                {[
                  {
                    icon: <BookOpenIcon size={24} />,
                    title: "مساعد يشرح من كتبك ومراجعك فقط",
                    desc: "لا مزيد من الإجابات العشوائية أو الهلوسة. المساعد الذكي يستند حصرياً إلى الكتب والمذكرات التي ترفعها ويستشهد بأرقام الصفحات.",
                  },
                  {
                    icon: <SparklesIcon size={24} />,
                    title: "تفريغ فوري للمحاضرات الصوتية",
                    desc: "ارفع تسجيلات المحاضرات بصيغة MP3 أو WAV، وتتحول لنصوص مشروحة يستخرج منها المساعد كافة التفاصيل.",
                  },
                  {
                    icon: <FolderIcon size={24} />,
                    title: "رسوم توضيحية ومخططات بصرية",
                    desc: "حوّل المفاهيم المعقدة إلى رسوم هندسية وخرائط مفاهيمية SVG واضحة تعزز الذاكرة البصرية وتثبت المعلومات بسهولة.",
                  },
                  {
                    icon: <ClockIcon size={24} />,
                    title: "جلسات تركيز بومودورو ذكية",
                    desc: "اختر مدة جلستك (15، 25، 45، أو 60 دقيقة) بضغطة زر مع مؤقت تفاعلي يحميك من التشتت ويحسب وقتك الفعلي.",
                  },
                  {
                    icon: <GraduationCapIcon size={24} />,
                    title: "تقييم أكاديمي حقيقي (مستويات 1-10)",
                    desc: "تقييم ذكي مبني على أسس التعلم: انتظام جلسات التركيز، عمق الفضول الأكاديمي، ودقة الاسترجاع، وليس مجرد عدّ الملفات.",
                  },
                  {
                    icon: <ShieldIcon size={24} />,
                    title: "إشراف أكاديمي مباشر وإشعارات فورية",
                    desc: "أي سؤال لا يغطيه منهجك يتم توجيهه لإدارة المادة لمراجعته واعتماد إجابته، مع إشعار فوري يظهر لك بمجرد الرد.",
                  },
                ].map((card, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: "var(--surface)",
                      borderRadius: 18,
                      padding: 24,
                      border: "1px solid var(--line)",
                      boxShadow: "var(--shadow)",
                      display: "flex",
                      flexDirection: "column",
                      gap: 12,
                    }}
                  >
                    <div
                      style={{
                        width: 44,
                        height: 44,
                        borderRadius: 12,
                        background: "rgba(45, 106, 79, 0.1)",
                        color: "var(--green)",
                        display: "grid",
                        placeItems: "center",
                      }}
                    >
                      {card.icon}
                    </div>
                    <h3 style={{ fontSize: 18, margin: "0", fontWeight: 700, color: "var(--ink)" }}>{card.title}</h3>
                    <p style={{ margin: 0, fontSize: 14, color: "var(--muted)", lineHeight: 1.7 }}>{card.desc}</p>
                  </div>
                ))}
              </div>
            </section>

            {/* HOW IT WORKS (3 SIMPLE STEPS) */}
            <section
              id="how-it-works"
              style={{
                background: "var(--surface)",
                borderRadius: 22,
                padding: "44px 32px",
                border: "1px solid var(--line)",
                margin: "20px 0 40px",
                boxShadow: "var(--shadow)",
              }}
            >
              <div style={{ textAlign: "center", marginBottom: 36 }}>
                <span className="eyebrow">سهولة وسلاسة لا مثيل لها</span>
                <h2 style={{ fontSize: 28, margin: "4px 0", fontWeight: 800, color: "var(--ink)" }}>
                  كيف تبدأ المذاكرة في 3 خطوات بسيطة؟
                </h2>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                  gap: 28,
                  textAlign: "center",
                }}
              >
                <div>
                  <div
                    style={{
                      width: 52,
                      height: 52,
                      borderRadius: "50%",
                      background: "var(--mint)",
                      color: "var(--green)",
                      display: "grid",
                      placeItems: "center",
                      fontSize: 20,
                      fontWeight: 800,
                      margin: "0 auto 16px",
                    }}
                  >
                    1
                  </div>
                  <h3 style={{ fontSize: 17, marginBottom: 8, fontWeight: 700, color: "var(--ink)" }}>
                    أنشئ مادتك وارفع مراجعك
                  </h3>
                  <p style={{ fontSize: 13.5, color: "var(--muted)", lineHeight: 1.7 }}>
                    أضف اسم المادة، وارفع ملازمك أو كتبك بصيغة PDF أو تسجيلات المحاضرات الصوتية وروابط YouTube.
                  </p>
                </div>

                <div>
                  <div
                    style={{
                      width: 52,
                      height: 52,
                      borderRadius: "50%",
                      background: "var(--mint)",
                      color: "var(--green)",
                      display: "grid",
                      placeItems: "center",
                      fontSize: 20,
                      fontWeight: 800,
                      margin: "0 auto 16px",
                    }}
                  >
                    2
                  </div>
                  <h3 style={{ fontSize: 17, marginBottom: 8, fontWeight: 700, color: "var(--ink)" }}>
                    تحاور مع رفيقك الذكي
                  </h3>
                  <p style={{ fontSize: 13.5, color: "var(--muted)", lineHeight: 1.7 }}>
                    اسأله في أي جزئية غامضة، واطلب منه تبسيط الشرح أو رسم مخططات توضيحية بصرية بالذكاء الاصطناعي.
                  </p>
                </div>

                <div>
                  <div
                    style={{
                      width: 52,
                      height: 52,
                      borderRadius: "50%",
                      background: "var(--mint)",
                      color: "var(--green)",
                      display: "grid",
                      placeItems: "center",
                      fontSize: 20,
                      fontWeight: 800,
                      margin: "0 auto 16px",
                    }}
                  >
                    3
                  </div>
                  <h3 style={{ fontSize: 17, marginBottom: 8, fontWeight: 700, color: "var(--ink)" }}>
                    عزز تركيزك وارتقِ بمستواك
                  </h3>
                  <p style={{ fontSize: 13.5, color: "var(--muted)", lineHeight: 1.7 }}>
                    اضبط جلسات بومودورو للتركيز، وتابع تقدمك الأكاديمي وصعودك في مستويات الإتقان (1-10).
                  </p>
                </div>
              </div>

              <div style={{ textAlign: "center", marginTop: 40 }}>
                <Link href="/login" className="session-start" style={{ padding: "14px 34px", fontSize: 16 }}>
                  ابدأ المذاكرة الآن مع «ذاكر معي»
                </Link>
              </div>
            </section>
          </>
        )}

        {/* SHARED FOOTER */}
        <footer
          style={{
            borderTop: "1px solid var(--line)",
            paddingTop: 24,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 12,
            fontSize: 13,
            color: "var(--muted)",
          }}
        >
          <div>
            <strong>ذاكر معي</strong> — منصة المذاكرة الذكية والتعلم المركز. جميع الحقوق محفوظة.
          </div>
          <div>خطوة صغيرة كل يوم تصنع تفوقاً كبيراً في مستقبلك.</div>
        </footer>
      </main>
    </div>
  );
}
