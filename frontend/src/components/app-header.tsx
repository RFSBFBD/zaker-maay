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
  UserIcon,
} from "@/components/icons";

type CurrentProfile = {
  id: string;
  email: string | null;
  role: "student" | "admin";
};

export function AppHeader({ currentSubjectId }: { currentSubjectId?: string }) {
  const [profile, setProfile] = useState<CurrentProfile | null>(null);
  const [isMounted, setIsMounted] = useState(false);
  const [loadingAuth, setLoadingAuth] = useState(true);
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();

  useEffect(() => {
    setIsMounted(true);

    // Fast-path: immediately read cached profile on client to avoid layout shifts
    try {
      const cached = localStorage.getItem("zaker_profile");
      if (cached) {
        setProfile(JSON.parse(cached));
        setLoadingAuth(false);
      }
    } catch {}

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
    <>
      <header className="topbar">
        <div className="shell-wide" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
          {/* Brand & Desktop Navigation */}
          <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
            <Link href="/" className="brand" aria-label="الصفحة الرئيسية لذاكر معي">
              <span className="brand-mark">
                <GraduationCapIcon size={22} />
              </span>
              <span style={{ fontSize: 19, fontWeight: 800, letterSpacing: -0.5, color: "var(--ink)" }}>
                ذاكر معي
              </span>
              {isMounted && isAdmin && (
                <span className="badge badge-orange" style={{ fontSize: 11, fontWeight: 700 }}>
                  مسؤول المنصة
                </span>
              )}
            </Link>

            {/* Desktop Navigation */}
            <nav className="main-nav" style={{ display: "flex", alignItems: "center", gap: 6 }} aria-label="التنقل الرئيسي">
              <Link
                href="/"
                className={`nav-link ${pathname === "/" ? "active" : ""}`}
              >
                <span>الرئيسية</span>
              </Link>

              {/* STUDENT NAVIGATION */}
              {isMounted && isStudent && (
                <>
                  <Link
                    href="/subjects"
                    className={`nav-link ${pathname.startsWith("/subjects") ? "active" : ""}`}
                  >
                    <BookOpenIcon size={16} />
                    <span>المواد الدراسية</span>
                  </Link>

                  <Link
                    href="/dashboard"
                    className={`nav-link ${pathname === "/dashboard" ? "active" : ""}`}
                  >
                    <ChartBarIcon size={16} />
                    <span>تقدمي ومستواي</span>
                  </Link>
                </>
              )}

              {/* ADMIN NAVIGATION */}
              {isMounted && isAdmin && (
                <Link
                  href="/admin"
                  className={`nav-link ${pathname === "/admin" ? "active" : ""}`}
                  style={{
                    color: pathname === "/admin" ? "var(--orange)" : "var(--muted)",
                    background: pathname === "/admin" ? "var(--orange-light)" : "transparent",
                    borderColor: pathname === "/admin" ? "rgba(217, 119, 54, 0.3)" : "transparent",
                  }}
                >
                  <ShieldIcon size={16} />
                  <span>لوحة الإدارة</span>
                </Link>
              )}
            </nav>
          </div>

          {/* Action Controls & Utilities */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {/* Student Study Session Modal & Notifications */}
            {isMounted && isStudent && (
              <>
                <StudySessionModal currentSubjectId={currentSubjectId} />
                <NotificationsDropdown />
              </>
            )}

            {/* Theme Switcher Toggle */}
            <button
              type="button"
              onClick={toggleTheme}
              title={theme === "light" ? "تفعيل الوضع الليلي" : "تفعيل الوضع النهاري"}
              aria-label={theme === "light" ? "تفعيل الوضع الليلي" : "تفعيل الوضع النهاري"}
              suppressHydrationWarning
              style={{
                background: "var(--surface)",
                border: "1px solid var(--line)",
                borderRadius: 9,
                width: 38,
                height: 38,
                display: "grid",
                placeItems: "center",
                cursor: "pointer",
                color: "var(--ink)",
                transition: "all 0.15s ease",
              }}
            >
              {theme === "light" ? <MoonIcon size={17} /> : <SunIcon size={17} />}
            </button>

            {/* Auth Action */}
            {isMounted ? (
              profile ? (
                <button
                  type="button"
                  onClick={() => void handleSignOut()}
                  className="btn btn-ghost btn-sm"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    border: "1px solid var(--line)",
                    borderRadius: 9,
                    height: 38,
                    padding: "0 12px",
                  }}
                  title="تسجيل الخروج"
                >
                  <LogoutIcon size={15} />
                  <span>خروج</span>
                </button>
              ) : (
                <Link
                  href="/login"
                  className="btn btn-primary btn-sm"
                  style={{ height: 38, padding: "0 16px" }}
                >
                  <UserIcon size={15} />
                  <span>تسجيل الدخول</span>
                </Link>
              )
            ) : (
              <div style={{ width: 88, height: 38 }} />
            )}
          </div>
        </div>
      </header>

      {/* Mobile Bottom Navigation Bar (Visible only on small screens for authenticated users) */}
      {isMounted && profile && (
        <nav
          className="mobile-bottom-nav"
          style={{
            position: "fixed",
            bottom: 0,
            left: 0,
            right: 0,
            zIndex: 90,
            background: "var(--surface)",
            borderTop: "1px solid var(--line)",
            display: "none",
            justifyContent: "space-around",
            alignItems: "center",
            padding: "8px 12px calc(8px + env(safe-area-inset-bottom, 0px))",
            boxShadow: "0 -2px 10px rgba(0,0,0,0.04)",
          }}
          aria-label="التنقل على الهواتف"
        >
          <Link
            href="/"
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 3,
              fontSize: 11,
              fontWeight: 700,
              color: pathname === "/" ? "var(--green)" : "var(--muted)",
              minWidth: 50,
              padding: "4px 0",
            }}
          >
            <GraduationCapIcon size={20} />
            <span>الرئيسية</span>
          </Link>

          {isStudent && (
            <>
              <Link
                href="/subjects"
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 3,
                  fontSize: 11,
                  fontWeight: 700,
                  color: pathname.startsWith("/subjects") ? "var(--green)" : "var(--muted)",
                  minWidth: 50,
                  padding: "4px 0",
                }}
              >
                <BookOpenIcon size={20} />
                <span>المواد</span>
              </Link>

              <Link
                href="/dashboard"
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 3,
                  fontSize: 11,
                  fontWeight: 700,
                  color: pathname === "/dashboard" ? "var(--green)" : "var(--muted)",
                  minWidth: 50,
                  padding: "4px 0",
                }}
              >
                <ChartBarIcon size={20} />
                <span>إنجازاتي</span>
              </Link>
            </>
          )}

          {isAdmin && (
            <Link
              href="/admin"
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 3,
                fontSize: 11,
                fontWeight: 700,
                color: pathname === "/admin" ? "var(--orange)" : "var(--muted)",
                minWidth: 50,
                padding: "4px 0",
              }}
            >
              <ShieldIcon size={20} />
              <span>الإدارة</span>
            </Link>
          )}
        </nav>
      )}

      <style jsx global>{`
        @media (max-width: 768px) {
          .mobile-bottom-nav {
            display: flex !important;
          }
          body {
            padding-bottom: 64px;
          }
        }
      `}</style>
    </>
  );
}
