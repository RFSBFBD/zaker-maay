"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { ClockIcon } from "@/components/icons";

type StudySession = {
  id: string;
  subject_id: string;
  planned_end_at: string;
  remaining_seconds: number;
};

type SubjectOption = {
  id: string;
  name: string;
};

function formatSeconds(seconds: number): string {
  const safe = Math.max(0, seconds);
  const mins = Math.floor(safe / 60);
  const secs = safe % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

export function StudySessionModal({ currentSubjectId }: { currentSubjectId?: string }) {
  const [open, setOpen] = useState(false);
  const [activeSession, setActiveSession] = useState<StudySession | null>(null);
  const [subjects, setSubjects] = useState<SubjectOption[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>(currentSubjectId || "");
  const [durationMinutes, setDurationMinutes] = useState(25);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function getHeaders() {
    const {
      data: { session },
    } = await createClient().auth.getSession();
    if (!session) throw new Error("سجّل الدخول أولاً");
    return { Authorization: `Bearer ${session.access_token}` };
  }

  async function loadState() {
    try {
      const headers = await getHeaders();
      const [current, subList] = await Promise.all([
        apiRequest<StudySession | null>("/api/v1/study-sessions/active", { headers }).catch(() => null),
        apiRequest<SubjectOption[]>("/api/v1/subjects", { headers }).catch(() => []),
      ]);
      setActiveSession(current);
      setSubjects(subList);
      if (!selectedSubjectId && subList.length > 0) {
        setSelectedSubjectId(currentSubjectId || subList[0].id);
      }
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    void loadState();
  }, [currentSubjectId]);

  // Live timer countdown
  useEffect(() => {
    if (!activeSession) return;
    const timer = window.setInterval(() => {
      setActiveSession((prev) => {
        if (!prev) return null;
        const remaining = prev.remaining_seconds - 1;
        if (remaining <= 0) return null;
        return { ...prev, remaining_seconds: remaining };
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [activeSession?.id]);

  async function startSession() {
    if (!selectedSubjectId) {
      setError("اختر المادة الدراسية للجلسة");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const headers = await getHeaders();
      const created = await apiRequest<StudySession>("/api/v1/study-sessions", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          subject_id: selectedSubjectId,
          duration_minutes: durationMinutes,
        }),
      });
      setActiveSession(created);
      setOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر بدء الجلسة.");
    } finally {
      setBusy(false);
    }
  }

  async function endSession() {
    if (!activeSession) return;
    setBusy(true);
    setError(null);
    try {
      const headers = await getHeaders();
      await apiRequest(`/api/v1/study-sessions/${activeSession.id}/end`, {
        method: "POST",
        headers,
      });
      setActiveSession(null);
      setOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر إنهاء الجلسة.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {activeSession ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "7px 14px",
            borderRadius: 20,
            background: "rgba(45, 106, 79, 0.12)",
            border: "1px solid var(--green)",
            color: "var(--green)",
            fontWeight: 700,
            fontSize: 13,
            cursor: "pointer",
            direction: "ltr",
          }}
        >
          <ClockIcon size={16} />
          <span>{formatSeconds(activeSession.remaining_seconds)}</span>
        </button>
      ) : (
        <button
          type="button"
          onClick={() => {
            void loadState();
            setOpen(true);
          }}
          className="text-button"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "7px 14px",
            borderRadius: 8,
            border: "1px solid var(--line)",
            fontSize: 13,
            fontWeight: 600,
            color: "var(--ink)",
            background: "transparent",
            cursor: "pointer",
          }}
        >
          <ClockIcon size={16} style={{ color: "var(--green)" }} />
          <span>تحديد جلسة تركيز</span>
        </button>
      )}

      {open && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.55)",
            backdropFilter: "blur(3px)",
            zIndex: 9999,
            display: "grid",
            placeItems: "center",
            padding: 16,
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpen(false);
          }}
        >
          <div
            style={{
              background: "var(--surface, #fff)",
              color: "var(--ink)",
              borderRadius: 16,
              maxWidth: 440,
              width: "100%",
              padding: 24,
              boxShadow: "0 20px 48px rgba(0,0,0,0.2)",
              direction: "rtl",
              textAlign: "right",
              border: "1px solid var(--line)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 16,
              }}
            >
              <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>
                {activeSession ? "🍅 جلسة المذاكرة الجارية" : "⏱️ تحديد جلسة تركيز جديدة"}
              </h3>
              <button
                type="button"
                onClick={() => setOpen(false)}
                style={{
                  background: "transparent",
                  border: 0,
                  fontSize: 18,
                  cursor: "pointer",
                  color: "var(--muted)",
                }}
              >
                ✕
              </button>
            </div>

            {error && (
              <p
                style={{
                  padding: "8px 12px",
                  borderRadius: 8,
                  background: "#fff0ed",
                  color: "#9b3f32",
                  fontSize: 13,
                  margin: "0 0 14px",
                }}
              >
                {error}
              </p>
            )}

            {activeSession ? (
              <div style={{ textAlign: "center", padding: "16px 0" }}>
                <div
                  style={{
                    fontSize: 48,
                    fontWeight: 800,
                    color: "var(--green)",
                    fontFamily: "'DM Sans', sans-serif",
                    letterSpacing: 2,
                    margin: "12px 0",
                  }}
                >
                  {formatSeconds(activeSession.remaining_seconds)}
                </div>
                <p style={{ color: "var(--muted)", fontSize: 14, margin: "0 0 20px" }}>
                  أحسنت! حافظ على تركيزك، وابتعد عن المشتتات حتى اكتمال المؤقت. ✨
                </p>
                <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
                  <button
                    type="button"
                    onClick={() => void endSession()}
                    disabled={busy}
                    className="session-start"
                    style={{
                      margin: 0,
                      background: "#d9534f",
                      borderColor: "#d9534f",
                      color: "#fff",
                      padding: "10px 22px",
                    }}
                  >
                    {busy ? "جارٍ الحفظ…" : "⏹️ إنهاء الجلسة وحفظ الإنجاز"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="text-button"
                    style={{ padding: "10px 16px" }}
                  >
                    إغلاق والعودة للمذاكرة
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <p style={{ color: "var(--muted)", fontSize: 13, margin: "0 0 16px", lineHeight: 1.6 }}>
                  اختر مدة الجلسة المناسبة ونوع المادة، لنساعدك على استثمار وقتك وتقييم التزامك الأكاديمي.
                </p>

                {/* Subject Selector */}
                {subjects.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                      المادة الدراسية:
                    </label>
                    <select
                      value={selectedSubjectId}
                      onChange={(e) => setSelectedSubjectId(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "10px 12px",
                        borderRadius: 8,
                        border: "1px solid var(--line)",
                        background: "var(--paper)",
                        color: "var(--ink)",
                        font: "inherit",
                        fontSize: 14,
                      }}
                    >
                      {subjects.map((sub) => (
                        <option key={sub.id} value={sub.id}>
                          {sub.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Duration Presets */}
                <div style={{ marginBottom: 18 }}>
                  <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
                    مدة الجلسة بالدقائق:
                  </label>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 10 }}>
                    {[
                      { mins: 15, label: "⚡ 15 دقيقة (مراجعة سريعة)" },
                      { mins: 25, label: "🍅 25 دقيقة (بومودورو قياسي)" },
                      { mins: 45, label: "🎯 45 دقيقة (تركيز عميق)" },
                      { mins: 60, label: "📚 60 دقيقة (جلسة استيعاب)" },
                    ].map((preset) => (
                      <button
                        key={preset.mins}
                        type="button"
                        onClick={() => setDurationMinutes(preset.mins)}
                        style={{
                          padding: "10px 8px",
                          borderRadius: 8,
                          border: durationMinutes === preset.mins ? "2px solid var(--green)" : "1px solid var(--line)",
                          background: durationMinutes === preset.mins ? "rgba(49, 95, 80, 0.1)" : "var(--paper)",
                          color: durationMinutes === preset.mins ? "var(--green)" : "var(--ink)",
                          fontWeight: durationMinutes === preset.mins ? 700 : 500,
                          fontSize: 12,
                          cursor: "pointer",
                          textAlign: "center",
                        }}
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>أو خصص وقتاً:</span>
                    <input
                      type="number"
                      min={5}
                      max={180}
                      value={durationMinutes}
                      onChange={(e) => setDurationMinutes(Math.max(5, Math.min(180, Number(e.target.value))))}
                      style={{
                        width: 70,
                        padding: "6px 8px",
                        borderRadius: 6,
                        border: "1px solid var(--line)",
                        background: "var(--paper)",
                        color: "var(--ink)",
                        textAlign: "center",
                        font: "inherit",
                      }}
                    />
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>دقيقة</span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => void startSession()}
                  disabled={busy || !selectedSubjectId}
                  className="session-start"
                  style={{
                    width: "100%",
                    margin: "10px 0 0",
                    padding: "12px",
                    fontSize: 15,
                    background: "var(--green)",
                    color: "#fff",
                    borderRadius: 10,
                  }}
                >
                  {busy ? "جارٍ البدء…" : "🚀 ابدأ جلسة المذاكرة والتركيز"}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
