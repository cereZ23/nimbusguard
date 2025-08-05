import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";
import { SWRProvider } from "@/lib/swr";
import ErrorBoundary from "@/components/ui/error-boundary";
import GlobalErrorHandlers from "@/components/global-error-handlers";

const dmSans = DM_Sans({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  title: "CSPM - Cloud Security Posture Management",
  description:
    "Monitor and manage the security posture of your cloud infrastructure",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={dmSans.variable} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('theme');if(t==='dark'||(!t&&matchMedia('(prefers-color-scheme:dark)').matches)){document.documentElement.classList.add('dark')}}catch(e){}})()`,
          }}
        />
      </head>
      <body
        className={`${dmSans.className} bg-white text-gray-900 dark:bg-gray-900 dark:text-gray-100`}
      >
        <ThemeProvider>
          <GlobalErrorHandlers />
          <ErrorBoundary>
            <SWRProvider>
              <AuthProvider>{children}</AuthProvider>
            </SWRProvider>
          </ErrorBoundary>
        </ThemeProvider>
      </body>
    </html>
  );
}
