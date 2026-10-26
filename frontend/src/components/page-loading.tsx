"use client";

import React, { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

export function GlobalPageLoader() {
  const pathname = usePathname();
  const [loading, setLoading] = useState(false);
  const [messageIndex, setMessageIndex] = useState(0);

  const encouragingMessages = [
    "جارٍ تجهيز مساحة المذاكرة الذكية…",
    "استعد لجلسة تركيز عميقة ومثمرة…",
    "رفيقك الذكي يستحضر مراجعك ومفاهيمك…",
    "لحظات ونبدأ خطوة جديدة نحو التفوق…",
  ];

  useEffect(() => {
    // Show brief transition on route change
    setLoading(true);
    const nextIndex = Math.floor(Math.random() * encouragingMessages.length);
    setMessageIndex(nextIndex);

    const timer = setTimeout(() => {
      setLoading(false);
    }, 450);

    return () => clearTimeout(timer);
  }, [pathname]);

  if (!loading) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 99999,
        background: "rgba(var(--paper-rgb, 248, 250, 248), 0.88)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        direction: "rtl",
        animation: "fadeIn 0.2s ease-out",
        transition: "opacity 0.25s ease",
      }}
      aria-live="assertive"
      aria-label="جاري تحميل الصفحة"
    >
      {/* Top running gradient bar */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 3,
          background: "linear-gradient(90deg, var(--green), #52b788, var(--orange), var(--green))",
          backgroundSize: "200% 100%",
          animation: "moveGradient 1.2s linear infinite",
        }}
      />

      <div
        style={{
          background: "var(--surface, #fff)",
          border: "1px solid var(--line, #e2e8e3)",
          borderRadius: 24,
          padding: "36px 44px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 16,
          boxShadow: "0 24px 64px rgba(0, 0, 0, 0.1)",
          maxWidth: 380,
          width: "90%",
          textAlign: "center",
        }}
      >
        {/* Animated Brand Logo Icon */}
        <div
          style={{
            position: "relative",
            width: 72,
            height: 72,
            display: "grid",
            placeItems: "center",
          }}
        >
          {/* Pulsing ring */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: 22,
              background: "var(--mint, #d8f3dc)",
              opacity: 0.6,
              animation: "pulseRing 1.6s cubic-bezier(0.4, 0, 0.6, 1) infinite",
            }}
          />
          {/* Main emblem */}
          <div
            style={{
              position: "relative",
              width: 58,
              height: 58,
              borderRadius: 18,
              background: "linear-gradient(135deg, var(--green), #1b4332)",
              color: "#fff",
              display: "grid",
              placeItems: "center",
              fontSize: 28,
              boxShadow: "0 8px 20px rgba(45, 106, 79, 0.35)",
            }}
          >
            🎓
          </div>
        </div>

        {/* Brand Name */}
        <div>
          <h2
            style={{
              fontSize: 22,
              fontWeight: 800,
              margin: "0 0 6px",
              color: "var(--ink)",
              letterSpacing: -0.5,
            }}
          >
            ذاكر معي
          </h2>
          <p
            style={{
              margin: 0,
              fontSize: 13.5,
              color: "var(--muted)",
              lineHeight: 1.6,
            }}
          >
            {encouragingMessages[messageIndex]}
          </p>
        </div>

        {/* Modern Indeterminate Spinner / Loader */}
        <div
          style={{
            width: 140,
            height: 4,
            background: "var(--line, #e2e8e3)",
            borderRadius: 8,
            overflow: "hidden",
            position: "relative",
            marginTop: 8,
          }}
        >
          <div
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              width: "45%",
              background: "var(--green)",
              borderRadius: 8,
              animation: "indeterminateBar 1.2s ease-in-out infinite",
            }}
          />
        </div>
      </div>
    </div>
  );
}

// Standalone loading screen component for Next.js loading.tsx
export function FullScreenPageLoader({
  title = "ذاكر معي",
  subtitle = "جارٍ تحميل المحتوى الأكاديمي…",
}: {
  title?: string;
  subtitle?: string;
}) {
  return (
    <div
      style={{
        minHeight: "70vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        direction: "rtl",
        padding: 24,
      }}
    >
      <div
        style={{
          background: "var(--surface, #fff)",
          border: "1px solid var(--line, #e2e8e3)",
          borderRadius: 24,
          padding: "36px 44px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 16,
          boxShadow: "0 20px 48px rgba(0, 0, 0, 0.06)",
          maxWidth: 380,
          width: "100%",
          textAlign: "center",
        }}
      >
        <div
          style={{
            width: 60,
            height: 60,
            borderRadius: 18,
            background: "linear-gradient(135deg, var(--green), #1b4332)",
            color: "#fff",
            display: "grid",
            placeItems: "center",
            fontSize: 28,
            boxShadow: "0 8px 20px rgba(45, 106, 79, 0.35)",
            animation: "pulseIcon 1.5s ease-in-out infinite",
          }}
        >
          🎓
        </div>
        <div>
          <h3 style={{ margin: "0 0 6px", fontSize: 20, fontWeight: 800, color: "var(--ink)" }}>{title}</h3>
          <p style={{ margin: 0, fontSize: 13.5, color: "var(--muted)" }}>{subtitle}</p>
        </div>
        <div
          style={{
            width: 120,
            height: 4,
            background: "var(--line, #e2e8e3)",
            borderRadius: 8,
            overflow: "hidden",
            position: "relative",
          }}
        >
          <div
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              width: "45%",
              background: "var(--green)",
              borderRadius: 8,
              animation: "indeterminateBar 1.2s ease-in-out infinite",
            }}
          />
        </div>
      </div>
    </div>
  );
}
