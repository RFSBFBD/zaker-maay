"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
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
  academic_chapter?: number | null;
  chapter_title?: string | null;
  ingestion_status?: string;
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
  channel_name?: string | null;
  duration_seconds?: number | null;
  processing_status: string;
  transcript_available: boolean;
  visual_analysis_status?: string;
  visual_summary?: string | null;
  created_at: string;
};

type VideoSegmentItem = {
  chunk_index: number;
  title: string | null;
  start_seconds: number | null;
  end_seconds: number | null;
  formatted_time: string;
  clickable_url: string;
  content: string;
  visual_description: string | null;
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

type QueuedFile = {
  id: string;
  file: File;
  previewUrl: string | null;
  isImage: boolean;
  isAudio: boolean;
  status: "idle" | "uploading" | "ready" | "failed";
  error: string | null;
  resourceId?: string;
  chapterNumber?: number | null;
  chapterTitle?: string | null;
};

type BatchUploadResponse = {
  batch_id: string;
  subject_id: string;
  title: string;
  status: string;
  total_files: number;
  success_count: number;
  failed_count: number;
  resources: Array<{
    resource_id?: string;
    file_name: string;
    status: string;
    chapter_number?: number | null;
    chapter_title?: string | null;
    concepts_count?: number | null;
    error?: string | null;
  }>;
  image_synthesis?: {
    images_count: number;
    ordered_filenames: string[];
    markdown_storage_key: string;
  } | null;
};

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} كيلوبايت`
    : `${(bytes / (1024 * 1024)).toFixed(1)} ميغابايت`;
}

function processingLabel(status: Resource["processing_status"]): string {
  return {
    pending: "قيد المعالجة",
    ready: "النص جاهز",
    no_text: "لم يُستخرج نص",
    unsupported: "لا يدعم استخراج النص",
    truncated: "عولج جزء من النص",
    failed: "فشل المعالجة",
  }[status];
}

const SUPPORTED_ACCEPT =
  ".pdf,.txt,.docx,.pptx,.ppt,.mp3,.wav,.m4a,.webm,.ogg,.aac,.flac,.mp4,.png,.jpg,.jpeg,.webp";

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
  const [transcribingId, setTranscribingId] = useState<string | null>(null);

  // Multi-file & Multi-image state
  const [queuedFiles, setQueuedFiles] = useState<QueuedFile[]>([]);
  const [batchTitle, setBatchTitle] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [batchProgress, setBatchProgress] = useState<{
    total: number;
    success: number;
    failed: number;
    status: string;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Video learning state
  const [videoSegments, setVideoSegments] = useState<Record<string, VideoSegmentItem[]>>({});
  const [loadingSegmentsId, setLoadingSegmentsId] = useState<string | null>(null);
  const [retryingVideoId, setRetryingVideoId] = useState<string | null>(null);

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

  // Handle adding files to queue (via file picker or drag & drop)
  const handleFilesAdded = useCallback((incoming: FileList | File[]) => {
    setError(null);
    const newItems: QueuedFile[] = [];
    let hasAudio = false;

    Array.from(incoming).forEach((file) => {
      const isImg =
        file.type.startsWith("image/") || /\.(png|jpe?g|webp)$/i.test(file.name);
      const isAud =
        file.type.startsWith("audio/") ||
        /\.(mp3|wav|m4a|ogg|webm|aac|flac|mp4)$/i.test(file.name);

      if (isAud) hasAudio = true;

      const previewUrl = isImg ? URL.createObjectURL(file) : null;
      newItems.push({
        id: `${file.name}-${file.size}-${Math.random().toString(36).substring(2, 9)}`,
        file,
        previewUrl,
        isImage: isImg,
        isAudio: isAud,
        status: "idle",
        error: null,
      });
    });

    if (hasAudio) {
      setTranscribeAudio(true);
    }

    setQueuedFiles((current) => [...current, ...newItems]);
  }, []);

  // Remove individual file from selection
  const removeQueuedFile = useCallback((id: string) => {
    setQueuedFiles((current) => {
      const target = current.find((item) => item.id === id);
      if (target?.previewUrl) {
        URL.revokeObjectURL(target.previewUrl);
      }
      return current.filter((item) => item.id !== id);
    });
  }, []);

  // Clear all queued files
  const clearQueue = useCallback(() => {
    queuedFiles.forEach((item) => {
      if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    });
    setQueuedFiles([]);
    setBatchProgress(null);
  }, [queuedFiles]);

  // Execute batch upload
  const uploadBatch = async (event: FormEvent) => {
    event.preventDefault();
    if (queuedFiles.length === 0) return;

    setUploading(true);
    setError(null);
    setNotice(null);

    // Mark queued items as uploading
    setQueuedFiles((curr) =>
      curr.map((f) => (f.status === "idle" ? { ...f, status: "uploading" } : f))
    );

    try {
      const headers = await getHeaders();
      const formData = new FormData();
      if (batchTitle.trim()) {
        formData.append("batch_title", batchTitle.trim());
      }
      formData.append("transcribe_audio", String(transcribeAudio));

      queuedFiles.forEach((item) => {
        formData.append("files", item.file);
      });

      setNotice(`جارٍ رفع ومعالجة ${queuedFiles.length} ملفات بواسطة الذكاء الاصطناعي…`);

      const resp = await apiRequest<BatchUploadResponse>(
        `/api/v1/subjects/${subjectId}/resources/upload-batch`,
        {
          method: "POST",
          headers: { Authorization: headers.Authorization },
          body: formData,
        },
        300_000
      );

      setBatchProgress({
        total: resp.total_files,
        success: resp.success_count,
        failed: resp.failed_count,
        status: resp.status,
      });

      // Update per-item statuses
      setQueuedFiles((curr) =>
        curr.map((item) => {
          const matched = resp.resources.find((r) => r.file_name === item.file.name);
          if (matched) {
            return {
              ...item,
              status: matched.status === "failed" ? "failed" : "ready",
              error: matched.error || null,
              resourceId: matched.resource_id,
              chapterNumber: matched.chapter_number,
              chapterTitle: matched.chapter_title,
            };
          }
          return item;
        })
      );

      await loadResources();

      if (resp.failed_count === 0) {
        setNotice(
          `تم بنجاح رفع وفهرسة ${resp.success_count} ملفات تعليمية في مكتبة المادة!`
        );
      } else {
        setNotice(
          `اكتملت معالجة ${resp.success_count} ملفات بنجاح، بينما تعذرت معالجة ${resp.failed_count} ملفات. يمكنك إعادة المحاولة لكل ملف بشكل مستقل.`
        );
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر رفع الدفعة.");
      setQueuedFiles((curr) =>
        curr.map((f) => (f.status === "uploading" ? { ...f, status: "failed", error: "فشل الرفع" } : f))
      );
    } finally {
      setUploading(false);
    }
  };

  // Retry an individual failed file without re-uploading the whole batch
  const retryResource = async (resourceId: string, queuedId: string) => {
    setError(null);
    setQueuedFiles((curr) =>
      curr.map((item) => (item.id === queuedId ? { ...item, status: "uploading", error: null } : item))
    );

    try {
      const headers = await getHeaders();
      await apiRequest(
        `/api/v1/subjects/${subjectId}/resources/${resourceId}/retry`,
        {
          method: "POST",
          headers,
        }
      );

      setQueuedFiles((curr) =>
        curr.map((item) => (item.id === queuedId ? { ...item, status: "ready", error: null } : item))
      );
      await loadResources();
      setNotice("تمت إعادة معالجة الملف بنجاح!");
    } catch (cause) {
      setQueuedFiles((curr) =>
        curr.map((item) =>
          item.id === queuedId
            ? { ...item, status: "failed", error: cause instanceof Error ? cause.message : "فشلت المحاولة" }
            : item
        )
      );
    }
  };

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

  async function triggerTranscribe(resourceId: string) {
    setTranscribingId(resourceId);
    setError(null);
    setNotice(null);
    try {
      const headers = await getHeaders();
      const updated = await apiRequest<Resource>(
        `/api/v1/subjects/${subjectId}/resources/${resourceId}/transcribe`,
        { method: "POST", headers }
      );
      setResources((prev) => prev.map((r) => (r.id === resourceId ? updated : r)));
      setNotice("تم تفريغ المحاضرة الصوتية بنجاح وأصبحت مرجعاً معتمداً للوكيل الذكي! 🎙️");
      await loadTranscript(resourceId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر تفريغ الملف الصوتي حالياً.");
    } finally {
      setTranscribingId(null);
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
      setNotice("تمت إضافة رابط الفيديو للمادة بنجاح.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر حفظ رابط الفيديو.");
    } finally {
      setVideoBusy(false);
    }
  }

  async function removeVideo(linkId: string) {
    setError(null);
    setNotice(null);
    try {
      const headers = await getHeaders();
      await apiRequest(`/api/v1/subjects/${subjectId}/youtube-links/${linkId}`, {
        method: "DELETE",
        headers,
      });
      setYoutubeLinks((current) => current.filter((l) => l.id !== linkId));
      setNotice("حُذف رابط الفيديو من مراجع المادة.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر حذف رابط الفيديو.");
    }
  }

  const toggleVideoSegments = async (linkId: string) => {
    if (videoSegments[linkId]) {
      setVideoSegments((prev) => {
        const copy = { ...prev };
        delete copy[linkId];
        return copy;
      });
      return;
    }
    setLoadingSegmentsId(linkId);
    try {
      const headers = await getHeaders();
      const segs = await apiRequest<VideoSegmentItem[]>(
        `/api/v1/subjects/${subjectId}/youtube-links/${linkId}/segments`,
        { headers }
      );
      setVideoSegments((prev) => ({ ...prev, [linkId]: segs }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر تحميل فهارس الفيديو.");
    } finally {
      setLoadingSegmentsId(null);
    }
  };

  const retryVideoProcessing = async (linkId: string) => {
    setRetryingVideoId(linkId);
    setError(null);
    try {
      const headers = await getHeaders();
      const updated = await apiRequest<YouTubeLink>(
        `/api/v1/subjects/${subjectId}/youtube-links/${linkId}/retry`,
        { method: "POST", headers }
      );
      setYoutubeLinks((prev) => prev.map((l) => (l.id === linkId ? updated : l)));
      setNotice("تمت إعادة معالجة وتحليل المحاضرة المرئية بنجاح!");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "تعذر إعادة معالجة الفيديو.");
    } finally {
      setRetryingVideoId(null);
    }
  };

  const totalQueuedBytes = queuedFiles.reduce((sum, item) => sum + item.file.size, 0);

  return (
    <div className="library-wrapper" style={{ maxWidth: 960, margin: "0 auto", paddingBottom: 60 }}>
      <div style={{ marginBottom: 24 }}>
        <p className="eyebrow">📁 مكتبة المادة والمراجع المعتمدة</p>
        <h1 style={{ fontSize: 28, margin: "6px 0 10px" }}>
          مراجع <span>{subject?.name ?? "المادة"}</span>
        </h1>
        <p className="intro" style={{ margin: 0 }}>
          {subject?.description || "ارفع كتبك والمحاضرات والصور الدراسية لتكون مصدراً وحيداً يشرح منه المساعد الذكي."}
        </p>
      </div>

      {error && <p className="state-card form-error" role="alert">{error}</p>}
      {notice && <p className="state-card form-notice" role="status">{notice}</p>}

      {/* Bulk & Multi-Image Upload Panel */}
      <section className="upload-panel" style={{ marginBottom: 32 }}>
        <h3 style={{ fontSize: 18, marginBottom: 8 }}>📤 رفع جماعي للكتب، المستندات، والصور الدراسية</h3>
        <p style={{ fontSize: 14, color: "var(--muted)", margin: "0 0 16px" }}>
          يمكنك تحديد عدة ملفات أو صور معاً، أو سحب وإفلات مذكرات وفصول كاملة. تتم معالجة وفهرسة كل ملف باستقلالية تامة.
        </p>

        {/* Drag & Drop Target Zone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            if (e.dataTransfer.files?.length) {
              handleFilesAdded(e.dataTransfer.files);
            }
          }}
          style={{
            border: `2px dashed ${isDragging ? "var(--green)" : "var(--line)"}`,
            backgroundColor: isDragging ? "var(--surface-raised)" : "var(--surface)",
            borderRadius: 12,
            padding: "28px 20px",
            textAlign: "center",
            cursor: "pointer",
            transition: "all 0.2s ease",
            marginBottom: 16,
          }}
          onClick={() => fileInputRef.current?.click()}
        >
          <span style={{ fontSize: 36, display: "block", marginBottom: 8 }}>
            {isDragging ? "📂" : "📥"}
          </span>
          <strong style={{ fontSize: 16, display: "block", marginBottom: 4 }}>
            اسحب وأفلت الملفات والصور هنا، أو انقر للاختيار
          </strong>
          <span style={{ fontSize: 13, color: "var(--muted)" }}>
            يدعم ملفات PDF، Word (DOCX)، الشرائح (PPTX)، التسجيلات الصوتية، والصور (PNG، JPG، WEBP)
          </span>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={SUPPORTED_ACCEPT}
            style={{ display: "none" }}
            disabled={uploading}
            onChange={(e) => {
              if (e.target.files?.length) {
                handleFilesAdded(e.target.files);
                e.target.value = "";
              }
            }}
          />
        </div>

        {/* Selected Files Queue Preview */}
        {queuedFiles.length > 0 && (
          <div
            style={{
              backgroundColor: "var(--surface-raised)",
              borderRadius: 12,
              padding: 16,
              marginBottom: 16,
              border: "1px solid var(--line)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 12,
              }}
            >
              <span style={{ fontWeight: 600, fontSize: 15 }}>
                الملفات المحددة ({queuedFiles.length}) · الحجم الإجمالي: {formatSize(totalQueuedBytes)}
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                >
                  ➕ إضافة المزيد
                </button>
                <button
                  type="button"
                  className="text-button"
                  style={{ color: "#d9534f" }}
                  onClick={clearQueue}
                  disabled={uploading}
                >
                  🗑️ مسح الكل
                </button>
              </div>
            </div>

            {/* Optional Batch Title */}
            <div style={{ marginBottom: 14 }}>
              <input
                type="text"
                placeholder="عنوان الدفعة أو اسم الفصل (اختياري، مثلاً: الفصل الأول - المذكرات والصور الملحقة)"
                value={batchTitle}
                onChange={(e) => setBatchTitle(e.target.value)}
                disabled={uploading}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: 8,
                  border: "1px solid var(--line)",
                  background: "var(--surface)",
                  color: "inherit",
                  fontSize: 14,
                }}
              />
            </div>

            {/* List of individual queued files */}
            <div style={{ display: "grid", gap: 8, maxHeight: 320, overflowY: "auto", paddingRight: 4 }}>
              {queuedFiles.map((item) => (
                <div
                  key={item.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 12px",
                    borderRadius: 8,
                    background: "var(--surface)",
                    border: "1px solid var(--line)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0, flex: 1 }}>
                    {item.isImage && item.previewUrl ? (
                      /* eslint-disable-next-line @next/next/no-img-element */
                      <img
                        src={item.previewUrl}
                        alt={item.file.name}
                        style={{
                          width: 40,
                          height: 40,
                          objectFit: "cover",
                          borderRadius: 6,
                          border: "1px solid var(--line)",
                        }}
                      />
                    ) : (
                      <span style={{ fontSize: 24 }}>
                        {item.isAudio ? "🎙️" : item.file.name.endsWith(".pdf") ? "📄" : "📝"}
                      </span>
                    )}
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <p
                        style={{
                          margin: 0,
                          fontSize: 14,
                          fontWeight: 500,
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                        title={item.file.name}
                      >
                        {item.file.name}
                      </p>
                      <span style={{ fontSize: 12, color: "var(--muted)" }}>
                        {formatSize(item.file.size)}
                        {item.chapterTitle ? ` · ${item.chapterTitle}` : ""}
                        {item.error ? ` · ⚠️ ${item.error}` : ""}
                      </span>
                    </div>
                  </div>

                  {/* Status & Actions */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    {item.status === "idle" && (
                      <span style={{ fontSize: 12, color: "var(--muted)" }}>جاهز</span>
                    )}
                    {item.status === "uploading" && (
                      <span style={{ fontSize: 12, color: "var(--mint)" }}>⏳ جارٍ المعالجة…</span>
                    )}
                    {item.status === "ready" && (
                      <span style={{ fontSize: 12, color: "var(--green)", fontWeight: 600 }}>✅ تم الاستيعاب</span>
                    )}
                    {item.status === "failed" && (
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ fontSize: 12, color: "#d9534f" }}>❌ تعذر</span>
                        {item.resourceId && (
                          <button
                            type="button"
                            className="text-button"
                            style={{ fontSize: 12, padding: "2px 6px" }}
                            onClick={() => retryResource(item.resourceId!, item.id)}
                          >
                            🔄 إعادة
                          </button>
                        )}
                      </div>
                    )}
                    {item.status === "idle" && !uploading && (
                      <button
                        type="button"
                        onClick={() => removeQueuedFile(item.id)}
                        style={{
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          color: "var(--muted)",
                          fontSize: 16,
                          padding: 4,
                        }}
                        title="إزالة من القائمة"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Audio transcription option if any audio queued */}
            {queuedFiles.some((f) => f.isAudio) && (
              <label className="consent-choice" style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 8 }}>
                <input
                  type="checkbox"
                  checked={transcribeAudio}
                  onChange={(event) => setTranscribeAudio(event.target.checked)}
                  disabled={uploading}
                />
                🎙️ تفعيل التفريغ النصي الصوتي الذكي للتسجيلات الصوتية في هذه الدفعة.
              </label>
            )}

            {/* Upload Button */}
            <div style={{ marginTop: 16, display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                className="session-start"
                disabled={uploading || queuedFiles.length === 0}
                onClick={uploadBatch}
                style={{ padding: "10px 24px", fontSize: 15 }}
              >
                {uploading
                  ? `⏳ جارٍ رفع ومعالجة (${queuedFiles.length}) ملفات…`
                  : `⬆️ بدء الرفع والمعالجة الذكية (${queuedFiles.length} ملفات)`}
              </button>
            </div>
          </div>
        )}

        {/* Batch Summary Report if completed */}
        {batchProgress && (
          <div
            style={{
              padding: 12,
              borderRadius: 8,
              backgroundColor: batchProgress.failed === 0 ? "rgba(16, 185, 129, 0.1)" : "rgba(245, 158, 11, 0.1)",
              border: `1px solid ${batchProgress.failed === 0 ? "var(--green)" : "var(--line)"}`,
              fontSize: 14,
              marginBottom: 12,
            }}
          >
            <strong>تقرير المعالجة الأكاديمية:</strong> اكتملت معالجة {batchProgress.success} من أصل {batchProgress.total} ملفات بنجاح.
            {batchProgress.failed > 0 && ` (تعذرت معالجة ${batchProgress.failed}، يمكنك النقر على زر "إعادة" أعلاه).`}
          </div>
        )}
      </section>

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
              ارفع مذكرتك، كتابك، أو صور السبورة والمحاضرات من النموذج أعلاه لكي يبدأ المساعد بشرحها.
            </p>
          </div>
        )}

        {resources.length > 0 && (
          <div className="resource-list" aria-label="ملفات المادة">
            {resources.map((resource) => (
              <article className="resource-item" key={resource.id}>
                <div>
                  <h3 style={{ fontSize: 17, margin: "0 0 6px" }}>
                    {resource.mime_type.startsWith("image/") ? "🖼️ " : resource.mime_type.startsWith("audio/") ? "🎙️ " : "📄 "}
                    {resource.file_name}
                  </h3>
                  <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>
                    {formatSize(resource.size_bytes)} · {new Date(resource.created_at).toLocaleDateString("ar-EG")} ·{" "}
                    <span style={{ fontWeight: 600 }}>
                      {resource.mime_type.startsWith("audio/") && !resource.has_transcript
                        ? "🎙️ تسجيل صوتي (غير مفرغ بعد)"
                        : processingLabel(resource.processing_status)}
                    </span>
                    {resource.chapter_title ? ` · 🏷️ ${resource.chapter_title}` : ""}
                    {resource.transcript_language ? ` · لغة التفريغ: ${resource.transcript_language}` : ""}
                  </p>
                </div>
                <div className="resource-actions">
                  {resource.mime_type.startsWith("audio/") && !resource.has_transcript && (
                    <button
                      className="text-button"
                      type="button"
                      disabled={transcribingId === resource.id}
                      onClick={() => void triggerTranscribe(resource.id)}
                      style={{ color: "var(--green)", fontWeight: 700 }}
                    >
                      {transcribingId === resource.id ? "⏳ جارٍ التفريغ النصي..." : "🎙️ تفريغ المحاضرة ليذاكر منها المساعد"}
                    </button>
                  )}
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
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <h3 style={{ fontSize: 16, margin: 0 }}>🎬 {link.title || "فيديو YouTube للمادة"}</h3>
                    <span
                      style={{
                        fontSize: 11,
                        padding: "2px 8px",
                        borderRadius: 10,
                        background: link.transcript_available ? "var(--mint)" : "var(--surface-raised)",
                        color: link.transcript_available ? "var(--green)" : "var(--muted)",
                        border: `1px solid ${link.transcript_available ? "var(--green)" : "var(--line)"}`,
                      }}
                    >
                      {link.processing_status === "ready"
                        ? "🧠 تم الاستيعاب — الوكيل يذاكر ويجيب منه"
                        : link.processing_status === "no_captions"
                        ? "⚠️ للمشاهدة فقط — لا تتوفر ترجمة ليذاكر منها الوكيل"
                        : link.processing_status === "pending"
                        ? "⏳ جاري قراءة تفريغ الفيديو..."
                        : link.processing_status === "failed"
                        ? "❌ تعذر قراءة نصوص الفيديو"
                        : "🔄"}
                    </span>
                  </div>
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

                {/* Video Learning Details & Actions */}
                <div style={{ marginTop: 12, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>
                    {link.channel_name ? `🎙️ القناة: ${link.channel_name} · ` : ""}
                    {link.duration_seconds ? `⏱️ المدة: ${Math.floor(link.duration_seconds / 60)} دقيقة · ` : ""}
                    {link.visual_analysis_status === "ready" && (
                      <span style={{ color: "var(--mint)", fontWeight: 500 }}>
                        👁️ تم استخلاص المخططات والسلايدات البصرية
                      </span>
                    )}
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => toggleVideoSegments(link.id)}
                      disabled={loadingSegmentsId === link.id}
                      style={{ fontWeight: 600 }}
                    >
                      {loadingSegmentsId === link.id
                        ? "⏳ جارٍ التحميل…"
                        : videoSegments[link.id]
                        ? "▲ إخفاء الفهرس الزمني"
                        : "▼ ⏱️ الفهرس الزمني والمخططات"}
                    </button>
                    {(link.processing_status === "failed" || link.processing_status === "no_captions") && (
                      <button
                        type="button"
                        className="text-button"
                        onClick={() => retryVideoProcessing(link.id)}
                        disabled={retryingVideoId === link.id}
                        style={{ color: "var(--green)", fontWeight: 600 }}
                      >
                        {retryingVideoId === link.id ? "⏳ جارٍ إعادة المحاولة…" : "🔄 إعادة التحليل"}
                      </button>
                    )}
                  </div>
                </div>

                {/* Timestamped Topics & Visual Index Drawer */}
                {videoSegments[link.id] && (
                  <div
                    style={{
                      marginTop: 14,
                      padding: 14,
                      borderRadius: 8,
                      backgroundColor: "var(--surface-raised)",
                      border: "1px solid var(--line)",
                    }}
                  >
                    <h4 style={{ margin: "0 0 10px", fontSize: 14, fontWeight: 600 }}>
                      📑 الفهرس الزمني والمفاهيم البصرية المستوعبة ({videoSegments[link.id].length} مقاطع):
                    </h4>
                    {videoSegments[link.id].length === 0 ? (
                      <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>
                        لا توجد مقاطع مفهرسة مسجلة لهذا الفيديو.
                      </p>
                    ) : (
                      <div style={{ display: "grid", gap: 8, maxHeight: 280, overflowY: "auto" }}>
                        {videoSegments[link.id].map((seg) => (
                          <div
                            key={seg.chunk_index}
                            style={{
                              display: "flex",
                              alignItems: "flex-start",
                              gap: 10,
                              padding: "8px 10px",
                              borderRadius: 6,
                              backgroundColor: "var(--surface)",
                              border: "1px solid var(--line)",
                              fontSize: 13,
                            }}
                          >
                            <a
                              href={seg.clickable_url}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                color: "var(--mint)",
                                fontWeight: 700,
                                textDecoration: "none",
                                whiteSpace: "nowrap",
                                backgroundColor: "rgba(16, 185, 129, 0.1)",
                                padding: "2px 6px",
                                borderRadius: 4,
                              }}
                              title="فتح المحاضرة مباشرة عند هذا التوقيت"
                            >
                              ▶️ {seg.formatted_time}
                            </a>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <strong style={{ display: "block", marginBottom: 2 }}>
                                {seg.title || "مقطع دراسي"}
                              </strong>
                              <span style={{ color: "var(--muted)", fontSize: 12, display: "block" }}>
                                {seg.content.slice(0, 140)}...
                              </span>
                              {seg.visual_description && (
                                <span
                                  style={{
                                    display: "inline-block",
                                    marginTop: 4,
                                    fontSize: 11,
                                    color: "var(--mint)",
                                    backgroundColor: "rgba(52, 211, 153, 0.1)",
                                    padding: "1px 6px",
                                    borderRadius: 4,
                                  }}
                                >
                                  {seg.visual_description}
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
