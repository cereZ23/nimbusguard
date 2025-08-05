"use client";

import { useCallback, useState } from "react";
import type { ReactNode } from "react";
import dynamic from "next/dynamic";
import Sidebar from "@/components/layout/sidebar";
import Topbar from "@/components/layout/topbar";
import SessionWarning from "@/components/ui/session-warning";
import { BrandingProvider } from "@/lib/branding";
import { HelpProvider } from "@/lib/help";

// Lazy load CommandPalette -- it is a modal triggered by Cmd+K, not needed on initial render
const CommandPalette = dynamic(
  () => import("@/components/ui/command-palette"),
  { ssr: false },
);

interface AppShellProps {
  children: ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleMenuToggle = useCallback(() => {
    setMobileMenuOpen((prev) => !prev);
  }, []);

  const handleMobileClose = useCallback(() => {
    setMobileMenuOpen(false);
  }, []);

  return (
    <BrandingProvider>
      <HelpProvider>
        <div className="flex h-screen overflow-hidden">
          <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[100] focus:rounded-lg focus:bg-blue-600 focus:px-4 focus:py-2 focus:text-white focus:shadow-lg focus:outline-none"
          >
            Skip to main content
          </a>
          <Sidebar
            mobileOpen={mobileMenuOpen}
            onMobileClose={handleMobileClose}
          />
          <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
            <SessionWarning />
            <Topbar onMenuToggle={handleMenuToggle} />
            <main
              id="main-content"
              tabIndex={-1}
              className="min-w-0 flex-1 overflow-x-hidden overflow-y-auto bg-gray-50 p-6 dark:bg-gray-900 focus:outline-none"
            >
              <div className="mx-auto w-full max-w-[1600px]">{children}</div>
            </main>
          </div>
          <CommandPalette />
        </div>
      </HelpProvider>
    </BrandingProvider>
  );
}
