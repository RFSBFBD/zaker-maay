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
  TargetIcon,
  LightbulbIcon,
  BrainIcon,
  RocketIcon,
  BotIcon,
  ChevronLeftIcon,
  CheckCircleIcon,
  LayersIcon,
  WandIcon,
  UserIcon,
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
    icon: <TargetIcon size={20} />,
    badge: "الاسترجاع النشط",
  },
  {
    quote: "«قسم المادة الكبيرة إلى أهداف صغيرة، وسترى الصعب يصبح سهلاً وممتعاً خطوة بخطوة.»",
    tip: "اطلب من رفيقك ومساعدك الذكي شرح المفاهيم المعقدة برسم توضيحي أو تشبيه من الحياة الواقعية.",
    icon: <LightbulbIcon size={20} />,
    badge: "التفكيك الذكي",
  },
  {
    quote: "«الاستمرارية الهادئة تصنع المعجزات؛ ٢٥ دقيقة تركيز يومياً تصنع فارقاً تراكمياً هائلاً.»",
    tip: "اضبط مؤقت بومودورو للتركيز الآن واقضِ وقتاً نقياً مع درس واحد دون أي مشتتات.",
    icon: <ClockIcon size={20} />,
    badge: "إدارة الوقت",
  },
  {
    quote: "«المعرفة التي تلخصها وتختبرها بنفسك ترسخ في الذاكرة بنسبة ٨٠٪ مقارنة بالقراءة العابرة.»",
    tip: "راجع البطاقات التعليمية (Flashcards) لتثبيت المصطلحات والقوانين الأساسية في دقائق معدودة.",
    icon: <BrainIcon size={20} />,
    badge: "تثبيت الذاكرة",
  },
  {
    quote: "«كل سؤال تطرحه اليوم يضيء لك فكرة غامضة؛ اسأل رفيقك الذكي دون أي تردد.»",
    tip: "لا يوجد سؤال بديهي في العلم؛ وإذا لم تجد الإجابة في مراجعك فستجيبك الإدارة فوراً.",
    icon: <RocketIcon size={20} />,
    badge: "الفضول الأكاديمي",
  },
];

export default function Home() {
  const [sessionUser, setSessionUser] = useState<UserProfile | null>(null);
  const [subjects, setSubjects] = useState<SubjectItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isMounted, setIsMounted] = useState(false);
  const [tipIndex, setTipIndex] = useState(0);

  // Rotate tips automatically every 8 seconds
  useEffect(() => {
    const timer = setInterval(() => {
      setTipIndex((prev) => (prev + 1) % MOTIVATIONAL_TIPS.length);
    }, 8000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    setIsMounted(true);
    let active = true;

    // Fast-path: immediately read cached profile on client to avoid layout shifts
    try {
      const cached = localStorage.getItem("zaker_profile");
      if (cached) {
        const parsed = JSON.parse(cached);
        if (parsed && parsed.id) {
          setSessionUser(parsed);
          setLoading(false);
        }
      }
    } catch {}

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

  // Clean loading state with zero layout shift
  if (!isMounted || (loading && !sessionUser)) {
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
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 12,
                background: "var(--mint)",
                color: "var(--green)",
                display: "grid",
                placeItems: "center",
                animation: "pulseIcon 1.5s infinite ease-in-out",
              }}
            >
              <GraduationCapIcon size={24} />
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
            STATE 1: LOGGED-IN USER (STRICT SEPARATION: ADMIN vs STUDENT)
           ========================================================================= */}
        {sessionUser ? (
          sessionUser.role === "admin" ? (
            /* =========================================================================
               STATE 1A: ADMIN OVERVIEW PORTAL
               ========================================================================= */
            <div style={{ paddingTop: 32, display: "flex", flexDirection: "column", gap: 32 }}>
              {/* Admin Welcome Banner */}
              <div
                className="card"
                style={{
                  background: "var(--surface)",
                  borderColor: "rgba(217, 119, 54, 0.25)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 24,
                  padding: "32px",
                }}
              >
                <div>
                  <div className="badge badge-orange" style={{ marginBottom: 12 }}>
                    <ShieldIcon size={14} />
                    <span>لوحة تحكم إدارة منصة ذاكر معي</span>
                  </div>
                  <h1 style={{ fontSize: "clamp(24px, 3vw, 32px)", fontWeight: 800, margin: "0 0 10px" }}>
                    مرحباً بك يا مدير المنصة
                  </h1>
                  <p style={{ margin: 0, fontSize: 14.5, color: "var(--muted)", maxWidth: 580, lineHeight: 1.7 }}>
                    لديك صلاحيات الإدارة الشاملة: إدارة المواد والملفات والمناهج، رفع مهارات وتدريب الذكاء الاصطناعي من GitHub،
                    ومتابعة تفاعل ونشاط الطلاب بدقة في غرفة العمليات.
                  </p>
                </div>

                <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                  <Link
                    href="/admin"
                    className="btn btn-accent btn-lg"
                  >
                    <ShieldIcon size={18} />
                    <span>فتح لوحة الإدارة الشاملة</span>
                  </Link>
                </div>
              </div>

              {/* Admin Quick Modules Grid */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                  gap: 20,
                }}
              >
                <div className="card card-hover" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 10,
                      background: "var(--orange-light)",
                      color: "var(--orange)",
                      display: "grid",
                      placeItems: "center",
                    }}
                  >
                    <BotIcon size={22} />
                  </div>
                  <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "var(--ink)" }}>تدريب الذكاء الاصطناعي</h3>
                  <p style={{ margin: 0, fontSize: 13.5, color: "var(--muted)", lineHeight: 1.65 }}>
                    ارفع مستودعات GitHub لتعزيز مهارات ومكتبة الشرح للـ AI Agent وتزويده بأحدث الشروح الأكاديمية.
                  </p>
                  <Link href="/admin" className="text-button" style={{ color: "var(--orange)", marginTop: "auto" }}>
                    <span>الانتقال لقسم الذكاء الاصطناعي</span>
                    <ChevronLeftIcon size={16} />
                  </Link>
                </div>

                <div className="card card-hover" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 10,
                      background: "var(--mint)",
                      color: "var(--green)",
                      display: "grid",
                      placeItems: "center",
                    }}
                  >
                    <ChartBarIcon size={22} />
                  </div>
                  <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "var(--ink)" }}>تحليلات نشاط الطلاب</h3>
                  <p style={{ margin: 0, fontSize: 13.5, color: "var(--muted)", lineHeight: 1.65 }}>
                    فحص عدد الطلاب النشطين، إجمالي ساعات المذاكرة، ومعدلات حل الاختبارات الذكية لحظياً.
                  </p>
                  <Link href="/admin" className="text-button" style={{ color: "var(--green)", marginTop: "auto" }}>
                    <span>استعراض لوحة التحليلات</span>
                    <ChevronLeftIcon size={16} />
                  </Link>
                </div>

                <div className="card card-hover" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 10,
                      background: "var(--surface-raised)",
                      color: "var(--ink)",
                      display: "grid",
                      placeItems: "center",
                    }}
                  >
                    <BookOpenIcon size={22} />
                  </div>
                  <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "var(--ink)" }}>إدارة المواد والمناهج</h3>
                  <p style={{ margin: 0, fontSize: 13.5, color: "var(--muted)", lineHeight: 1.65 }}>
                    رفع وتعديل الملازم الدراسية والتسجيلات الصوتية وفهرستها لجميع الطلاب المشتركين.
                  </p>
                  <Link href="/admin" className="text-button" style={{ marginTop: "auto" }}>
                    <span>إدارة المواد الدراسية</span>
                    <ChevronLeftIcon size={16} />
                  </Link>
                </div>
              </div>
            </div>
          ) : (
            /* =========================================================================
               STATE 1B: LOGGED-IN STUDENT WORKSPACE & MOTIVATION HUB
               ========================================================================= */
            <div style={{ paddingTop: 32, display: "flex", flexDirection: "column", gap: 32 }}>
              {/* Student Welcome Header Card */}
              <div
                className="card"
                style={{
                  background: "var(--surface)",
                  borderColor: "var(--mint-border)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 24,
                  padding: "32px",
                }}
              >
                <div>
                  <div className="badge badge-mint" style={{ marginBottom: 12 }}>
                    <GraduationCapIcon size={14} />
                    <span>مساحتك الدراسية الذكية</span>
                  </div>
                  <h1
                    style={{
                      fontSize: "clamp(24px, 3vw, 32px)",
                      fontWeight: 800,
                      margin: "0 0 8px",
                      color: "var(--ink)",
                    }}
                  >
                    أهلاً بك مجدداً،{" "}
                    <span style={{ color: "var(--green)" }}>
                      {sessionUser.display_name || sessionUser.email?.split("@")[0] || "يا بطل"}
                    </span>
                  </h1>
                  <p style={{ margin: 0, fontSize: 14.5, color: "var(--muted)", maxWidth: 560, lineHeight: 1.7 }}>
                    جاهز لجلسة مذاكرة واستيعاب جديدة اليوم؟ رفيقك الذكي مجهز بكافة كتبك ومذكراتك لشرح أي درس أو اختبار فهمك.
                  </p>
                </div>

                {/* Fast Action Buttons */}
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                  <Link
                    href="/subjects"
                    className="btn btn-primary btn-lg"
                  >
                    <BookOpenIcon size={18} />
                    <span>ابدأ المذاكرة وتصفح المواد</span>
                  </Link>

                  <Link
                    href="/dashboard"
                    className="btn btn-secondary btn-lg"
                  >
                    <ChartBarIcon size={18} />
                    <span>متابعة تقدمي ومستواي</span>
                  </Link>
                </div>
              </div>

              {/* ROTATING MOTIVATIONAL QUOTE & SMART STUDY TIP */}
              <section className="card" style={{ padding: "24px 28px" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 16,
                    borderBottom: "1px solid var(--line)",
                    paddingBottom: 14,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ color: "var(--green)" }}>{activeTip.icon}</span>
                    <strong style={{ fontSize: 15, color: "var(--ink)" }}>محطة التحفيز اليومية</strong>
                    <span className="badge badge-mint">{activeTip.badge}</span>
                  </div>

                  {/* Tip Navigation Controls */}
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    {MOTIVATIONAL_TIPS.map((_, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setTipIndex(idx)}
                        style={{
                          width: tipIndex === idx ? 22 : 8,
                          height: 7,
                          borderRadius: 4,
                          border: 0,
                          background: tipIndex === idx ? "var(--green)" : "var(--line)",
                          cursor: "pointer",
                          transition: "all 0.25s ease",
                          padding: 0,
                        }}
                        aria-label={`الانتقال للنصيحة ${idx + 1}`}
                      />
                    ))}
                  </div>
                </div>

                {/* Animated Content Wrapper */}
                <div
                  key={tipIndex}
                  className="animate-fade-in"
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                  }}
                >
                  <blockquote
                    style={{
                      margin: 0,
                      fontSize: 16.5,
                      fontWeight: 700,
                      color: "var(--ink)",
                      lineHeight: 1.6,
                    }}
                  >
                    {activeTip.quote}
                  </blockquote>
                  <p
                    style={{
                      margin: 0,
                      fontSize: 13.5,
                      color: "var(--muted)",
                      lineHeight: 1.7,
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <span style={{ color: "var(--green)", fontWeight: 700 }}>نصيحة المذاكرة:</span>
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
                    <h2 style={{ fontSize: 19, margin: "0 0 4px", fontWeight: 700, color: "var(--ink)" }}>
                      موادك الدراسية النشطة ({subjects.length})
                    </h2>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>
                      استأنف شرح الدروس، أو راجع البطاقات والاختبارات التفاعلية بنقرة واحدة.
                    </span>
                  </div>

                  <Link
                    href="/subjects"
                    className="text-button"
                    style={{ fontSize: 13.5 }}
                  >
                    <span>عرض وإدارة جميع المواد</span>
                    <ChevronLeftIcon size={16} />
                  </Link>
                </div>

                {subjects.length === 0 ? (
                  <div
                    className="card"
                    style={{
                      borderStyle: "dashed",
                      padding: "48px 20px",
                      textAlign: "center",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 12,
                    }}
                  >
                    <div
                      style={{
                        width: 48,
                        height: 48,
                        borderRadius: 12,
                        background: "var(--mint)",
                        color: "var(--green)",
                        display: "grid",
                        placeItems: "center",
                      }}
                    >
                      <BookOpenIcon size={24} />
                    </div>
                    <h3 style={{ margin: 0, fontSize: 17, color: "var(--ink)" }}>لم تضف أي مادة دراسية بعد</h3>
                    <p style={{ margin: 0, fontSize: 13.5, color: "var(--muted)", maxWidth: 440 }}>
                      أنشئ مادتك الأولى لتبدأ برفع الملازم، تفريغ المحاضرات الصوتية، والتفاعل مع رفيقك الذكي.
                    </p>
                    <Link
                      href="/subjects"
                      className="btn btn-primary"
                      style={{ marginTop: 8 }}
                    >
                      <BookOpenIcon size={16} />
                      <span>إنشاء مادة جديدة وبدء المذاكرة</span>
                    </Link>
                  </div>
                ) : (
                  <div className="subject-grid">
                    {subjects.slice(0, 3).map((sub) => (
                      <div
                        key={sub.id}
                        className="subject-card"
                      >
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                            <div
                              style={{
                                width: 38,
                                height: 38,
                                borderRadius: 10,
                                background: "var(--mint)",
                                color: "var(--green)",
                                display: "grid",
                                placeItems: "center",
                              }}
                            >
                              <BookOpenIcon size={18} />
                            </div>
                            <h3
                              style={{
                                margin: 0,
                                fontSize: 16.5,
                                fontWeight: 700,
                                color: "var(--ink)",
                              }}
                            >
                              {sub.name}
                            </h3>
                          </div>
                          <p
                            style={{
                              margin: 0,
                              fontSize: 13.5,
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
                            paddingTop: 14,
                            marginTop: 16,
                          }}
                        >
                          <Link
                            href={`/subjects/${sub.id}`}
                            className="btn btn-primary btn-sm"
                          >
                            <span>محادثة الشرح</span>
                            <ChevronLeftIcon size={14} />
                          </Link>

                          <Link
                            href={`/subjects/${sub.id}`}
                            className="text-button"
                            style={{ fontSize: 12.5, color: "var(--muted)" }}
                          >
                            المكتبة والاختبارات
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          )
        ) : (
          /* =========================================================================
             STATE 2: GUEST / BEFORE LOGIN (ACADEMIC EDITORIAL SHOWCASE)
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
                  className="badge badge-mint"
                  style={{
                    padding: "6px 14px",
                    borderRadius: 20,
                    marginBottom: 20,
                    fontSize: 13,
                  }}
                >
                  <SparklesIcon size={15} />
                  <span>رفيقك الأكاديمي الذكي الموثق من مراجعك الخاصة</span>
                </div>

                <h1
                  style={{
                    fontSize: "clamp(30px, 4.2vw, 48px)",
                    lineHeight: 1.35,
                    fontWeight: 900,
                    margin: "0 0 20px",
                    color: "var(--ink)",
                    letterSpacing: -0.5,
                  }}
                >
                  المذاكرة لم تعد معركة شاقة.
                  <br />
                  افهم أسرع، وتذكر أطول مع <span style={{ color: "var(--green)" }}>«ذاكر معي»</span>.
                </h1>

                <p
                  style={{
                    fontSize: 16,
                    lineHeight: 1.8,
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
                    className="btn btn-primary btn-lg"
                  >
                    <BookOpenIcon size={18} />
                    <span>ابدأ المذاكرة وسجل الدخول الآن</span>
                  </Link>

                  <a
                    href="#how-it-works"
                    className="btn btn-secondary btn-lg"
                  >
                    <span>كيف تعمل المنصة؟</span>
                    <ChevronLeftIcon size={16} />
                  </a>
                </div>

                {/* Proof & Efficiency Metrics */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                    gap: 16,
                    marginTop: 40,
                    paddingTop: 24,
                    borderTop: "1px solid var(--line)",
                  }}
                >
                  <div>
                    <strong style={{ fontSize: 24, color: "var(--green)", display: "block", fontWeight: 800 }}>٣ أضعاف</strong>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>سرعة استيعاب المفاهيم</span>
                  </div>
                  <div>
                    <strong style={{ fontSize: 24, color: "var(--green)", display: "block", fontWeight: 800 }}>١٠٠٪ توثيق</strong>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>اقتباس مباشر من ملازمك</span>
                  </div>
                  <div>
                    <strong style={{ fontSize: 24, color: "var(--green)", display: "block", fontWeight: 800 }}>تفريغ فوري</strong>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>للمحاضرات الصوتية</span>
                  </div>
                </div>
              </div>

              {/* Interactive Simulation Workstation Window */}
              <div
                className="card"
                style={{
                  padding: 0,
                  overflow: "hidden",
                  boxShadow: "var(--shadow-lg)",
                }}
              >
                {/* Window Header */}
                <div
                  style={{
                    padding: "12px 18px",
                    background: "var(--surface-raised)",
                    borderBottom: "1px solid var(--line)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#ef4444", display: "inline-block" }} />
                    <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#f59e0b", display: "inline-block" }} />
                    <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#10b981", display: "inline-block" }} />
                  </div>
                  <span style={{ fontSize: 12.5, color: "var(--muted)", fontWeight: 600 }}>
                    الفيزياء الكهرومغناطيسية · مادة دراسية
                  </span>
                  <span className="badge badge-mint" style={{ fontSize: 11 }}>
                    مستوى 4
                  </span>
                </div>

                {/* Simulated Chat Feed */}
                <div style={{ padding: 22, display: "flex", flexDirection: "column", gap: 14 }}>
                  {/* Student message */}
                  <div
                    style={{
                      alignSelf: "flex-start",
                      background: "var(--green)",
                      color: "#ffffff",
                      padding: "11px 16px",
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
                      background: "var(--surface-raised)",
                      color: "var(--ink)",
                      padding: "16px 18px",
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
                        background: "var(--surface)",
                        borderRadius: 10,
                        padding: "12px 14px",
                        border: "1px solid var(--line)",
                        marginBottom: 10,
                      }}
                    >
                      <svg viewBox="0 0 340 110" style={{ width: "100%", height: "auto", display: "block" }}>
                        <line
                          x1="170"
                          y1="100"
                          x2="170"
                          y2="15"
                          stroke="var(--green)"
                          strokeWidth="4"
                          strokeLinecap="round"
                        />
                        <polygon points="170,8 164,22 176,22" fill="var(--green)" />
                        <text x="188" y="24" fill="var(--green)" fontSize="12" fontWeight="bold">
                          التيار (I ↑)
                        </text>

                        <ellipse
                          cx="170"
                          cy="55"
                          rx="75"
                          ry="24"
                          fill="none"
                          stroke="var(--orange)"
                          strokeWidth="2"
                          strokeDasharray="4 3"
                        />
                        <polygon points="245,55 240,48 244,62" fill="var(--orange)" />
                        <text x="252" y="60" fill="var(--orange)" fontSize="11" fontWeight="bold">
                          المجال (B ↻)
                        </text>

                        <ellipse
                          cx="170"
                          cy="75"
                          rx="55"
                          ry="18"
                          fill="none"
                          stroke="var(--green-light)"
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
                      padding: "10px 14px",
                      borderRadius: 10,
                      background: "var(--orange-light)",
                      border: "1px solid rgba(217, 119, 54, 0.25)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      fontSize: 12.5,
                    }}
                  >
                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <ClockIcon size={15} style={{ color: "var(--orange)" }} />
                      <span style={{ fontWeight: 600, color: "var(--ink)" }}>جلسة تركيز جارية</span>
                    </span>
                    <strong style={{ color: "var(--orange)", direction: "ltr" }}>21:15 دقيقة متبقية</strong>
                  </div>
                </div>
              </div>
            </section>

            {/* FEATURES GRID */}
            <section style={{ padding: "60px 0 40px" }}>
              <div style={{ textAlign: "center", maxWidth: 640, margin: "0 auto 40px" }}>
                <span className="eyebrow">
                  <SparklesIcon size={14} />
                  <span>مميزات صُممت لراحتك وتفوقك</span>
                </span>
                <h2 style={{ fontSize: 30, margin: "6px 0 12px", fontWeight: 800, color: "var(--ink)" }}>
                  كل ما تحتاجه لتذاكر <span style={{ color: "var(--green)" }}>بأعلى كفاءة ومرونة</span>
                </h2>
                <p style={{ color: "var(--muted)", fontSize: 15.5 }}>
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
                    icon: <BookOpenIcon size={22} />,
                    title: "شرح موثق من مراجعك حصراً",
                    desc: "المساعد الذكي يستند حصرياً إلى الكتب والمذكرات التي ترفعها، ويستشهد بأرقام الصفحات لضمان دقة المعلومة.",
                  },
                  {
                    icon: <SparklesIcon size={22} />,
                    title: "تفريغ فوري للمحاضرات الصوتية",
                    desc: "ارفع تسجيلات المحاضرات بصيغة MP3 أو WAV، وتتحول لنصوص مشروحة يستخرج منها المساعد كافة النقاط الأساسية.",
                  },
                  {
                    icon: <WandIcon size={22} />,
                    title: "رسوم توضيحية ومخططات بصرية",
                    desc: "حوّل المفاهيم المعقدة إلى رسوم وخرائط مفاهيمية SVG واضحة تعزز الذاكرة البصرية وتثبت القوانين بسهولة.",
                  },
                  {
                    icon: <ClockIcon size={22} />,
                    title: "جلسات تركيز بومودورو ذكية",
                    desc: "اضبط مدة جلستك (15، 25، 45، أو 60 دقيقة) بضغطة زر مع مؤقت تفاعلي يحميك من التشتت ويحسب وقتك الفعلي.",
                  },
                  {
                    icon: <GraduationCapIcon size={22} />,
                    title: "تقييم أكاديمي حقيقي (مستويات 1-10)",
                    desc: "تقييم مبني على أسس التعلم: انتظام جلسات التركيز، عمق الفضول، ودقة الاسترجاع، وليس مجرد عدّ الملفات.",
                  },
                  {
                    icon: <ShieldIcon size={22} />,
                    title: "إشراف أكاديمي مباشر وإشعارات فورية",
                    desc: "أي سؤال لا يغطيه منهجك يتم توجيهه لإدارة المادة لمراجعته واعتماد إجابته، مع إشعار فوري يظهر لك بمجرد الرد.",
                  },
                ].map((card, idx) => (
                  <div
                    key={idx}
                    className="card card-hover"
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 12,
                      padding: "24px",
                    }}
                  >
                    <div
                      style={{
                        width: 44,
                        height: 44,
                        borderRadius: 10,
                        background: "var(--mint)",
                        color: "var(--green)",
                        display: "grid",
                        placeItems: "center",
                      }}
                    >
                      {card.icon}
                    </div>
                    <h3 style={{ fontSize: 17, margin: "0", fontWeight: 700, color: "var(--ink)" }}>{card.title}</h3>
                    <p style={{ margin: 0, fontSize: 14, color: "var(--muted)", lineHeight: 1.7 }}>{card.desc}</p>
                  </div>
                ))}
              </div>
            </section>

            {/* HOW IT WORKS (3 SIMPLE STEPS) */}
            <section
              id="how-it-works"
              className="card"
              style={{
                padding: "44px 32px",
                margin: "20px 0 40px",
              }}
            >
              <div style={{ textAlign: "center", marginBottom: 36 }}>
                <span className="eyebrow">
                  <CheckCircleIcon size={14} />
                  <span>سهولة وسلاسة لا مثيل لها</span>
                </span>
                <h2 style={{ fontSize: 26, margin: "4px 0", fontWeight: 800, color: "var(--ink)" }}>
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
                      width: 48,
                      height: 48,
                      borderRadius: "50%",
                      background: "var(--mint)",
                      color: "var(--green)",
                      display: "grid",
                      placeItems: "center",
                      fontSize: 19,
                      fontWeight: 800,
                      margin: "0 auto 16px",
                    }}
                  >
                    1
                  </div>
                  <h3 style={{ fontSize: 16.5, marginBottom: 8, fontWeight: 700, color: "var(--ink)" }}>
                    أنشئ مادتك وارفع مراجعك
                  </h3>
                  <p style={{ fontSize: 13.5, color: "var(--muted)", lineHeight: 1.7 }}>
                    أضف اسم المادة، وارفع ملازمك أو كتبك بصيغة PDF أو تسجيلات المحاضرات الصوتية وروابط YouTube.
                  </p>
                </div>

                <div>
                  <div
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: "50%",
                      background: "var(--mint)",
                      color: "var(--green)",
                      display: "grid",
                      placeItems: "center",
                      fontSize: 19,
                      fontWeight: 800,
                      margin: "0 auto 16px",
                    }}
                  >
                    2
                  </div>
                  <h3 style={{ fontSize: 16.5, marginBottom: 8, fontWeight: 700, color: "var(--ink)" }}>
                    تحاور مع رفيقك الذكي
                  </h3>
                  <p style={{ fontSize: 13.5, color: "var(--muted)", lineHeight: 1.7 }}>
                    اسأله في أي جزئية غامضة، واطلب منه تبسيط الشرح أو رسم مخططات توضيحية بصرية بالذكاء الاصطناعي.
                  </p>
                </div>

                <div>
                  <div
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: "50%",
                      background: "var(--mint)",
                      color: "var(--green)",
                      display: "grid",
                      placeItems: "center",
                      fontSize: 19,
                      fontWeight: 800,
                      margin: "0 auto 16px",
                    }}
                  >
                    3
                  </div>
                  <h3 style={{ fontSize: 16.5, marginBottom: 8, fontWeight: 700, color: "var(--ink)" }}>
                    عزز تركيزك وارتقِ بمستواك
                  </h3>
                  <p style={{ fontSize: 13.5, color: "var(--muted)", lineHeight: 1.7 }}>
                    اضبط جلسات بومودورو للتركيز، وتابع تقدمك الأكاديمي وصعودك في مستويات الإتقان (1-10).
                  </p>
                </div>
              </div>

              <div style={{ textAlign: "center", marginTop: 40 }}>
                <Link href="/login" className="btn btn-primary btn-lg">
                  <UserIcon size={18} />
                  <span>ابدأ المذاكرة الآن مع «ذاكر معي»</span>
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
          <div>خطوة صغيرة كل يوم تصنع تفوقاً كبيراً في مستقبلك الأكاديمي.</div>
        </footer>
      </main>
    </div>
  );
}
