"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  Bell,
  ChevronRight,
  LogOut,
  Menu,
  Moon,
  Search,
  Sun,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";

/** Derive a human-readable page name from a URL pathname segment. */
function segmentToLabel(segment: string): string {
  // Remove dynamic route brackets, e.g. "[id]" -> "Detail"
  if (segment.startsWith("[") && segment.endsWith("]")) {
    return "Detail";
  }
  return segment.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Build breadcrumb entries from the current pathname. */
function useBreadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  const crumbs: { label: string; href: string | null }[] = [
    { label: "Home", href: "/dashboard" },
  ];

  let accumulated = "";
  for (let i = 0; i < segments.length; i++) {
    accumulated += `/${segments[i]}`;
    const isLast = i === segments.length - 1;
    crumbs.push({
      label: segmentToLabel(segments[i]),
      href: isLast ? null : accumulated,
    });
  }

  return crumbs;
}

/** Extract user initials (first letter of full_name, fallback to email). */
function getUserInitial(
  fullName: string | undefined,
  email: string | undefined,
): string {
  if (fullName && fullName.length > 0) {
    return fullName.charAt(0).toUpperCase();
  }
  if (email && email.length > 0) {
    return email.charAt(0).toUpperCase();
  }
  return "U";
}

interface TopbarProps {
  onMenuToggle?: () => void;
}

export default function Topbar({ onMenuToggle }: TopbarProps) {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const breadcrumbs = useBreadcrumbs();

  const displayName = user?.full_name ?? user?.email ?? "User";
  const roleBadge = user?.role === "admin" ? "Admin" : "Viewer";

  return (
    <header className="flex h-16 items-center justify-between border-b border-gray-200/80 bg-white/80 px-4 backdrop-blur-sm dark:border-gray-700/80 dark:bg-gray-800/80 md:px-6">
      {/* Left: Hamburger (mobile) + Breadcrumb navigation */}
      <div className="flex items-center gap-2">
        {/* Hamburger menu button -- mobile only */}
        <button
          onClick={onMenuToggle}
          className="flex items-center justify-center rounded-lg p-2 text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700 md:hidden"
          aria-label="Open navigation menu"
        >
          <Menu size={20} />
        </button>

        <nav
          className="flex items-center gap-1.5 text-sm"
          aria-label="Breadcrumb"
        >
          {breadcrumbs.map((crumb, index) => {
            const isLast = index === breadcrumbs.length - 1;
            return (
              <span key={index} className="flex items-center gap-1.5">
                {index > 0 && (
                  <ChevronRight
                    size={14}
                    className="text-slate-400 dark:text-slate-500"
                    aria-hidden="true"
                  />
                )}
                {isLast || crumb.href === null ? (
                  <span className="font-medium text-gray-900 dark:text-white">
                    {crumb.label}
                  </span>
                ) : (
                  <Link
                    href={crumb.href}
                    className="text-gray-500 transition-colors hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
                  >
                    {crumb.label}
                  </Link>
                )}
              </span>
            );
          })}
        </nav>
      </div>

      {/* Right: Search + Actions */}
      <div className="flex items-center gap-3">
        {/* Search bar — opens command palette */}
        <button
          onClick={() =>
            window.dispatchEvent(
              new KeyboardEvent("keydown", { key: "k", metaKey: true }),
            )
          }
          className="relative hidden h-9 w-80 items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 pl-9 pr-16 text-left text-sm text-gray-400 transition-colors hover:border-gray-300 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-800/50 dark:text-gray-500 dark:hover:border-gray-500 dark:hover:bg-gray-700/50 lg:flex"
          aria-label="Open search (Cmd+K)"
        >
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500"
            aria-hidden="true"
          />
          Search assets, findings...
          <span className="absolute right-3 top-1/2 -translate-y-1/2 select-none rounded-md border border-gray-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-gray-400 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-500">
            Cmd+K
          </span>
        </button>

        {/* Divider */}
        <div
          className="hidden h-6 w-px bg-gray-200 dark:bg-gray-700 lg:block"
          aria-hidden="true"
        />

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="flex items-center justify-center rounded-lg p-2 text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700"
          aria-label={
            theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
          }
        >
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        {/* Notification bell */}
        <button
          className="relative flex items-center justify-center rounded-lg p-2 text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700"
          aria-label="Notifications"
        >
          <Bell size={18} />
        </button>

        {/* Divider */}
        <div
          className="h-6 w-px bg-gray-200 dark:bg-gray-700"
          aria-hidden="true"
        />

        {/* User avatar and info */}
        <div className="flex items-center gap-2.5">
          {/* Avatar circle with gradient */}
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-blue-600 text-sm font-semibold text-white shadow-sm">
            {getUserInitial(user?.full_name, user?.email)}
          </div>

          {/* Name and role */}
          <div className="hidden flex-col sm:flex">
            <span className="text-sm font-medium leading-tight text-gray-900 dark:text-white">
              {displayName}
            </span>
            <span className="text-[10px] font-medium leading-tight text-gray-500 dark:text-gray-400">
              {roleBadge}
            </span>
          </div>
        </div>

        {/* Divider */}
        <div
          className="h-6 w-px bg-gray-200 dark:bg-gray-700"
          aria-hidden="true"
        />

        {/* Logout */}
        <button
          onClick={logout}
          className="flex items-center justify-center rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-red-500 dark:text-gray-500 dark:hover:bg-gray-700 dark:hover:text-red-400"
          aria-label="Logout"
        >
          <LogOut size={18} />
        </button>
      </div>
    </header>
  );
}
