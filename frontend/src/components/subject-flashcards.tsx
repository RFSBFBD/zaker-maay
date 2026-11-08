"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type FlashcardItem = {
  front: string;
  back: string;
};

type StudyArtifactResponse = {
  id: string;
  subject_id: string;
  kind: string;
  title: string;
  content: {
    title?: string;
    cards?: Array<{
      front?: string;
      back?: string;
      question?: string;
      answer?: string;
      prompt?: string;
      explanation?: string;
    }>;
    [key: string]: unknown;
  };
  sources: Array<{ source_index?: number; file_name?: string; page_number?: number }>;
  model: string;
  created_at: string;
  cached: boolean;
};

export function SubjectFlashcards({ subjectId }: { subjectId: string }) {
  const [artifacts, setArtifacts] = useState<StudyArtifactResponse[]>([]);
  const [activeArtifact, setActiveArtifact] = useState<StudyArtifactResponse | null>(null);
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getHeaders = useCallback(async () => {
    const {
      data: { session },
      error: sessionError,
    } = await createClient().auth.getSession();
    if (sessionError || !session) throw new Error("انتهت الجلسة. سجّل الدخول مجدداً.");
    return { Authorization: `Bearer ${session.access_token}` };
  }, []);

  const loadArtifacts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const headers = await getHeaders();
      const list = await apiRequest<StudyArtifactResponse[]>(
        `/api/v1/subjects/${subjectId}/study-artifacts?kind=flashcards`,
        { headers }
      );
      setArtifacts(list);
      if (list.length > 0) {
        setActiveArtifact((current) => current ?? list[0]);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر تحميل البطاقات التعليمية.");
    } finally {
      setLoading(false);
    }
  }, [getHeaders, subjectId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadArtifacts(), 0);
    return () => window.clearTimeout(timer);
  }, [loadArtifacts]);

  async function handleCreateFlashcards() {
    setCreating(true);
    setError(null);
    try {
      const headers = await getHeaders();
      const created = await apiRequest<StudyArtifactResponse>(
        `/api/v1/subjects/${subjectId}/study-artifacts`,
        {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({ kind: "flashcards" }),
        },
        55_000
      );
      // Replace any existing flashcard artifact for this subject with the new one,
      // instead of adding a duplicate. This prevents duplicate decks when user
      // regenerates flashcards.
      setArtifacts((prev) => {
        const existingIndex = prev.findIndex((a) => a.kind === "flashcards");
        if (existingIndex >= 0) {
          // Replace existing: remove old, add new at beginning
          const newList = [...prev];
          newList.splice(existingIndex, 1, created);
          return [created, ...newList.filter((a) => a.id !== created.id)];
        }
        // No existing: add new at beginning
        return [created, ...prev.filter((a) => a.id !== created.id)];
      });
      setActiveArtifact(created);
      setCurrentCardIndex(0);
      setIsFlipped(false);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "تعذر إنشاء البطاقات. تأكد من توفر مصادر نصية كافية في مكتبة المادة."
      );
    } finally {
      setCreating(false);
    }
  }

  // Extract normalized cards from artifact
  const cards: FlashcardItem[] = [];
  if (activeArtifact?.content?.cards && Array.isArray(activeArtifact.content.cards)) {
    for (const rawCard of activeArtifact.content.cards) {
      const front = rawCard.front || rawCard.question || rawCard.prompt || "سؤال/مفهوم";
      const back = rawCard.back || rawCard.answer || rawCard.explanation || "شرح الإجابة";
      cards.push({ front, back });
    }
  }

  const currentCard = cards[currentCardIndex];

  function handleNext() {
    if (currentCardIndex < cards.length - 1) {
      setCurrentCardIndex((prev) => prev + 1);
      setIsFlipped(false);
    }
  }

  function handlePrev() {
    if (currentCardIndex > 0) {
      setCurrentCardIndex((prev) => prev - 1);
      setIsFlipped(false);
    }
  }

  return (
    <div style={{ maxWidth: 840, margin: "0 auto", padding: "20px 16px" }}>
      {/* Top Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
          marginBottom: 24,
        }}
      >
        <div>
          <h2 style={{ margin: "0 0 4px", fontSize: 20, color: "var(--ink)" }}>
            🃏 بطاقات الاستذكار السريع (Flashcards)
          </h2>
          <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>
            مراجعة ذكية وسريعة لأهم المفاهيم، المصطلحات، والتعاريف عبر تقنية الاسترجاع النشط (Active Recall).
          </p>
        </div>

        <button
          type="button"
          onClick={() => void handleCreateFlashcards()}
          disabled={creating}
          className="session-start"
          style={{
            margin: 0,
            padding: "10px 20px",
            fontSize: 14,
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span>{creating ? "💭" : "✨"}</span>
          <span>{creating ? "جاري استخراج البطاقات…" : "توليد حزمة بطاقات جديدة"}</span>
        </button>
      </div>

      {error && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: 8,
            background: "#fff0ed",
            color: "#9b3f32",
            fontSize: 14,
            marginBottom: 20,
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {loading ? (
        <p className="state-card">جارٍ تحميل البطاقات التعليمية…</p>
      ) : cards.length > 0 && currentCard ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 20 }}>
          {/* Card Selector / Set Info */}
          {artifacts.length > 1 && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}>
              {artifacts.map((art, idx) => (
                <button
                  key={art.id}
                  type="button"
                  onClick={() => {
                    setActiveArtifact(art);
                    setCurrentCardIndex(0);
                    setIsFlipped(false);
                  }}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 20,
                    border: "1px solid var(--line)",
                    background: activeArtifact?.id === art.id ? "var(--green)" : "var(--surface, #fff)",
                    color: activeArtifact?.id === art.id ? "#fff" : "var(--ink)",
                    fontSize: 12,
                    cursor: "pointer",
                    fontWeight: 600,
                  }}
                >
                  حزمة {idx + 1}: {art.title.slice(0, 24)}…
                </button>
              ))}
            </div>
          )}

          {activeArtifact?.cached && (
            <div
              style={{
                padding: '6px 14px',
                borderRadius: 20,
                background: 'rgba(45, 106, 79, 0.08)',
                border: '1px solid var(--green, #2d6a4f)',
                fontSize: 12,
                color: 'var(--green, #2d6a4f)',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <span>⚡</span>
              <span>حزمة بطاقات محفوظة مسبقاً لمصادر المادة الحالية.</span>
            </div>
          )}

          {/* Progress Counter */}
          <div
            style={{
              fontSize: 13,
              fontWeight: 700,
              color: "var(--muted)",
              letterSpacing: 0.5,
            }}
          >
            بطاقة {currentCardIndex + 1} من {cards.length}
          </div>

          {/* REAL 3D FLIP CARD PERSPECTIVE CONTAINER */}
          <div
            onClick={() => setIsFlipped((prev) => !prev)}
            style={{
              width: "100%",
              maxWidth: 580,
              minHeight: 320,
              perspective: 1200,
              cursor: "pointer",
              userSelect: "none",
            }}
          >
            <div
              style={{
                position: "relative",
                width: "100%",
                minHeight: 320,
                transformStyle: "preserve-3d",
                transition: "transform 0.6s cubic-bezier(0.4, 0, 0.2, 1)",
                transform: isFlipped ? "rotateY(180deg)" : "rotateY(0deg)",
              }}
            >
              {/* FRONT FACE (Question) */}
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  backfaceVisibility: "hidden",
                  WebkitBackfaceVisibility: "hidden",
                  background: "var(--surface, #fff)",
                  border: "2px solid var(--line)",
                  borderRadius: 20,
                  padding: "36px 30px",
                  boxShadow: "0 10px 30px rgba(0,0,0,0.06)",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  alignItems: "center",
                  textAlign: "center",
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: "var(--muted)",
                    background: "rgba(0,0,0,0.05)",
                    padding: "4px 14px",
                    borderRadius: 20,
                  }}
                >
                  ❓ السؤال / المفهوم (الوجه الأمامي)
                </span>
                <div style={{ margin: "24px 0", width: "100%" }}>
                  <p
                    style={{
                      margin: 0,
                      fontSize: 19,
                      lineHeight: 1.8,
                      fontWeight: 600,
                      color: "var(--ink)",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {currentCard.front}
                  </p>
                </div>
                <span style={{ fontSize: 12, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6 }}>
                  <span>🔄</span>
                  <span>انقر لقلب البطاقة ومعرفة الإجابة</span>
                </span>
              </div>

              {/* BACK FACE (Answer) */}
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  backfaceVisibility: "hidden",
                  WebkitBackfaceVisibility: "hidden",
                  transform: "rotateY(180deg)",
                  background: "var(--mint, #f2f7f3)",
                  border: "2px solid var(--green)",
                  borderRadius: 20,
                  padding: "36px 30px",
                  boxShadow: "0 12px 32px rgba(46, 125, 50, 0.12)",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  alignItems: "center",
                  textAlign: "center",
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: "var(--green)",
                    background: "rgba(100, 140, 90, 0.2)",
                    padding: "4px 14px",
                    borderRadius: 20,
                  }}
                >
                  💡 الإجابة والشرح (الوجه الخلفي)
                </span>
                <div style={{ margin: "24px 0", width: "100%" }}>
                  <p
                    style={{
                      margin: 0,
                      fontSize: 18,
                      lineHeight: 1.8,
                      fontWeight: 600,
                      color: "var(--ink)",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {currentCard.back}
                  </p>
                </div>
                <span style={{ fontSize: 12, color: "var(--green)", display: "flex", alignItems: "center", gap: 6 }}>
                  <span>✓</span>
                  <span>انقر للعودة إلى السؤال</span>
                </span>
              </div>
            </div>
          </div>

          {/* Navigation Controls */}
          <div style={{ display: "flex", gap: 14, alignItems: "center", marginTop: 8 }}>
            <button
              type="button"
              onClick={handlePrev}
              disabled={currentCardIndex === 0}
              className="text-button"
              style={{
                padding: "10px 20px",
                border: "1px solid var(--line)",
                borderRadius: 10,
                background: "var(--surface, #fff)",
                cursor: currentCardIndex === 0 ? "not-allowed" : "pointer",
                opacity: currentCardIndex === 0 ? 0.4 : 1,
                fontSize: 14,
                fontWeight: 600,
              }}
            >
              → البطاقة السابقة
            </button>

            <button
              type="button"
              onClick={() => setIsFlipped((prev) => !prev)}
              className="session-start"
              style={{
                margin: 0,
                padding: "10px 24px",
                background: "var(--paper)",
                border: "1px solid var(--line)",
                color: "var(--ink)",
                fontSize: 14,
              }}
            >
              🔄 اقلب البطاقة
            </button>

            <button
              type="button"
              onClick={handleNext}
              disabled={currentCardIndex === cards.length - 1}
              className="session-start"
              style={{
                margin: 0,
                padding: "10px 24px",
                cursor: currentCardIndex === cards.length - 1 ? "not-allowed" : "pointer",
                opacity: currentCardIndex === cards.length - 1 ? 0.4 : 1,
                fontSize: 14,
                fontWeight: 600,
              }}
            >
              البطاقة التالية ←
            </button>
          </div>
        </div>
      ) : (
        /* Empty State */
        <div
          style={{
            textAlign: "center",
            padding: "48px 20px",
            background: "var(--surface, #fff)",
            border: "1px dashed var(--line)",
            borderRadius: 14,
          }}
        >
          <span style={{ fontSize: 44, display: "block", marginBottom: 12 }}>🃏</span>
          <h3 style={{ margin: "0 0 6px", fontSize: 18, color: "var(--ink)" }}>
            لا توجد بطاقات استذكار لهذه المادة بعد
          </h3>
          <p style={{ margin: "0 0 18px", fontSize: 14, color: "var(--muted)" }}>
            اضغط على زر «توليد حزمة بطاقات جديدة» ليقوم الذكاء الاصطناعي باستخراج بطاقات ذكية من كتب وملازم المادة.
          </p>
          <button
            type="button"
            onClick={() => void handleCreateFlashcards()}
            disabled={creating}
            className="session-start"
            style={{ margin: "0 auto", padding: "10px 24px" }}
          >
            {creating ? "جاري التوليد…" : "توليد أول حزمة بطاقات الآن ✨"}
          </button>
        </div>
      )}
    </div>
  );
}
