"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { apiRequest } from "@/lib/api";
import { useTheme } from "@/components/theme-provider";
import { NotificationsDropdown } from "@/components/notifications-dropdown";
import { StudySessionModal } from "@/components/study-session-modal";
import {
  GraduationCapIcon,
  BookOpenIcon,
  ChartBarIcon,
  ShieldIcon,
  SunIcon,
  MoonIcon,
  LogoutIcon,
} from "@/components/icons";

type CurrentProfile = {
  id: string;
  email: string | null;
  role: "student" | "admin";
};

export function AppHeader({ currentSubjectId }: { currentSubjectId?: string }) {
  const [profile, setProfile] = useState<CurrentProfile | null>(() => {
    if (typeof window !== "undefined") {
      try {
        const cached = localStorage.getItem("zaker_profile");
        if (cached) return JSON.parse(cached);
      } catch {}
    }
    return null;
  });
  const [loadingAuth, setLoadingAuth] = useState(() => {
    if (typeof window !== "undefined") {
      try {
        if (localStorage.getItem("zaker_profile")) return false;
      } catch {}
    }
    return true;
  });
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();

  useEffect(() => {
    let active = true;
    async function loadMe() {
      try {
        const {
          data: { session },
        } = await createClient().auth.getSession();
        if (session) {
          const me = await apiRequest<CurrentProfile>("/api/v1/auth/me", {
            headers: { Authorization: `Bearer ${session.access_token}` },
          });
          if (active) {
            setProfile(me);
            try {
              localStorage.setItem("zaker_profile", JSON.stringify(me));
            } catch {}
          }
        } else {
          if (active) {
            setProfile(null);
            try {
              localStorage.removeItem("zaker_profile");
            } catch {}
          }
        }
      } catch {
        if (active) setProfile(null);
      } finally {
        if (active) setLoadingAuth(false);
      }
    }
    void loadMe();
    return () => {
      active = false;
    };
  }, []);

  async function handleSignOut() {
    try {
      localStorage.removeItem("zaker_profile");
      await createClient().auth.signOut();
      window.location.replace("/login");
    } catch {
      localStorage.removeItem("zaker_profile");
      window.location.replace("/login");
    }
  }

  const isAdmin = profile?.role === "admin";
  const isStudent = profile?.role === "student";

  return (
    <header
      className="topbar"
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "0 24px",
        borderBottom: "1px solid var(--line)",
        background: "var(--surface)",
        height: 72,
        position: "sticky",
        top: 0,
        zIndex: 900,
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
      }}
    >
      {/* Brand & Nav */}
      <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
        <Link href="/" className="brand" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            className="brand-mark"
            style={{
              width: 38,
              height: 38,
              borderRadius: 12,
              background: "linear-gradient(135deg, var(--green), var(--green-hover))",
              color: "#fff",
              display: "grid",
              placeItems: "center",
              boxShadow: "0 4px 12px rgba(45, 106, 79, 0.25)",
            }}
          >
            <GraduationCapIcon size={22} />
          </span>
          <span style={{ fontSize: 20, fontWeight: 800, letterSpacing: -0.5, color: "var(--ink)" }}>
            ذاكر معي
          </span>
          {isAdmin && (
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                padding: "2px 8px",
                borderRadius: 12,
                background: "rgba(224, 122, 95, 0.15)",
                color: "var(--orange)",
                border: "1px solid rgba(224, 122, 95, 0.3)",
              }}
            >
              مسؤول المنصة
            </span>
          )}
        </Link>

        {/* Main Navigation: STRICTLY ROLE-BASED */}
        {!loadingAuth && (
          <nav
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
            className="main-nav"
          >
            {/* Common Home link for everyone */}
            <Link
              href="/"
              className={`nav-link ${pathname === "/" ? "active" : ""}`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "8px 14px",
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 600,
                color: pathname === "/" ? "var(--green)" : "var(--muted)",
                background: pathname === "/" ? "rgba(45, 106, 79, 0.08)" : "transparent",
              }}
            >
              <span>الرئيسية</span>
            </Link>

            {/* STUDENT-ONLY NAVIGATION */}
            {isStudent && (
              <>
                <Link
                  href="/subjects"
                  className={`nav-link ${pathname.startsWith("/subjects") ? "active" : ""}`}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "8px 14px",
                    borderRadius: 8,
                    fontSize: 14,
                    fontWeight: 600,
                    color: pathname.startsWith("/subjects") ? "var(--green)" : "var(--muted)",
                    background: pathname.startsWith("/subjects") ? "rgba(45, 106, 79, 0.08)" : "transparent",
                  }}
                >
                  <BookOpenIcon size={16} />
                  <span>المواد الدراسية</span>
                </Link>

                <Link
                  href="/dashboard"
                  className={`nav-link ${pathname === "/dashboard" ? "active" : ""}`}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "8px 14px",
                    borderRadius: 8,
                    fontSize: 14,
                    fontWeight: 600,
                    color: pathname === "/dashboard" ? "var(--green)" : "var(--muted)",
                    background: pathname === "/dashboard" ? "rgba(45, 106, 79, 0.08)" : "transparent",
                  }}
                >
                  <ChartBarIcon size={16} />
                  <span>تقدمي ومستواي</span>
                </Link>
              </>
            )}

            {/* ADMIN-ONLY NAVIGATION */}
            {isAdmin && (
              <Link
                href="/admin"
                className={`nav-link ${pathname === "/admin" ? "active" : ""}`}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "8px 14px",
                  borderRadius: 8,
                  fontSize: 14,
                  fontWeight: 700,
                  color: "var(--orange)",
                  background: pathname === "/admin" ? "rgba(224, 122, 95, 0.12)" : "transparent",
                  border: "1px solid rgba(224, 122, 95, 0.25)",
                }}
              >
                <ShieldIcon size={16} />
                <span>🛡️ لوحة الإدارة</span>
              </Link>
            )}
          </nav>
        )}
      </div>

      {/* Action Controls */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {/* Student-only quick actions */}
        {isStudent && (
          <>
            <StudySessionModal currentSubjectId={currentSubjectId} />
            <NotificationsDropdown />
          </>
        )}

        {/* Theme Switcher Toggle (Light / Dark) */}
        <button
          type="button"
          onClick={toggleTheme}
          title={theme === "light" ? "تفعيل الوضع الليلي" : "تفعيل الوضع النهاري"}
          aria-label="تبديل المظهر"
          style={{
            background: "transparent",
            border: "1px solid var(--line)",
            borderRadius: 10,
            width: 38,
            height: 38,
            display: "grid",
            placeItems: "center",
            cursor: "pointer",
            color: "var(--ink)",
            transition: "border-color 0.2s, background 0.2s",
          }}
        >
          {theme === "light" ? <MoonIcon size={18} /> : <SunIcon size={18} />}
        </button>

        {/* Auth Action */}
        {!loadingAuth && (
          profile ? (
            <button
              type="button"
              onClick={() => void handleSignOut()}
              className="text-button"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontSize: 13,
                fontWeight: 600,
                color: "var(--muted)",
                padding: "7px 12px",
                borderRadius: 8,
                border: "1px solid var(--line)",
                background: "transparent",
                cursor: "pointer",
              }}
              title="تسجيل الخروج"
            >
              <LogoutIcon size={15} />
              <span>خروج</span>
            </button>
          ) : (
            <Link
              href="/login"
              className="session-start"
              style={{ margin: 0, padding: "8px 18px", fontSize: 13.5, borderRadius: 10 }}
            >
              تسجيل الدخول
            </Link>
          )
        )}
      </div>
    </header>
  );
}
