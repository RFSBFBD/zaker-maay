"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { apiRequest } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Resource = {
  id: string;
  subject_id: string;
  uploaded_by: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  processing_status: "pending" | "ready" | "no_text" | "unsupported" | "truncated" | "failed";
  transcript_language: string | null;
  audio_duration_seconds: number | null;
  has_transcript: boolean;
  created_at: string;
};

type ResourceTranscript = {
  language: string;
  transcript: string;
  model: string;
  audio_duration_seconds: number;
  timestamp_quality: "not_provided";
};

type YouTubeLink = {
  id: string;
  subject_id: string;
  owner_id: string;
  video_id: string;
  url: string;
  title: string | null;
  created_at: string;
};

type Subject = {
  id: string;
  name: string;
  description: string | null;
};

type SignedDownload = {
  download_url: string;
  expires_in_seconds: number;
};

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} كيلوبايت`
    : `${(bytes / (1024 * 1024)).toFixed(1)} ميغابايت`;
}

function processingLabel(status: Resource["processing_status"]): string {
  // Return plain text without emoji for cleaner UI
  return {
    pending: "قيد المعالجة",
    ready: "النص جاهز",
    no_text: "لم يُستخرج نص",
    unsupported: "لا يدعم استخراج النص",
    truncated: "عولج جزء من النص",
    failed: "فشل المعالجة",
  }[status];
  return {
    pending: "⏳ بانتظار المعالجة",
    ready: "✅ النص جاهز للشرح والبحث",
    no_text: "⚠️ لم يُستخرج نص",
    unsupported: "ℹ️ لا يدعم استخراج النص",
    truncated: "📄 عولج جزء من النص",
    failed: "❌ تعذرت المعالجة",
  }[status];
}

export function SubjectLibrary({ subjectId }: { subjectId: string }) {
  const [resources, setResources] = useState<Resource[]>([]);
  const [youtubeLinks, setYoutubeLinks] = useState<YouTubeLink[]>([]);
  const [subject, setSubject] = useState<Subject | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [downloadLinks, setDownloadLinks] = useState<Record<string, string>>({});
  const [videoUrl, setVideoUrl] = useState("");
  const [videoBusy, setVideoBusy] = useState(false);
  const [transcribeAudio, setTranscribeAudio] = useState(false);
  const [transcripts, setTranscripts] = useState<Record<string, ResourceTranscript>>({});

  const getHeaders = useCallback(async () => {
    const {
      data: { session },
      error: sessionError,
    } = await createClient().auth.getSession();
    if (sessionError || !session) throw new Error("انتهت جلسة الدخول. سجّل الدخول مجددًا.");
    return { Authorization: `Bearer ${session.access_token}` };
  }, []);

  const loadResources = useCallback(async () => {
    const headers = await getHeaders();
    const [details, data, videoList] = await Promise.all([
      apiRequest<Subject>(`/api/v1/subjects/${subjectId}`, { headers }),
      apiRequest<Resource[]>(`/api/v1/subjects/${subjectId}/resources`, { headers }),
      apiRequest<YouTubeLink[]>(`/api/v1/subjects/${subjectId}/youtube-links`, { headers }),
    ]);
    setSubject(details);
    setResources(data);
    setYoutubeLinks(videoList);
  }, [getHeaders, subjectId]);

  useEffect(() => {
    let mounted = true;
    void (async () => {
      try {
        await loadResources();
      } catch (cause) {
        if (mounted) setError(cause instanceof Error ? cause.message : "تعذر تحميل مكتبة المادة.");
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [loadResources]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("file") as HTMLInputElement | null;
    const file = input?.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    setNotice(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const headers = await getHeaders();
      const query = transcribeAudio ? "?transcribe_audio=true" : "";
      const created = await apiRequest<Resource>(`/api/v1/subjects/${subjectId}/resources${query}`, {
        method: "POST",
        headers,
        body: formData,
      });
      setResources((current) => [created, ...current]);
      form.reset();
      setTranscribeAudio(false);
      setNotice(
        created.has_transcript
          ? "أُضيف الملف الصوتي وجرى إرساله للتفريغ الذكي بنجاح."
          : "رُفع الملف إلى مكتبة المادة بنجاح وهو متاح للمساعد الذكي."
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر رفع الملف.");
    } finally {
      setUploading(false);
    }
  }

  async function prepareDownload(resourceId: string) {
    try {
      const headers = await getHeaders();
      const signed = await apiRequest<SignedDownload>(
        `/api/v1/subjects/${subjectId}/resources/${resourceId}/download`,
        { headers }
      );
      setDownloadLinks((current) => ({ ...current, [resourceId]: signed.download_url }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر تجهيز رابط التنزيل.");
    }
  }

  async function loadTranscript(resourceId: string) {
    try {
      const headers = await getHeaders();
      const data = await apiRequest<ResourceTranscript>(
        `/api/v1/subjects/${subjectId}/resources/${resourceId}/transcript`,
        { headers }
      );
      setTranscripts((current) => ({ ...current, [resourceId]: data }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر تحميل تفريغ الصوت.");
    }
  }

  async function addVideo(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!videoUrl.trim()) return;
    setVideoBusy(true);
    setError(null);
    setNotice(null);
    try {
      const headers = await getHeaders();
      const created = await apiRequest<YouTubeLink>(`/api/v1/subjects/${subjectId}/youtube-links`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ url: videoUrl.trim() }),
      });
      setYoutubeLinks((current) => [created, ...current]);
      setVideoUrl("");
      setNotice("أُضيف رابط الفيديو التعليمي إلى مراجع المادة.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر إضافة رابط الفيديو.");
    } finally {
      setVideoBusy(false);
    }
  }

  async function removeVideo(linkId: string) {
    if (!window.confirm("هل تريد إزالة هذا الفيديو من مراجع المادة؟")) return;
    setError(null);
    try {
      const headers = await getHeaders();
      await apiRequest<void>(`/api/v1/subjects/${subjectId}/youtube-links/${linkId}`, {
        method: "DELETE",
        headers,
      });
      setYoutubeLinks((current) => current.filter((link) => link.id !== linkId));
      setNotice("حُذف رابط الفيديو من مراجع المادة.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر حذف رابط الفيديو.");
    }
  }

  return (
    <div className="library-wrapper" style={{ maxWidth: 960, margin: "0 auto", paddingBottom: 60 }}>
      <div style={{ marginBottom: 24 }}>
        <p className="eyebrow">📁 مكتبة المادة والمراجع المعتمدة</p>
        <h1 style={{ fontSize: 28, margin: "6px 0 10px" }}>
          مراجع <span>{subject?.name ?? "المادة"}</span>
        </h1>
        <p className="intro" style={{ margin: 0 }}>
          {subject?.description || "ارفع كتبك والمحاضرات الصوتية لتكون مصدراً وحيداً يشرح منه المساعد الذكي."}
        </p>
      </div>

      {error && <p className="state-card form-error" role="alert">{error}</p>}
      {notice && <p className="state-card form-notice" role="status">{notice}</p>}

      {/* Upload Box */}
      <form className="upload-panel" onSubmit={upload} style={{ marginBottom: 32 }}>
        <h3 style={{ fontSize: 18, marginBottom: 8 }}>📤 إضافة كتاب أو ملزمة أو تسجيل صوتي</h3>
        <label htmlFor="resource-file" style={{ fontSize: 14, color: "var(--muted)" }}>
          يدعم ملفات PDF، المستندات النصية (TXT/DOCX)، والتسجيلات الصوتية (MP3/WAV/M4A) حتى 20 ميغابايت
        </label>
        <div className="upload-row" style={{ marginTop: 12 }}>
          <input
            id="resource-file"
            name="file"
            type="file"
            accept=".pdf,.txt,.docx,.mp3,.wav,.m4a,.webm"
            required
            disabled={uploading}
          />
          <button className="session-start" type="submit" disabled={uploading}>
            {uploading ? "⏳ جارٍ الرفع والمعالجة…" : "⬆️ رفع إلى مكتبة المادة"}
          </button>
        </div>
        <label className="consent-choice" style={{ marginTop: 12 }}>
          <input
            type="checkbox"
            checked={transcribeAudio}
            onChange={(event) => setTranscribeAudio(event.target.checked)}
            disabled={uploading}
          />
          🎙️ تفعيل التفريغ النصي الصوتي الذكي بواسطة Google Gemini (للتسجيلات الصوتية حتى 30 دقيقة).
        </label>
        <p className="privacy-note">
          عند تفعيل هذا الخيار يتم استخراج النص وتحويله لمقاطع دراسية يستشهد بها المساعد في إجاباته.
        </p>
      </form>

      {/* Uploaded Resources List */}
      <section style={{ marginBottom: 40 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h2 style={{ fontSize: 20 }}>📚 الملفات والكتب المرفوعة ({resources.length})</h2>
        </div>

        {loading && <p className="state-card" role="status">جارٍ تحميل الملفات والمراجع…</p>}
        {!loading && resources.length === 0 && (
          <div className="state-card" style={{ textAlign: "center", padding: "32px 20px" }}>
            <span style={{ fontSize: 36, display: "block", marginBottom: 8 }}>📖</span>
            <strong>لا توجد ملفات في مكتبة هذه المادة بعد.</strong>
            <p style={{ margin: "6px 0 0", color: "var(--muted)", fontSize: 14 }}>
              ارفع مذكرتك أو كتابك بصيغة PDF أو تسجيل المحاضرة من النموذج أعلاه لكي يبدأ المساعد بشرحه.
            </p>
          </div>
        )}

        {resources.length > 0 && (
          <div className="resource-list" aria-label="ملفات المادة">
            {resources.map((resource) => (
              <article className="resource-item" key={resource.id}>
                <div>
                  <h3 style={{ fontSize: 17, margin: "0 0 6px" }}>📄 {resource.file_name}</h3>
                  <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>
                    {formatSize(resource.size_bytes)} · {new Date(resource.created_at).toLocaleDateString("ar-EG")} ·{" "}
                    <span style={{ fontWeight: 600 }}>
                      {resource.mime_type.startsWith("audio/") && !resource.has_transcript
                        ? "ملف صوتي محفوظ"
                        : processingLabel(resource.processing_status)}
                    </span>
                    {resource.transcript_language ? ` · لغة التفريغ: ${resource.transcript_language}` : ""}
                  </p>
                </div>
                <div className="resource-actions">
                  {resource.has_transcript && (
                    <button
                      className="text-button"
                      type="button"
                      onClick={() => void loadTranscript(resource.id)}
                    >
                      {transcripts[resource.id] ? "🔄 تحديث التفريغ" : "📝 عرض التفريغ النصي"}
                    </button>
                  )}
                  {downloadLinks[resource.id] ? (
                    <a className="session-start" href={downloadLinks[resource.id]} target="_blank" rel="noreferrer">
                      ⬇️ فتح / تنزيل
                    </a>
                  ) : (
                    <button className="text-button" onClick={() => void prepareDownload(resource.id)}>
                      🔗 رابط التحميل
                    </button>
                  )}
                </div>
                {transcripts[resource.id] && (
                  <section className="transcript-card" aria-label={`تفريغ ${resource.file_name}`}>
                    <p style={{ fontWeight: "bold", marginBottom: 6 }}>
                      🎙️ تفريغ المحاضرة ({transcripts[resource.id].language} · مدة التسجيل:{" "}
                      {Math.floor(transcripts[resource.id].audio_duration_seconds / 60)} دقيقة):
                    </p>
                    <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.7, fontSize: 14 }}>
                      {transcripts[resource.id].transcript}
                    </p>
                  </section>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      {/* YouTube Links Section */}
      <section className="assistant-panel" aria-labelledby="youtube-heading">
        <p className="eyebrow">🎥 روابط وفيديوهات الشرح</p>
        <h2 id="youtube-heading" style={{ fontSize: 20 }}>محاضرات وشروحات YouTube</h2>
        <p style={{ color: "var(--muted)", fontSize: 14 }}>
          أضف روابط فيديوهات الشرح المرتبطة بهذه المادة لتستعرضها وتراجعها في مساحة دراستك.
        </p>
        <form className="assistant-form" onSubmit={addVideo}>
          <label htmlFor="youtube-url">رابط فيديو YouTube</label>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <input
              id="youtube-url"
              type="url"
              inputMode="url"
              autoComplete="url"
              maxLength={2048}
              value={videoUrl}
              onChange={(event) => setVideoUrl(event.target.value)}
              placeholder="https://www.youtube.com/watch?v=... أو https://youtu.be/..."
              required
              style={{ flex: 1, minWidth: 260 }}
            />
            <button className="session-start" type="submit" disabled={videoBusy || !videoUrl.trim()}>
              {videoBusy ? "⏳ جاري الإضافة…" : "➕ إضافة الفيديو"}
            </button>
          </div>
        </form>

        {youtubeLinks.length === 0 ? (
          <p className="state-card" style={{ marginTop: 14 }}>لا توجد روابط فيديو لهذه المادة بعد.</p>
        ) : (
          <div className="resource-list" style={{ marginTop: 16 }}>
            {youtubeLinks.map((link) => (
              <article className="resource-item" key={link.id} style={{ display: "block" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <h3 style={{ fontSize: 16, margin: 0 }}>🎬 {link.title || "فيديو YouTube للمادة"}</h3>
                  <div style={{ display: "flex", gap: 10 }}>
                    <a href={link.url} target="_blank" rel="noreferrer" className="text-button">
                      ↗️ فتح في YouTube
                    </a>
                    <button
                      className="text-button"
                      style={{ color: "#d9534f" }}
                      type="button"
                      onClick={() => void removeVideo(link.id)}
                    >
                      🗑️ حذف
                    </button>
                  </div>
                </div>
                <div style={{ position: "relative", paddingBottom: "56.25%", height: 0, overflow: "hidden", borderRadius: 8 }}>
                  <iframe
                    style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", border: 0 }}
                    src={`https://www.youtube-nocookie.com/embed/${link.video_id}`}
                    title={link.title || "فيديو YouTube للمادة"}
                    loading="lazy"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                    allowFullScreen
                  />
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
