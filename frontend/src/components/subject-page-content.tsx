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
import {
  ChatIcon,
  BookOpenIcon,
  CheckCircleIcon,
  LayersIcon,
  ClockIcon,
  BotIcon,
  UserIcon,
  TrashIcon,
  PlusIcon,
  SparklesIcon,
  AlertCircleIcon,
  XIcon,
  LightbulbIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  FolderIcon,
  DownloadIcon,
  MaximizeIcon,
  CopyIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from "@/components/icons";

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
  timestamp?: Date;
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
  suggested_replies?: string[];
  media_type?: "image" | "svg" | null;
  media_url?: string | null;
  media_svg?: string | null;
  media_title?: string | null;
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

type SubjectInfo = {
  id: string;
  name: string;
  description: string | null;
};

const CHAT_TIME_FORMATTER = new Intl.DateTimeFormat("ar-EG", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Africa/Cairo",
});

function ClientMessageTime({ date }: { date?: Date | string }) {
  if (!date) return <span>·</span>;
  const value = typeof date === "string" ? new Date(date) : date;
  if (Number.isNaN(value.getTime())) return <span>·</span>;
  return <span>{CHAT_TIME_FORMATTER.format(value)}</span>;
}

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "مرحبًا بك! أنا رفيقك ومساعدك الذكي في «ذاكر معي». 📚\nأنا هنا لأشرح لك مفاهيم المادة، وألخص الدروس، وأجيب عن كل أسئلتك استناداً إلى كتبك ومراجعك وشروحات الفيديو المرفوعة للمادة.\n\nتفضل بطرح أي سؤال وسأجيبك بدقة خطوة بخطوة!",
};

let localMessageSequence = 0;

function createLocalMessageId(prefix: string): string {
  localMessageSequence += 1;
  return `${prefix}-${localMessageSequence}`;
}

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

      {/* Workspace Bar: Navigation & Tabs */}
      <div
        style={{
          borderBottom: "1px solid var(--line)",
          background: "var(--surface)",
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
            style={{ fontSize: 13.5, color: "var(--muted)" }}
          >
            <ChevronRightIcon size={16} />
            <span>قائمة المواد</span>
          </Link>
          <span style={{ color: "var(--line)" }}>/</span>
          <h2 style={{ fontSize: 17, margin: 0, fontWeight: 700, color: "var(--ink)", display: "flex", alignItems: "center", gap: 6 }}>
            <BookOpenIcon size={18} style={{ color: "var(--green)" }} />
            <span>{subject?.name || "المادة الدراسية"}</span>
          </h2>
        </div>

        {/* Tab Toggle Navigation */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }} role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "chat"}
            onClick={() => setActiveTab("chat")}
            className={`btn btn-sm ${activeTab === "chat" ? "btn-primary" : "btn-ghost"}`}
          >
            <ChatIcon size={15} />
            <span>الشرح والمحادثة الذكية</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "library"}
            onClick={() => setActiveTab("library")}
            className={`btn btn-sm ${activeTab === "library" ? "btn-primary" : "btn-ghost"}`}
          >
            <FolderIcon size={15} />
            <span>مكتبة المادة والمراجع</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "quizzes"}
            onClick={() => setActiveTab("quizzes")}
            className={`btn btn-sm ${activeTab === "quizzes" ? "btn-primary" : "btn-ghost"}`}
          >
            <CheckCircleIcon size={15} />
            <span>اختبر فهمك</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "flashcards"}
            onClick={() => setActiveTab("flashcards")}
            className={`btn btn-sm ${activeTab === "flashcards" ? "btn-primary" : "btn-ghost"}`}
          >
            <LayersIcon size={15} />
            <span>البطاقات التعليمية</span>
          </button>
        </div>
      </div>

      {/* Workspace Content */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {activeTab === "chat" && (
          <FullScreenChat subjectId={subjectId} onSwitchToLibrary={() => setActiveTab("library")} />
        )}
        {activeTab === "library" && (
          <div className="shell" style={{ padding: "28px 20px" }}>
            <SubjectLibrary subjectId={subjectId} />
          </div>
        )}
        {activeTab === "quizzes" && (
          <div className="shell" style={{ padding: "28px 20px" }}>
            <SubjectQuizzes subjectId={subjectId} />
          </div>
        )}
        {activeTab === "flashcards" && (
          <div className="shell" style={{ padding: "28px 20px" }}>
            <SubjectFlashcards subjectId={subjectId} />
          </div>
        )}
      </div>
    </div>
  );
}

function downloadMediaFile(media: ChatMedia, format: "svg" | "png") {
  const safeTitle = (media.title || "educational-visual")
    .replace(/[^a-zA-Z0-9\u0600-\u06FF_-]/g, "_")
    .slice(0, 40);

  if (format === "svg" && media.svg) {
    const blob = new Blob([media.svg], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${safeTitle}.svg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } else if (format === "png" && media.svg) {
    const svgBlob = new Blob([media.svg], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = 1600;
      canvas.height = 992;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.fillStyle = "#0a0f1d";
        ctx.fillRect(0, 0, 1600, 992);
        ctx.drawImage(img, 0, 0, 1600, 992);
        canvas.toBlob((blob) => {
          if (blob) {
            const pngUrl = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = pngUrl;
            a.download = `${safeTitle}.png`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(pngUrl);
          }
        }, "image/png");
      }
      URL.revokeObjectURL(url);
    };
    img.src = url;
  } else if (media.url) {
    const a = document.createElement("a");
    a.href = media.url;
    a.download = `${safeTitle}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }
}

function MediaLightboxModal({
  media,
  onClose,
}: {
  media: ChatMedia;
  onClose: () => void;
}) {
  const [zoom, setZoom] = useState(1);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleCopyCode = async () => {
    if (media.svg) {
      try {
        await navigator.clipboard.writeText(media.svg);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch {
        // ignore
      }
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 99999,
        background: "rgba(8, 12, 22, 0.9)",
        backdropFilter: "blur(10px)",
        display: "flex",
        flexDirection: "column",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Modal Top Bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 24px",
          background: "rgba(15, 23, 42, 0.98)",
          borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
          gap: 14,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              padding: "4px 10px",
              borderRadius: 6,
              background: "rgba(56, 189, 248, 0.15)",
              color: "#38bdf8",
              fontSize: 12,
              fontWeight: "bold",
            }}
          >
            {media.type === "svg" ? "مخطط مفاهيمي دلالي" : "صورة تعليمية ذكية"}
          </span>
          <h3 style={{ margin: 0, fontSize: 16, color: "#f8fafc", fontWeight: 600 }}>
            {media.title || "استعراض الرسم التوضيحي"}
          </h3>
        </div>

        {/* Action Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {/* Zoom controls */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              background: "rgba(255,255,255,0.06)",
              borderRadius: 8,
              padding: 2,
              border: "1px solid rgba(255,255,255,0.1)",
            }}
          >
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              style={{ color: "#cbd5e1", padding: "4px 8px" }}
              title="تصغير"
              onClick={() => setZoom((z) => Math.max(0.5, Number((z - 0.2).toFixed(2))))}
            >
              <ZoomOutIcon size={16} />
            </button>
            <span style={{ fontSize: 12, color: "#94a3b8", padding: "0 6px", minWidth: 42, textAlign: "center" }}>
              {Math.round(zoom * 100)}%
            </span>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              style={{ color: "#cbd5e1", padding: "4px 8px" }}
              title="تكبير"
              onClick={() => setZoom((z) => Math.min(2.5, Number((z + 0.2).toFixed(2))))}
            >
              <ZoomInIcon size={16} />
            </button>
            {zoom !== 1 && (
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                style={{ fontSize: 11, color: "#38bdf8", padding: "2px 6px" }}
                onClick={() => setZoom(1)}
              >
                إعادة
              </button>
            )}
          </div>

          {/* Copy Code */}
          {media.type === "svg" && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              style={{ color: copied ? "#10b981" : "#cbd5e1", border: "1px solid rgba(255,255,255,0.1)" }}
              onClick={handleCopyCode}
              title="نسخ كود الـ SVG"
            >
              <CopyIcon size={15} />
              <span>{copied ? "تم النسخ!" : "نسخ الكود"}</span>
            </button>
          )}

          {/* Download SVG */}
          {media.type === "svg" && (
            <button
              type="button"
              className="btn btn-sm"
              style={{
                background: "rgba(56, 189, 248, 0.15)",
                color: "#38bdf8",
                border: "1px solid rgba(56, 189, 248, 0.3)",
              }}
              onClick={() => downloadMediaFile(media, "svg")}
            >
              <DownloadIcon size={15} />
              <span>تنزيل SVG</span>
            </button>
          )}

          {/* Download PNG */}
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => downloadMediaFile(media, "png")}
          >
            <DownloadIcon size={15} />
            <span>تنزيل كصورة PNG</span>
          </button>

          {/* Close */}
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            style={{ color: "#f87171", padding: "6px" }}
            onClick={onClose}
            aria-label="إغلاق النافذة"
          >
            <XIcon size={20} />
          </button>
        </div>
      </div>

      {/* Modal Canvas Body */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 24,
        }}
        onClick={(e) => {
          if (e.target === e.currentTarget) onClose();
        }}
      >
        <div
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: "center center",
            transition: "transform 0.15s ease-out",
            maxWidth: "92vw",
            maxHeight: "82vh",
            boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)",
            borderRadius: 14,
            overflow: "hidden",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {media.type === "svg" && media.svg ? (
            <div
              dangerouslySetInnerHTML={{
                __html: DOMPurify.sanitize(media.svg, { USE_PROFILES: { svg: true } }),
              }}
              style={{
                width: "100%",
                maxWidth: 1040,
                display: "block",
                background: "transparent",
              }}
            />
          ) : media.type === "image" && media.url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={media.url}
              alt={media.title || "رسم تعليمي"}
              style={{
                maxWidth: "100%",
                maxHeight: "80vh",
                display: "block",
                objectFit: "contain",
              }}
            />
          ) : null}
        </div>
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
  const [suggestedReplies, setSuggestedReplies] = useState<string[]>([]);
  const [threads, setThreads] = useState<ChatThreadItem[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [showThreadsDrawer, setShowThreadsDrawer] = useState(false);
  const [loadingThreads, setLoadingThreads] = useState(false);
  const [selectedMedia, setSelectedMedia] = useState<ChatMedia | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
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
    const timer = window.setTimeout(() => void loadThreads(), 0);
    return () => window.clearTimeout(timer);
  }, [loadThreads]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, sending]);

  async function handleSelectThread(threadId: string) {
    if (threadId === activeThreadId) {
      setShowThreadsDrawer(false);
      return;
    }
    setActiveThreadId(threadId);
    setError(null);
    setShowThreadsDrawer(false);
    setSuggestedReplies([]);
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
    setSuggestedReplies([]);
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
      id: createLocalMessageId("user"),
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
        `/api/v1/subjects/${subjectId}/chat`,
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
        id: createLocalMessageId("assistant"),
        role: "assistant",
        content: response.answer,
        timestamp: new Date(),
        no_resources: response.no_resources,
        out_of_scope: response.out_of_scope,
        media: response.media_type
          ? {
              type: response.media_type,
              url: response.media_url || undefined,
              svg: response.media_svg || undefined,
              title: response.media_title || undefined,
            }
          : undefined,
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setSuggestedReplies(response.suggested_replies || []);
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
          background: "var(--surface)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            type="button"
            onClick={() => setShowThreadsDrawer((prev) => !prev)}
            className="btn btn-secondary btn-sm"
          >
            <ClockIcon size={14} />
            <span>سجل المحادثات ({threads.length})</span>
          </button>

          <button
            type="button"
            onClick={handleNewChat}
            className="btn btn-primary btn-sm"
          >
            <PlusIcon size={14} />
            <span>محادثة جديدة</span>
          </button>
        </div>

        <div style={{ fontSize: 13, color: "var(--muted)", fontWeight: 600 }}>
          {activeThread ? activeThread.title : "جلسة محادثة جديدة"}
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
            background: "var(--surface)",
            borderLeft: "1px solid var(--line)",
            boxShadow: "var(--shadow-lg)",
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
            <h3 style={{ margin: 0, fontSize: 14.5, fontWeight: 700, color: "var(--ink)", display: "flex", alignItems: "center", gap: 6 }}>
              <ClockIcon size={16} />
              <span>سجل المحادثات السابقة</span>
            </h3>
            <button
              type="button"
              onClick={() => setShowThreadsDrawer(false)}
              className="btn btn-ghost btn-sm"
              style={{ padding: "4px" }}
              aria-label="إغلاق السجل"
            >
              <XIcon size={16} />
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
                    background: activeThreadId === t.id ? "var(--mint)" : "var(--surface-raised)",
                    border: `1.5px solid ${activeThreadId === t.id ? "var(--green)" : "var(--line)"}`,
                    cursor: "pointer",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 8,
                    transition: "all 0.15s ease",
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
                    className="btn btn-ghost btn-sm"
                    title="حذف المحادثة"
                    style={{ color: "var(--danger)", padding: "4px" }}
                  >
                    <TrashIcon size={14} />
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
          gap: 18,
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
                {isUser ? <UserIcon size={13} /> : <BotIcon size={14} style={{ color: "var(--green)" }} />}
                <span>{isUser ? "أنت" : "مساعد ذاكر معي"}</span>
              </span>

              {/* Chat Bubble */}
              <div
                style={{
                  padding: "16px 20px",
                  borderRadius: 14,
                  borderBottomRightRadius: isUser ? 4 : 14,
                  borderBottomLeftRadius: isUser ? 14 : 4,
                  background: isUser ? "var(--green)" : "var(--surface)",
                  color: isUser ? "#ffffff" : "var(--ink)",
                  boxShadow: "var(--shadow-card)",
                  border: isUser ? 0 : "1px solid var(--line)",
                  lineHeight: 1.75,
                  fontSize: 14.5,
                  width: "100%",
                }}
              >
                {/* Out of scope notification card */}
                {msg.out_of_scope && (
                  <div
                    style={{
                      background: "var(--orange-light)",
                      border: "1px solid rgba(217, 119, 54, 0.3)",
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
                    <AlertCircleIcon size={16} style={{ color: "var(--orange)", flexShrink: 0 }} />
                    <span style={{ flex: 1 }}>
                      <strong>استفسار تنظيمي:</strong> أُرسل هذا الاستفسار لإدارة المادة للمتابعة.
                    </span>
                    <Link
                      href="/dashboard?tab=inquiries"
                      className="btn btn-secondary btn-sm"
                      style={{ fontSize: 12, flexShrink: 0, padding: "4px 10px" }}
                    >
                      متابعة استفساراتي ←
                    </Link>
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
                      className="btn btn-secondary btn-sm"
                    >
                      <FolderIcon size={16} />
                      <span>الانتقال لرفع الكتب والمصادر في المكتبة الآن</span>
                    </button>
                  </div>
                )}

                {/* Inline Semantic SVG or Educational Image */}
                {msg.media && (
                  <div
                    style={{
                      marginTop: 14,
                      borderRadius: 12,
                      overflow: "hidden",
                      background: "var(--surface)",
                      border: "1px solid var(--line)",
                      boxShadow: "0 4px 16px rgba(0,0,0,0.06)",
                    }}
                  >
                    {/* Media Card Header with Actions */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "8px 12px",
                        background: "rgba(0, 0, 0, 0.03)",
                        borderBottom: "1px solid var(--line)",
                        gap: 8,
                        flexWrap: "wrap",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <SparklesIcon size={14} style={{ color: "var(--accent)" }} />
                        <span style={{ fontSize: 12.5, fontWeight: "bold", color: "var(--foreground)" }}>
                          {msg.media.title || (msg.media.type === "svg" ? "مخطط مفاهيمي دلالي" : "صورة تعليمية")}
                        </span>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          style={{ fontSize: 11.5, padding: "3px 8px", height: "auto" }}
                          onClick={() => setSelectedMedia(msg.media || null)}
                          title="فتح وتكبير المخطط داخل المنصة"
                        >
                          <MaximizeIcon size={13} />
                          <span>تكبير واستعراض</span>
                        </button>

                        {msg.media.type === "svg" && msg.media.svg && (
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            style={{ fontSize: 11.5, padding: "3px 8px", height: "auto" }}
                            onClick={() => downloadMediaFile(msg.media!, "svg")}
                            title="تنزيل ملف SVG"
                          >
                            <DownloadIcon size={13} />
                            <span>SVG</span>
                          </button>
                        )}

                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          style={{ fontSize: 11.5, padding: "3px 8px", height: "auto" }}
                          onClick={() => downloadMediaFile(msg.media!, "png")}
                          title="تنزيل كصورة PNG"
                        >
                          <DownloadIcon size={13} />
                          <span>PNG</span>
                        </button>
                      </div>
                    </div>

                    {/* Clickable Graphic Viewport */}
                    <div
                      onClick={() => setSelectedMedia(msg.media || null)}
                      style={{
                        padding: 12,
                        cursor: "pointer",
                        position: "relative",
                        transition: "background 0.15s ease",
                      }}
                      title="اضغط للتكبير والاستعراض الكامل داخل المنصة"
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
                          style={{ maxWidth: "100%", height: "auto", display: "block", borderRadius: 8 }}
                        />
                      )}
                    </div>
                  </div>
                )}

                <span
                  suppressHydrationWarning
                  style={{
                    display: "block",
                    marginTop: 6,
                    fontSize: 11,
                    opacity: 0.7,
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
              className="card"
              style={{
                padding: "12px 18px",
                borderRadius: 14,
                color: "var(--muted)",
                fontSize: 13.5,
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <SparklesIcon size={16} style={{ color: "var(--green)" }} />
              <span>المساعد يفكر ويستخرج الشرح من مصادر المادة…</span>
            </div>
          </div>
        )}

        {error && (
          <div
            className="form-error"
            role="alert"
            style={{ textAlign: "center" }}
          >
            {error}
          </div>
        )}
      </div>

      {/* Floating Bottom Section: Prompt Chips + Input Bar */}
      <div
        style={{
          background: "var(--surface)",
          borderTop: "1px solid var(--line)",
          padding: "12px 20px 16px",
        }}
      >
        {/* Dynamic Follow-up Suggestions (Derived only from student's conversation) */}
        {suggestedReplies.length > 0 && (
          <div
            style={{
              display: "flex",
              gap: 8,
              overflowX: "auto",
              paddingBottom: 10,
              scrollbarWidth: "none",
            }}
            aria-label="اقتراحات المتابعة"
          >
            {suggestedReplies.map((prompt, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => void handleSend(prompt)}
                disabled={sending}
                className="btn btn-ghost btn-sm"
                style={{
                  borderRadius: 20,
                  border: "1px solid var(--line)",
                  background: "var(--surface-raised)",
                  fontSize: 12.5,
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                }}
              >
                <LightbulbIcon size={13} style={{ color: "var(--green)" }} />
                <span>{prompt}</span>
              </button>
            ))}
          </div>
        )}

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
            className="input-field"
            style={{
              flex: 1,
              minHeight: 46,
              maxHeight: 120,
              resize: "none",
              lineHeight: 1.5,
            }}
          />

          {/* Send Button */}
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="btn btn-primary"
            style={{ height: 46, padding: "0 22px" }}
          >
            <span>إرسال</span>
            <ChevronLeftIcon size={16} />
          </button>
        </form>
      </div>

      {/* In-Platform Visual Lightbox Modal */}
      {selectedMedia && (
        <MediaLightboxModal
          media={selectedMedia}
          onClose={() => setSelectedMedia(null)}
        />
      )}
    </div>
  );
}
