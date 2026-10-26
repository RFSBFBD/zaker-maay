import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { GlobalPageLoader } from "@/components/page-loading";

export const metadata: Metadata = {
  title: "ذاكر معي — منصة المذاكرة الذكية والتعلم المركز",
  description: "ارفع كتبك ومحاضراتك الصوتية، ودع رفيقك الذكي يشرحها لك برسوم توضيحية وجلسات تركيز وتقييم أكاديمي دقيق.",
  icons: {
    icon: "/icon.svg",
    shortcut: "/icon.svg",
    apple: "/icon.svg",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ar" dir="rtl" data-theme="light" suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <GlobalPageLoader />
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
