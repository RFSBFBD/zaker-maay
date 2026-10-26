"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type QuizSummary = {
  id: string;
  title: string;
  question_count: number;
  created_at: string;
};

type QuestionView = {
  id: string;
  prompt: string;
  options: string[];
  source_file?: string | null;
  source_page?: number | null;
};

type QuizView = {
  id: string;
  subject_id: string;
  title: string;
  created_at: string;
  questions: QuestionView[];
};

type QuestionReview = {
  question_id: string;
  prompt: string;
  options: string[];
  selected_answer: number;
  correct_answer: number;
  is_correct: boolean;
  explanation: string;
  source_file?: string | null;
  source_page?: number | null;
};

type AttemptResponse = {
  id: string;
  quiz_id: string;
  score: number;
  total_questions: number;
  submitted_at: string;
  review: QuestionReview[];
};

export function SubjectQuizzes({ subjectId }: { subjectId: string }) {
  const [quizzes, setQuizzes] = useState<QuizSummary[]>([]);
  const [activeQuiz, setActiveQuiz] = useState<QuizView | null>(null);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [attemptResult, setAttemptResult] = useState<AttemptResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getHeaders = useCallback(async () => {
    const {
      data: { session },
      error: sessionError,
    } = await createClient().auth.getSession();
    if (sessionError || !session) throw new Error("انتهت الجلسة. سجّل الدخول مجدداً.");
    return { Authorization: `Bearer ${session.access_token}` };
  }, []);

  const loadQuizzes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const headers = await getHeaders();
      const list = await apiRequest<QuizSummary[]>(`/api/v1/subjects/${subjectId}/quizzes`, { headers });
      setQuizzes(list);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر تحميل قائمة الاختبارات.");
    } finally {
      setLoading(false);
    }
  }, [getHeaders, subjectId]);

  useEffect(() => {
    void loadQuizzes();
  }, [loadQuizzes]);

  async function handleCreateQuiz() {
    setCreating(true);
    setError(null);
    try {
      const headers = await getHeaders();
      const created = await apiRequest<QuizView>(`/api/v1/subjects/${subjectId}/quizzes`, {
        method: "POST",
        headers,
      });
      setQuizzes((prev) => [
        {
          id: created.id,
          title: created.title,
          question_count: created.questions.length,
          created_at: created.created_at,
        },
        ...prev,
      ]);
      setActiveQuiz(created);
      setSelectedAnswers({});
      setAttemptResult(null);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "تعذر إنشاء الاختبار. تأكد من رفع مصادر وملازم للمادة أولاً."
      );
    } finally {
      setCreating(false);
    }
  }

  async function handleOpenQuiz(quizId: string) {
    setLoading(true);
    setError(null);
    setAttemptResult(null);
    setSelectedAnswers({});
    try {
      const headers = await getHeaders();
      const quiz = await apiRequest<QuizView>(`/api/v1/subjects/${subjectId}/quizzes/${quizId}`, { headers });
      setActiveQuiz(quiz);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر فتح الاختبار.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmitAttempt() {
    if (!activeQuiz) return;
    const answeredCount = Object.keys(selectedAnswers).length;
    if (answeredCount < activeQuiz.questions.length) {
      setError(`يرجى الإجابة على جميع الأسئلة أولاً (${answeredCount} من ${activeQuiz.questions.length} تمت إجابتها).`);
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const headers = await getHeaders();
      const payload = {
        answers: activeQuiz.questions.map((q) => ({
          question_id: q.id,
          selected_answer: selectedAnswers[q.id] ?? 0,
        })),
      };
      const result = await apiRequest<AttemptResponse>(
        `/api/v1/subjects/${subjectId}/quizzes/${activeQuiz.id}/attempts`,
        {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      setAttemptResult(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر تسليم الاختبار.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "20px 16px" }}>
      {/* Top Header Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
          marginBottom: 20,
        }}
      >
        <div>
          <h2 style={{ margin: "0 0 4px", fontSize: 20, color: "var(--ink)" }}>
            📝 اختبر فهمك واستيعابك الذكي
          </h2>
          <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>
            اختبارات تفاعلية يولدها الذكاء الاصطناعي مستندة بدقة على محتوى كتبك ومذكراتك المرفوعة.
          </p>
        </div>

        <button
          type="button"
          onClick={() => void handleCreateQuiz()}
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
          <span>{creating ? "💭" : "➕"}</span>
          <span>{creating ? "جاري صياغة اختبار جديد…" : "توليد اختبار ذكي جديد"}</span>
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
            marginBottom: 16,
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {/* VIEW 1: ACTIVE QUIZ IN PROGRESS OR REVIEW */}
      {activeQuiz ? (
        <div
          style={{
            background: "var(--surface, #fff)",
            border: "1px solid var(--line)",
            borderRadius: 14,
            padding: "24px 20px",
            boxShadow: "0 2px 12px rgba(0,0,0,0.03)",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              borderBottom: "1px solid var(--line)",
              paddingBottom: 16,
              marginBottom: 20,
            }}
          >
            <div>
              <h3 style={{ margin: "0 0 6px", fontSize: 18, color: "var(--ink)" }}>{activeQuiz.title}</h3>
              <span style={{ fontSize: 12, color: "var(--muted)" }}>
                عدد الأسئلة: {activeQuiz.questions.length} أسئلة اختيار من متعدد
              </span>
            </div>
            <button
              type="button"
              onClick={() => {
                setActiveQuiz(null);
                setAttemptResult(null);
                setSelectedAnswers({});
              }}
              className="text-button"
              style={{ fontSize: 13 }}
            >
              ← العودة للاختبارات
            </button>
          </div>

          {/* If Result Available */}
          {attemptResult && (
            <div
              style={{
                background: "rgba(100, 140, 90, 0.08)",
                border: "1px solid var(--green)",
                borderRadius: 12,
                padding: "20px",
                marginBottom: 24,
                textAlign: "center",
              }}
            >
              <span style={{ fontSize: 36, display: "block", marginBottom: 6 }}>
                {attemptResult.score === attemptResult.total_questions ? "🌟" : "🎯"}
              </span>
              <h4 style={{ margin: "0 0 6px", fontSize: 20, color: "var(--ink)" }}>
                نتيجتك: {attemptResult.score} من {attemptResult.total_questions} (
                {Math.round((attemptResult.score / attemptResult.total_questions) * 100)}%)
              </h4>
              <p style={{ margin: 0, fontSize: 14, color: "var(--muted)" }}>
                {attemptResult.score === attemptResult.total_questions
                  ? "أداء مذهل ومثالي! لقد استوعبت محتوى المادة بامتياز."
                  : "أداء جيد! راجع الإجابات والتفسيرات المرجعية أدناه لتعزيز النقاط الصعبة."}
              </p>
            </div>
          )}

          {/* Questions Stream */}
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            {activeQuiz.questions.map((q, qIndex) => {
              const review = attemptResult?.review.find((r) => r.question_id === q.id);
              const isSubmitted = !!review;

              return (
                <div
                  key={q.id}
                  style={{
                    background: "var(--paper)",
                    border: `1px solid ${
                      isSubmitted ? (review.is_correct ? "var(--green)" : "#e06c58") : "var(--line)"
                    }`,
                    borderRadius: 12,
                    padding: "18px 20px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                    <h4 style={{ margin: "0 0 14px", fontSize: 15, lineHeight: 1.6, color: "var(--ink)" }}>
                      <span style={{ fontWeight: 700, color: "var(--green)" }}>س{qIndex + 1}: </span>
                      {q.prompt}
                    </h4>
                    {isSubmitted && (
                      <span
                        style={{
                          fontSize: 12,
                          fontWeight: 700,
                          padding: "3px 8px",
                          borderRadius: 6,
                          whiteSpace: "nowrap",
                          background: review.is_correct ? "#e7f0e5" : "#fff0ed",
                          color: review.is_correct ? "#2e6930" : "#9b3f32",
                        }}
                      >
                        {review.is_correct ? "إجابة صحيحة ✔" : "إجابة خاطئة ✖"}
                      </span>
                    )}
                  </div>

                  {/* Options */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {q.options.map((option, optIdx) => {
                      const isSelected = selectedAnswers[q.id] === optIdx;
                      let optionBg = "var(--surface, #fff)";
                      let optionBorder = "var(--line)";
                      let optionColor = "var(--ink)";

                      if (isSubmitted) {
                        if (optIdx === review.correct_answer) {
                          optionBg = "#e7f0e5";
                          optionBorder = "var(--green)";
                          optionColor = "#2e6930";
                        } else if (isSelected && !review.is_correct) {
                          optionBg = "#fff0ed";
                          optionBorder = "#e06c58";
                          optionColor = "#9b3f32";
                        }
                      } else if (isSelected) {
                        optionBg = "rgba(100, 140, 90, 0.12)";
                        optionBorder = "var(--green)";
                        optionColor = "var(--green)";
                      }

                      return (
                        <label
                          key={optIdx}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 12,
                            padding: "12px 16px",
                            borderRadius: 10,
                            border: `1.5px solid ${optionBorder}`,
                            background: optionBg,
                            color: optionColor,
                            cursor: isSubmitted ? "default" : "pointer",
                            transition: "all 0.15s",
                            fontSize: 14,
                            fontWeight: isSelected ? 600 : 400,
                          }}
                        >
                          <input
                            type="radio"
                            name={`q-${q.id}`}
                            checked={isSelected}
                            disabled={isSubmitted}
                            onChange={() => {
                              setSelectedAnswers((prev) => ({ ...prev, [q.id]: optIdx }));
                            }}
                            style={{ accentColor: "var(--green)", cursor: "pointer" }}
                          />
                          <span>{option}</span>
                        </label>
                      );
                    })}
                  </div>

                  {/* Explanation & Source Reference */}
                  {isSubmitted && (
                    <div
                      style={{
                        marginTop: 14,
                        padding: "12px 14px",
                        borderRadius: 8,
                        background: "rgba(0,0,0,0.02)",
                        borderRight: "3px solid var(--green)",
                        fontSize: 13,
                        lineHeight: 1.6,
                      }}
                    >
                      <strong style={{ display: "block", marginBottom: 4, color: "var(--ink)" }}>
                        💡 التفسير والشرح:
                      </strong>
                      <p style={{ margin: "0 0 6px", color: "var(--ink)" }}>{review.explanation}</p>
                      {review.source_file && (
                        <span style={{ fontSize: 11, color: "var(--muted)", display: "block" }}>
                          📖 مستند إلى المرجع: {review.source_file}
                          {review.source_page ? ` (صفحة ${review.source_page})` : ""}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Action Footer */}
          <div style={{ marginTop: 28, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            {!attemptResult ? (
              <button
                type="button"
                onClick={() => void handleSubmitAttempt()}
                disabled={submitting}
                className="session-start"
                style={{
                  margin: 0,
                  padding: "12px 32px",
                  fontSize: 15,
                  fontWeight: 700,
                }}
              >
                {submitting ? "جاري تقييم النتيجة…" : "تسليم الإجابات وتقييم النتيجة 🎯"}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setAttemptResult(null);
                  setSelectedAnswers({});
                }}
                className="session-start"
                style={{ margin: 0, padding: "10px 24px", fontSize: 14 }}
              >
                إعادة حل هذا الاختبار 🔄
              </button>
            )}

            <button
              type="button"
              onClick={() => {
                setActiveQuiz(null);
                setAttemptResult(null);
              }}
              className="text-button"
            >
              العودة لقائمة الاختبارات
            </button>
          </div>
        </div>
      ) : (
        /* VIEW 2: QUIZZES LIST */
        <div>
          {loading ? (
            <p className="state-card">جارٍ تحميل الاختبارات…</p>
          ) : quizzes.length === 0 ? (
            <div
              style={{
                textAlign: "center",
                padding: "48px 20px",
                background: "var(--surface, #fff)",
                border: "1px dashed var(--line)",
                borderRadius: 14,
              }}
            >
              <span style={{ fontSize: 44, display: "block", marginBottom: 12 }}>📝</span>
              <h3 style={{ margin: "0 0 6px", fontSize: 18, color: "var(--ink)" }}>
                لم يتم إنشاء أي اختبارات لهذه المادة بعد
              </h3>
              <p style={{ margin: "0 0 18px", fontSize: 14, color: "var(--muted)" }}>
                انقر على زر «توليد اختبار ذكي جديد» ليقوم المساعد بصياغة أسئلة تقيس استيعابك من مراجع المادة.
              </p>
              <button
                type="button"
                onClick={() => void handleCreateQuiz()}
                disabled={creating}
                className="session-start"
                style={{ margin: "0 auto", padding: "10px 24px" }}
              >
                {creating ? "جاري التوليد…" : "توليد أول اختبار الآن 🚀"}
              </button>
            </div>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                gap: 16,
              }}
            >
              {quizzes.map((quiz) => (
                <div
                  key={quiz.id}
                  style={{
                    background: "var(--surface, #fff)",
                    border: "1px solid var(--line)",
                    borderRadius: 12,
                    padding: "20px",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    gap: 14,
                    boxShadow: "0 2px 8px rgba(0,0,0,0.03)",
                  }}
                >
                  <div>
                    <span style={{ fontSize: 24, display: "block", marginBottom: 8 }}>📋</span>
                    <h4 style={{ margin: "0 0 6px", fontSize: 16, color: "var(--ink)", fontWeight: 700 }}>
                      {quiz.title}
                    </h4>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>
                      {quiz.question_count} أسئلة اختبارية
                    </span>
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
                    <span style={{ fontSize: 11, color: "var(--muted)" }}>
                      {new Date(quiz.created_at).toLocaleDateString("ar-EG", {
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                    <button
                      type="button"
                      onClick={() => void handleOpenQuiz(quiz.id)}
                      className="session-start"
                      style={{ margin: 0, padding: "6px 16px", fontSize: 13 }}
                    >
                      ابدأ الاختبار ✍️
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
