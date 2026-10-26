"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import DOMPurify from "dompurify";
import { apiRequest } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { SubjectLibrary } from "@/components/subject-library";
import { AppHeader } from "@/components/app-header";
import { SubjectQuizzes } from "@/components/subject-quizzes";
import { SubjectFlashcards } from "@/components/subject-flashcards";

type ChatMedia = {
  type: "image" | "svg";
  url?: string;
  svg?: string;
  title?: string;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  media?: ChatMedia;
  no_resources?: boolean;
  out_of_scope?: boolean;
};

type ChatResponse = {
  answer: string;
  no_resources?: boolean;
  out_of_scope?: boolean;
  inquiry_id?: string | null;
  thread_id?: string;
};

type ChatThreadItem = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

type PersistedMessageItem = {
  id: string;
  role: "user" | "assistant";
  content: string;
  media_type?: "image" | "svg" | null;
  media_url?: string | null;
  media_svg?: string | null;
  no_resources?: boolean;
  out_of_scope?: boolean;
  created_at: string;
};

type ImageResponse = {
  type: "image" | "svg";
  title: string;
  description: string;
  image_url?: string;
  svg?: string;
};

type SubjectInfo = {
  id: string;
  name: string;
  description: string | null;
};

function ClientMessageTime({ date }: { date: Date | string }) {
  const [formatted, setFormatted] = useState<string>("");
  useEffect(() => {
    try {
      const d = typeof date === "string" ? new Date(date) : date;
      setFormatted(d.toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" }));
    } catch {
      setFormatted("");
    }
  }, [date]);

  return <span suppressHydrationWarning>{formatted || "·"}</span>;
}

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "مرحبًا بك! أنا رفيقك ومساعدك الذكي في «ذاكر معي». 🎓\nأشرح لك كافة مفاهيم المادة من مراجعك وكتبك المرفوعة فقط، ويمكنك أيضاً طلب رسم توضيحي ذكي لأي مفهوم بصرياً!",
  timestamp: new Date(),
};

const QUICK_PROMPTS = [
  "ما هي أهم المحاور والنقاط الرئيسية في المادة؟",
  "اشرح لي فكرة المادة بأسلوب مبسط خطوة بخطوة",
  "اختبرني بسؤال سريع لتأكيد فهمي للدرس",
];

export function SubjectPageContent({ subjectId }: { subjectId: string }) {
  const [activeTab, setActiveTab] = useState<"chat" | "library" | "quizzes" | "flashcards">("chat");
  const [subject, setSubject] = useState<SubjectInfo | null>(null);

  useEffect(() => {
    let active = true;
    async function loadSubject() {
      try {
        const {
          data: { session },
        } = await createClient().auth.getSession();
        if (session) {
          const data = await apiRequest<SubjectInfo>(`/api/v1/subjects/${subjectId}`, {
            headers: { Authorization: `Bearer ${session.access_token}` },
          });
          if (active) setSubject(data);
        }
      } catch {
        // ignore
      }
    }
    void loadSubject();
    return () => {
      active = false;
    };
  }, [subjectId]);

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--paper)" }}>
      {/* Global Unified Header */}
      <AppHeader currentSubjectId={subjectId} />

      {/* Main Workspace Bar */}
      <div
        style={{
          borderBottom: "1px solid var(--line)",
          background: "var(--surface, #fff)",
          padding: "10px 24px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Link
            href="/subjects"
            className="text-button"
            style={{ fontSize: 13, color: "var(--muted)", textDecoration: "none" }}
          >
            ← قائمة المواد
          </Link>
          <span style={{ color: "var(--line)" }}>/</span>
          <h2 style={{ fontSize: 18, margin: 0, fontWeight: 700, color: "var(--ink)" }}>
            📖 {subject?.name || "المادة الدراسية"}
          </h2>
        </div>

        {/* Tab Toggle */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => setActiveTab("chat")}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              border: 0,
              cursor: "pointer",
              fontWeight: 600,
              fontSize: 13.5,
              transition: "all 0.2s",
              background: activeTab === "chat" ? "var(--green)" : "var(--paper)",
              color: activeTab === "chat" ? "#fff" : "var(--muted)",
            }}
          >
            💬 محادثة وشرح الذكاء الاصطناعي
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("library")}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              border: 0,
              cursor: "pointer",
              fontWeight: 600,
              fontSize: 13.5,
              transition: "all 0.2s",
              background: activeTab === "library" ? "var(--green)" : "var(--paper)",
              color: activeTab === "library" ? "#fff" : "var(--muted)",
            }}
          >
            📚 مكتبة المادة والمراجع
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("quizzes")}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              border: 0,
              cursor: "pointer",
              fontWeight: 600,
              fontSize: 13.5,
              transition: "all 0.2s",
              background: activeTab === "quizzes" ? "var(--green)" : "var(--paper)",
              color: activeTab === "quizzes" ? "#fff" : "var(--muted)",
            }}
          >
            📝 اختبر فهمك
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("flashcards")}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              border: 0,
              cursor: "pointer",
              fontWeight: 600,
              fontSize: 13.5,
              transition: "all 0.2s",
              background: activeTab === "flashcards" ? "var(--green)" : "var(--paper)",
              color: activeTab === "flashcards" ? "#fff" : "var(--muted)",
            }}
          >
            🃏 البطاقات التعليمية
          </button>
        </div>
      </div>

      {/* Workspace Content */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {activeTab === "chat" && (
          <FullScreenChat subjectId={subjectId} onSwitchToLibrary={() => setActiveTab("library")} />
        )}
        {activeTab === "library" && (
          <div style={{ padding: "24px 20px" }}>
            <SubjectLibrary subjectId={subjectId} />
          </div>
        )}
        {activeTab === "quizzes" && <SubjectQuizzes subjectId={subjectId} />}
        {activeTab === "flashcards" && <SubjectFlashcards subjectId={subjectId} />}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   FULL-SCREEN IMMERSIVE AI CHAT
   ═══════════════════════════════════════════════════════════════════ */

function FullScreenChat({
  subjectId,
  onSwitchToLibrary,
}: {
  subjectId: string;
  onSwitchToLibrary: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [threads, setThreads] = useState<ChatThreadItem[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [showThreadsDrawer, setShowThreadsDrawer] = useState(false);
  const [loadingThreads, setLoadingThreads] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [generatingImage, setGeneratingImage] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const getHeaders = useCallback(async () => {
    const {
      data: { session },
      error: sessionError,
    } = await createClient().auth.getSession();
    if (sessionError || !session) throw new Error("انتهت جلسة الدخول. سجّل الدخول مجددًا.");
    return { Authorization: `Bearer ${session.access_token}` };
  }, []);

  const loadThreads = useCallback(async () => {
    try {
      setLoadingThreads(true);
      const headers = await getHeaders();
      const data = await apiRequest<ChatThreadItem[]>(`/api/v1/subjects/${subjectId}/chat/threads`, { headers });
      setThreads(data);
    } catch {
      // ignore
    } finally {
      setLoadingThreads(false);
    }
  }, [getHeaders, subjectId]);

  useEffect(() => {
    void loadThreads();
  }, [loadThreads]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, sending, generatingImage]);

  async function handleSelectThread(threadId: string) {
    if (threadId === activeThreadId) {
      setShowThreadsDrawer(false);
      return;
    }
    setActiveThreadId(threadId);
    setError(null);
    setShowThreadsDrawer(false);
    try {
      const headers = await getHeaders();
      const rawMessages = await apiRequest<PersistedMessageItem[]>(
        `/api/v1/subjects/${subjectId}/chat/threads/${threadId}/messages`,
        { headers }
      );
      if (rawMessages && rawMessages.length > 0) {
        setMessages(
          rawMessages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            timestamp: new Date(m.created_at),
            no_resources: m.no_resources,
            out_of_scope: m.out_of_scope,
            media:
              m.media_type === "svg" && m.media_svg
                ? { type: "svg", svg: m.media_svg }
                : m.media_type === "image" && m.media_url
                ? { type: "image", url: m.media_url }
                : undefined,
          }))
        );
      } else {
        setMessages([WELCOME_MESSAGE]);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر استرجاع رسائل المحادثة.");
    }
  }

  function handleNewChat() {
    setActiveThreadId(null);
    setMessages([WELCOME_MESSAGE]);
    setError(null);
    setShowThreadsDrawer(false);
  }

  async function handleDeleteThread(threadId: string, event: React.MouseEvent) {
    event.stopPropagation();
    if (!window.confirm("هل أنت متأكد من حذف هذه المحادثة من سجلك؟")) return;
    try {
      const headers = await getHeaders();
      await apiRequest(`/api/v1/subjects/${subjectId}/chat/threads/${threadId}`, {
        method: "DELETE",
        headers,
      });
      setThreads((prev) => prev.filter((t) => t.id !== threadId));
      if (activeThreadId === threadId) {
        handleNewChat();
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر حذف المحادثة.");
    }
  }

  async function handleSend(textToSend?: string) {
    const text = (textToSend || input).trim();
    if (!text || sending) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setSending(true);
    setError(null);

    try {
      const headers = await getHeaders();
      const response = await apiRequest<ChatResponse>(
        `/api/v1/subjects/${subjectId}/chat/`,
        {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            thread_id: activeThreadId || undefined,
          }),
        },
        60_000
      );

      if (response.thread_id && !activeThreadId) {
        setActiveThreadId(response.thread_id);
        void loadThreads();
      }

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: response.answer,
        timestamp: new Date(),
        no_resources: response.no_resources,
        out_of_scope: response.out_of_scope,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر الحصول على إجابة من المساعد.");
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void handleSend();
  }

  async function handleGenerateIllustration() {
    const prompt = input.trim() || messages[messages.length - 1]?.content || "رسم توضيحي للدرس";
    if (generatingImage) return;

    setGeneratingImage(true);
    setError(null);

    const userNote: ChatMessage = {
      id: `req-${Date.now()}`,
      role: "user",
      content: `🎨 طلب رسم توضيحي بالذكاء الاصطناعي لـ: «${prompt.slice(0, 80)}»`,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userNote]);
    setInput("");

    try {
      const headers = await getHeaders();
      const result = await apiRequest<ImageResponse>(
        `/api/v1/subjects/${subjectId}/images/generate`,
        {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({ prompt, context: prompt }),
        },
        45_000
      );

      const assistantImageMsg: ChatMessage = {
        id: `img-${Date.now()}`,
        role: "assistant",
        content: `تم إنشاء المخطط والرسم التوضيحي التعليمي (${result.title}):`,
        timestamp: new Date(),
        media: {
          type: result.type,
          url: result.image_url,
          svg: result.svg,
          title: result.title,
        },
      };
      setMessages((prev) => [...prev, assistantImageMsg]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر إنشاء الرسم التوضيحي.");
    } finally {
      setGeneratingImage(false);
      inputRef.current?.focus();
    }
  }

  const activeThread = threads.find((t) => t.id === activeThreadId);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 124px)",
        maxWidth: 1100,
        width: "100%",
        margin: "0 auto",
        position: "relative",
      }}
    >
      {/* Chat Toolbar: Thread History Toggle & New Chat Button */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "8px 20px",
          borderBottom: "1px solid var(--line)",
          background: "var(--surface, #fff)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            type="button"
            onClick={() => setShowThreadsDrawer((prev) => !prev)}
            className="text-button"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 13,
              fontWeight: 600,
              padding: "6px 12px",
              borderRadius: 8,
              border: "1px solid var(--line)",
              background: showThreadsDrawer ? "rgba(100, 140, 90, 0.12)" : "var(--paper)",
              color: showThreadsDrawer ? "var(--green)" : "var(--ink)",
            }}
          >
            <span>📜</span>
            <span>سجل المحادثات ({threads.length})</span>
          </button>

          <button
            type="button"
            onClick={handleNewChat}
            className="session-start"
            style={{
              margin: 0,
              padding: "6px 14px",
              fontSize: 12.5,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span>➕</span>
            <span>محادثة جديدة</span>
          </button>
        </div>

        <div style={{ fontSize: 13, color: "var(--muted)", fontWeight: 500 }}>
          {activeThread ? `📌 ${activeThread.title}` : "محادثة جديدة 💭"}
        </div>
      </div>

      {/* Collapsible Slide-over Threads Drawer */}
      {showThreadsDrawer && (
        <div
          style={{
            position: "absolute",
            top: 48,
            right: 0,
            bottom: 0,
            width: 320,
            maxWidth: "85%",
            background: "var(--surface, #fff)",
            borderLeft: "1px solid var(--line)",
            boxShadow: "-4px 0 20px rgba(0,0,0,0.08)",
            zIndex: 30,
            display: "flex",
            flexDirection: "column",
            padding: "16px 14px",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              borderBottom: "1px solid var(--line)",
              paddingBottom: 10,
              marginBottom: 12,
            }}
          >
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: "var(--ink)" }}>
              📜 سجل محادثاتك السابقة
            </h3>
            <button
              type="button"
              onClick={() => setShowThreadsDrawer(false)}
              className="text-button"
              style={{ fontSize: 18, padding: "2px 8px" }}
            >
              ✕
            </button>
          </div>

          <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
            {loadingThreads ? (
              <p style={{ fontSize: 13, color: "var(--muted)", textAlign: "center", margin: "20px 0" }}>
                جارٍ تحميل السجل…
              </p>
            ) : threads.length === 0 ? (
              <p style={{ fontSize: 13, color: "var(--muted)", textAlign: "center", margin: "20px 0" }}>
                لا توجد محادثات سابقة محفوظة بعد. أرسل سؤالك الأول لتبدأ محادثة جديدة!
              </p>
            ) : (
              threads.map((t) => (
                <div
                  key={t.id}
                  onClick={() => void handleSelectThread(t.id)}
                  style={{
                    padding: "10px 12px",
                    borderRadius: 10,
                    background: activeThreadId === t.id ? "rgba(100, 140, 90, 0.12)" : "var(--paper)",
                    border: `1.5px solid ${activeThreadId === t.id ? "var(--green)" : "var(--line)"}`,
                    cursor: "pointer",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 8,
                    transition: "all 0.15s",
                  }}
                >
                  <div style={{ overflow: "hidden", flex: 1 }}>
                    <strong
                      style={{
                        display: "block",
                        fontSize: 13,
                        color: activeThreadId === t.id ? "var(--green)" : "var(--ink)",
                        textOverflow: "ellipsis",
                        overflow: "hidden",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {t.title}
                    </strong>
                    <span style={{ fontSize: 11, color: "var(--muted)" }}>
                      {new Date(t.created_at).toLocaleDateString("ar-EG", {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => void handleDeleteThread(t.id, e)}
                    className="text-button"
                    title="حذف المحادثة"
                    style={{ color: "#9b3f32", fontSize: 14, padding: "4px" }}
                  >
                    🗑️
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Scrollable Message Feed */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "24px 20px",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
        aria-live="polite"
      >
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={msg.id}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: isUser ? "flex-start" : "flex-end",
                maxWidth: "85%",
                alignSelf: isUser ? "flex-start" : "flex-end",
              }}
            >
              {/* Sender label */}
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--muted)",
                  marginBottom: 4,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                {isUser ? "👤 أنت" : "🎓 مساعد ذاكر معي"}
              </span>

              {/* Chat Bubble */}
              <div
                style={{
                  padding: "16px 20px",
                  borderRadius: 16,
                  borderBottomRightRadius: isUser ? 4 : 16,
                  borderBottomLeftRadius: isUser ? 16 : 4,
                  background: isUser ? "var(--green)" : "var(--surface, #fff)",
                  color: isUser ? "#fff" : "var(--ink)",
                  boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
                  border: isUser ? 0 : "1px solid var(--line)",
                  lineHeight: 1.8,
                  fontSize: 15,
                  width: "100%",
                }}
              >
                {/* Out of scope notification card */}
                {msg.out_of_scope && (
                  <div
                    style={{
                      background: "rgba(215, 142, 93, 0.12)",
                      border: "1px solid var(--orange)",
                      color: "var(--ink)",
                      borderRadius: 8,
                      padding: "10px 14px",
                      marginBottom: 12,
                      fontSize: 13,
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <span>📬</span>
                    <span>
                      <strong>تنبيه:</strong> هذا السؤال لم يُذكر في مراجع المادة، وتم إرساله إلى إدارة المادة لمراجعته
                      والرد عليك في الإشعارات.
                    </span>
                  </div>
                )}

                {/* Main Message Text */}
                <p style={{ margin: 0, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{msg.content}</p>

                {/* If no resources: Button to switch to library */}
                {msg.no_resources && (
                  <div style={{ marginTop: 14 }}>
                    <button
                      type="button"
                      onClick={onSwitchToLibrary}
                      className="session-start"
                      style={{
                        margin: 0,
                        background: "var(--green)",
                        color: "#fff",
                        padding: "10px 20px",
                        fontSize: 14,
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <span>📁</span>
                      <span>الانتقال لرفع الكتب والمصادر في المكتبة الآن</span>
                    </button>
                  </div>
                )}

                {/* Inline SVG or Educational Image */}
                {msg.media && (
                  <div
                    style={{
                      marginTop: 14,
                      borderRadius: 10,
                      overflow: "hidden",
                      background: "#fff",
                      border: "1px solid var(--line)",
                      padding: 12,
                    }}
                  >
                    {msg.media.type === "svg" && msg.media.svg && (
                      <div
                        dangerouslySetInnerHTML={{
                          __html: DOMPurify.sanitize(msg.media.svg, { USE_PROFILES: { svg: true } }),
                        }}
                        style={{ maxWidth: "100%", overflowX: "auto" }}
                      />
                    )}
                    {msg.media.type === "image" && msg.media.url && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={msg.media.url}
                        alt={msg.media.title || "رسم توضيحي"}
                        style={{ maxWidth: "100%", height: "auto", display: "block", borderRadius: 6 }}
                      />
                    )}
                  </div>
                )}

                <span
                  suppressHydrationWarning
                  style={{
                    display: "block",
                    marginTop: 6,
                    fontSize: 11,
                    opacity: 0.65,
                    textAlign: isUser ? "right" : "left",
                  }}
                >
                  <ClientMessageTime date={msg.timestamp} />
                </span>
              </div>
            </div>
          );
        })}

        {/* Loading Indicator */}
        {sending && (
          <div style={{ alignSelf: "flex-end", maxWidth: "80%" }}>
            <div
              style={{
                padding: "14px 18px",
                borderRadius: 16,
                background: "var(--surface, #fff)",
                border: "1px solid var(--line)",
                color: "var(--muted)",
                fontSize: 14,
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <span>💭</span>
              <span>المساعد يفكر ويستخرج الشرح من مصادر المادة…</span>
            </div>
          </div>
        )}

        {generatingImage && (
          <div style={{ alignSelf: "flex-end", maxWidth: "80%" }}>
            <div
              style={{
                padding: "14px 18px",
                borderRadius: 16,
                background: "var(--surface, #fff)",
                border: "1px solid var(--line)",
                color: "var(--muted)",
                fontSize: 14,
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <span>🎨</span>
              <span>جاري توليد الرسم التوضيحي التعليمي…</span>
            </div>
          </div>
        )}

        {error && (
          <div
            style={{
              padding: "12px 16px",
              borderRadius: 8,
              background: "#fff0ed",
              color: "#9b3f32",
              fontSize: 14,
              textAlign: "center",
            }}
          >
            {error}
          </div>
        )}
      </div>

      {/* Floating Bottom Section: Prompt Chips + Input Bar */}
      <div
        style={{
          background: "var(--surface, #fff)",
          borderTop: "1px solid var(--line)",
          padding: "12px 20px 16px",
        }}
      >
        {/* Suggestion Chips (ONLY on Chat Screen) */}
        <div
          style={{
            display: "flex",
            gap: 8,
            overflowX: "auto",
            paddingBottom: 10,
            scrollbarWidth: "none",
          }}
          aria-label="اقتراحات سريعة"
        >
          {QUICK_PROMPTS.map((prompt, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => void handleSend(prompt)}
              disabled={sending}
              style={{
                whiteSpace: "nowrap",
                fontSize: 12.5,
                padding: "6px 14px",
                borderRadius: 20,
                border: "1px solid var(--line)",
                background: "var(--paper)",
                color: "var(--ink)",
                cursor: "pointer",
                fontWeight: 500,
                transition: "all 0.2s",
              }}
            >
              💡 {prompt}
            </button>
          ))}
        </div>

        {/* Input Form */}
        <form onSubmit={handleSubmit} style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void handleSend();
              }
            }}
            placeholder="اسأل رفيقك الذكي عن أي درس، أو اطلب شرحاً مبسطاً..."
            rows={1}
            style={{
              flex: 1,
              minHeight: 48,
              maxHeight: 120,
              padding: "12px 16px",
              borderRadius: 12,
              border: "1px solid var(--line)",
              background: "var(--paper)",
              color: "var(--ink)",
              fontSize: 14,
              fontFamily: "inherit",
              resize: "none",
              lineHeight: 1.5,
            }}
          />

          {/* Educational Diagram / Image Button (Nano Banana) */}
          <button
            type="button"
            onClick={() => void handleGenerateIllustration()}
            disabled={generatingImage || sending}
            title="توليد رسم توضيحي أو خريطة بصرية للمفهوم"
            style={{
              height: 48,
              padding: "0 16px",
              borderRadius: 12,
              border: "1px solid var(--line)",
              background: "rgba(215, 142, 93, 0.1)",
              color: "var(--orange)",
              fontWeight: 600,
              fontSize: 13,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
              whiteSpace: "nowrap",
            }}
          >
            <span>🎨</span>
            <span>رسم توضيحي</span>
          </button>

          {/* Send Button */}
          <button
            type="submit"
            disabled={sending || !input.trim()}
            style={{
              height: 48,
              padding: "0 22px",
              borderRadius: 12,
              border: 0,
              background: "var(--green)",
              color: "#fff",
              fontWeight: 700,
              fontSize: 14,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 8,
              whiteSpace: "nowrap",
              opacity: sending || !input.trim() ? 0.6 : 1,
            }}
          >
            <span>إرسال</span>
            <span>🚀</span>
          </button>
        </form>
      </div>
    </div>
  );
}
