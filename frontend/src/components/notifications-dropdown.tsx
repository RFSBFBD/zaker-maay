"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiRequest } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { BellIcon } from "@/components/icons";

type InquiryItem = {
  id: string;
  subject_id: string;
  subject_name: string;
  question: string;
  ai_suggested_answer: string | null;
  status: "pending" | "approved" | "rejected";
  admin_answer: string | null;
  admin_notes: string | null;
  is_read: boolean;
  created_at: string;
  answered_at: string | null;
};

type InquiriesResponse = {
  inquiries: InquiryItem[];
  unread_count: number;
};

export function NotificationsDropdown() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<InquiriesResponse>({ inquiries: [], unread_count: 0 });
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  async function fetchInquiries() {
    try {
      const {
        data: { session },
      } = await createClient().auth.getSession();
      if (!session) return;
      const res = await apiRequest<InquiriesResponse>("/api/v1/inquiries/me", {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      setData(res);
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    void fetchInquiries();
    const interval = window.setInterval(() => void fetchInquiries(), 20_000);
    return () => window.clearInterval(interval);
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  async function markAllRead() {
    try {
      setLoading(true);
      const {
        data: { session },
      } = await createClient().auth.getSession();
      if (!session) return;
      await apiRequest("/api/v1/inquiries/mark-all-read", {
        method: "POST",
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      setData((prev) => ({
        ...prev,
        unread_count: 0,
        inquiries: prev.inquiries.map((item) => ({ ...item, is_read: true })),
      }));
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  const answeredInquiries = data.inquiries.filter((inq) => inq.status !== "pending");

  return (
    <div style={{ position: "relative" }} ref={dropdownRef}>
      <button
        type="button"
        className="icon-button"
        onClick={() => setOpen(!open)}
        title="الإشعارات والردود على أسئلتك"
        aria-label="الإشعارات"
        style={{
          position: "relative",
          background: "transparent",
          border: "1px solid var(--line)",
          borderRadius: 10,
          width: 38,
          height: 38,
          display: "grid",
          placeItems: "center",
          cursor: "pointer",
          color: "var(--ink)",
        }}
      >
        <BellIcon size={18} />
        {data.unread_count > 0 && (
          <span
            style={{
              position: "absolute",
              top: -3,
              right: -3,
              background: "#d9534f",
              color: "#fff",
              borderRadius: "50%",
              width: 18,
              height: 18,
              fontSize: 11,
              fontWeight: "bold",
              display: "grid",
              placeItems: "center",
              boxShadow: "0 0 0 2px var(--paper)",
            }}
          >
            {data.unread_count}
          </span>
        )}
      </button>

      {open && (
        <div
          className="notification-popover"
          style={{
            position: "absolute",
            top: 46,
            left: 0,
            width: 340,
            maxWidth: "90vw",
            background: "var(--surface, #fff)",
            border: "1px solid var(--line)",
            borderRadius: 12,
            boxShadow: "0 12px 36px rgba(0,0,0,0.14)",
            zIndex: 1000,
            padding: "16px",
            direction: "rtl",
            textAlign: "right",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 12,
              borderBottom: "1px solid var(--line)",
              paddingBottom: 8,
            }}
          >
            <h4 style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>
              🔔 إشعارات الردود ({data.unread_count} جديدة)
            </h4>
            {data.unread_count > 0 && (
              <button
                type="button"
                onClick={() => void markAllRead()}
                disabled={loading}
                style={{
                  background: "transparent",
                  border: 0,
                  color: "var(--green)",
                  fontSize: 12,
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                تحديد كمقروء
              </button>
            )}
          </div>

          <div style={{ maxHeight: 320, overflowY: "auto", display: "flex", flexDirection: "column", gap: 10 }}>
            {data.inquiries.length === 0 ? (
              <p style={{ margin: "20px 0", textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
                لا توجد إشعارات حتى الآن.
              </p>
            ) : (
              data.inquiries.slice(0, 5).map((inq) => (
                <div
                  key={inq.id}
                  style={{
                    padding: "10px 12px",
                    borderRadius: 8,
                    background: inq.is_read ? "var(--paper)" : "rgba(49, 95, 80, 0.08)",
                    border: inq.is_read ? "1px solid var(--line)" : "1px solid var(--green)",
                    fontSize: 13,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, color: "var(--green)", fontSize: 12 }}>
                      📚 {inq.subject_name}
                    </span>
                    <span style={{ fontSize: 11, color: "var(--muted)" }}>
                      {inq.status === "approved"
                        ? "✅ تم الرد"
                        : inq.status === "rejected"
                        ? "❌ مرفوض"
                        : "⏳ قيد المراجعة"}
                    </span>
                  </div>
                  <p style={{ margin: "2px 0 6px", fontWeight: 500, color: "var(--ink)" }}>
                    {inq.question.slice(0, 75)}...
                  </p>
                  {inq.admin_answer && (
                    <p
                      style={{
                        margin: 0,
                        fontSize: 12,
                        color: "var(--ink)",
                        background: "rgba(0,0,0,0.03)",
                        padding: "6px 8px",
                        borderRadius: 6,
                        borderRight: "3px solid var(--green)",
                      }}
                    >
                      <strong>إجابة الإدارة:</strong> {inq.admin_answer.slice(0, 100)}...
                    </p>
                  )}
                </div>
              ))
            )}
          </div>

          <div
            style={{
              marginTop: 12,
              paddingTop: 8,
              borderTop: "1px solid var(--line)",
              textAlign: "center",
            }}
          >
            <Link
              href="/dashboard"
              onClick={() => setOpen(false)}
              style={{ fontSize: 13, color: "var(--green)", fontWeight: 600, textDecoration: "none" }}
            >
              عرض سجل أسئلتي وتقييمي بالكامل ←
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
