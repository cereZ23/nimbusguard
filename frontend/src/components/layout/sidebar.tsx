"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Columns3,
  Cloud,
  Server,
  AlertTriangle,
  CheckCircle,
  FileDown,
  Settings,
  ChevronLeft,
  ChevronRight,
  Shield,
  HelpCircle,
  Lock,
  Network,
  X,
} from "lucide-react";
import { useBranding } from "@/lib/branding";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: "OPERATIONS",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
      { label: "Dashboards", href: "/dashboards", icon: Columns3 },
      { label: "Multi-Cloud", href: "/multi-cloud", icon: Cloud },
      { label: "Assets", href: "/assets", icon: Server },
      { label: "Asset Graph", href: "/asset-graph", icon: Network },
      { label: "Findings", href: "/findings", icon: AlertTriangle },
      { label: "Compliance", href: "/compliance", icon: CheckCircle },
    ],
  },
  {
    title: "SYSTEM",
    items: [
      { label: "Reports", href: "/reports", icon: FileDown },
      { label: "Settings", href: "/settings", icon: Settings },
      { label: "Help", href: "/help", icon: HelpCircle },
    ],
  },
];

interface SidebarProps {
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

export default function Sidebar({
  mobileOpen = false,
  onMobileClose,
}: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const { branding } = useBranding();

  // Close mobile sidebar on Escape key
  useEffect(() => {
    if (!mobileOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onMobileClose?.();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [mobileOpen, onMobileClose]);

  // Prevent body scroll when mobile sidebar is open
  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  const handleNavClick = useCallback(() => {
    onMobileClose?.();
  }, [onMobileClose]);

  /* ── Logo icon: tenant logo or default Shield ── */

  const logoIcon = branding.logo_url ? (
    <div className="relative flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-lg ring-1 ring-indigo-500/20">
      <Image
        src={branding.logo_url}
        alt={`${branding.company_name} logo`}
        width={36}
        height={36}
        className="h-full w-full object-contain"
        unoptimized
      />
    </div>
  ) : (
    <div className="relative flex shrink-0 items-center justify-center">
      <div className="absolute inset-0 rounded-lg bg-gradient-to-br from-blue-500/20 to-indigo-500/20 blur-lg" />
      <div
        className="relative flex h-9 w-9 items-center justify-center rounded-lg ring-1"
        style={{
          backgroundColor: `${branding.primary_color}15`,
          borderColor: `${branding.primary_color}33`,
        }}
      >
        <Shield size={20} style={{ color: branding.primary_color }} />
      </div>
    </div>
  );

  /* ── Shared sub-components rendered by both desktop and mobile ── */

  const logoArea = (showExpanded: boolean) => (
    <div
      className={`flex h-[72px] items-center gap-3 px-4 ${
        !showExpanded ? "justify-center" : ""
      }`}
    >
      {logoIcon}

      {showExpanded && (
        <div className="flex flex-col">
          <span
            className="text-[15px] font-bold tracking-widest"
            style={{ color: branding.primary_color }}
          >
            {branding.company_name}
          </span>
          <span className="text-[10px] font-medium tracking-wide text-slate-500">
            v3.0
          </span>
        </div>
      )}
    </div>
  );

  const navContent = (showExpanded: boolean, closeSidebar?: () => void) => (
    <nav className="flex-1 overflow-y-auto px-3 py-4">
      {NAV_GROUPS.map((group, groupIndex) => (
        <div key={group.title}>
          {/* Group separator (not before the first group) */}
          {groupIndex > 0 && (
            <div className="my-4">
              <div className="mx-1 h-px bg-gradient-to-r from-transparent via-slate-700/60 to-transparent" />
            </div>
          )}

          {/* Group label */}
          {showExpanded && (
            <div className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
              {group.title}
            </div>
          )}

          {/* Collapsed state: thin line separator instead of label */}
          {!showExpanded && groupIndex > 0 && (
            <div className="mx-auto mb-2 h-px w-6 bg-slate-700/60" />
          )}

          <div className="space-y-0.5">
            {group.items.map((item) => {
              const isActive = pathname.startsWith(item.href);
              const Icon = item.icon;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={closeSidebar}
                  className={`group relative flex items-center gap-3 rounded-lg px-3 py-2.5 transition-all duration-200 ${
                    !showExpanded ? "justify-center" : ""
                  } ${
                    isActive
                      ? "bg-sidebar-active/80 text-sidebar-text-active"
                      : "text-sidebar-text hover:bg-sidebar-hover hover:text-sidebar-text-active"
                  }`}
                  title={!showExpanded ? item.label : undefined}
                >
                  {/* Active indicator -- left accent bar */}
                  {isActive && (
                    <span
                      className="absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-r-full"
                      style={{ backgroundColor: branding.primary_color }}
                    />
                  )}

                  <Icon
                    size={20}
                    className={`shrink-0 transition-colors duration-200 ${
                      isActive
                        ? ""
                        : "text-slate-400 group-hover:text-slate-300"
                    }`}
                    style={
                      isActive ? { color: branding.primary_color } : undefined
                    }
                  />

                  {showExpanded && (
                    <span className="text-[13px] font-medium">
                      {item.label}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );

  const securityBadge = (
    <div className="mx-3 mb-3 flex items-center gap-2 rounded-lg bg-slate-800/50 px-3 py-2.5 ring-1 ring-slate-700/50">
      <Lock size={14} className="shrink-0 text-emerald-400" />
      <span className="text-[11px] font-medium text-slate-400">
        Secured by {branding.company_name}
      </span>
      <span className="ml-auto h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]" />
    </div>
  );

  return (
    <>
      {/* ── Mobile: backdrop overlay ── */}
      <div
        className={`fixed inset-0 z-40 bg-black/50 transition-opacity duration-300 md:hidden ${
          mobileOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onMobileClose}
        aria-hidden="true"
      />

      {/* ── Mobile: slide-in sidebar ── */}
      <aside
        className={`fixed left-0 top-0 z-50 flex h-full w-[280px] flex-col bg-sidebar-bg text-sidebar-text transition-transform duration-300 ease-in-out md:hidden ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation menu"
      >
        {/* Mobile header with close button */}
        <div className="flex h-[72px] items-center justify-between px-4">
          <div className="flex items-center gap-3">
            {logoIcon}
            <div className="flex flex-col">
              <span
                className="text-[15px] font-bold tracking-widest"
                style={{ color: branding.primary_color }}
              >
                {branding.company_name}
              </span>
              <span className="text-[10px] font-medium tracking-wide text-slate-500">
                v3.0
              </span>
            </div>
          </div>

          <button
            onClick={onMobileClose}
            className="flex items-center justify-center rounded-lg p-2 text-sidebar-text transition-colors hover:bg-sidebar-hover hover:text-sidebar-text-active"
            aria-label="Close navigation menu"
          >
            <X size={20} />
          </button>
        </div>

        {/* Gradient line separator */}
        <div
          className="mx-3 h-px"
          style={{
            background: `linear-gradient(to right, transparent, ${branding.primary_color}4D, transparent)`,
          }}
        />

        {/* Navigation (always expanded on mobile) */}
        {navContent(true, handleNavClick)}

        {/* Bottom section */}
        <div className="mt-auto">
          {securityBadge}
          <div className="mx-3 h-px bg-gradient-to-r from-transparent via-slate-700/60 to-transparent" />
          {/* No collapse toggle on mobile -- just a spacer */}
          <div className="p-3" />
        </div>
      </aside>

      {/* ── Desktop: static sidebar ── */}
      <aside
        className={`relative hidden flex-col bg-sidebar-bg text-sidebar-text transition-all duration-300 ease-in-out md:flex ${
          collapsed ? "w-16" : "w-[260px]"
        }`}
      >
        {/* Logo area */}
        {logoArea(!collapsed)}

        {/* Gradient line separator */}
        <div
          className="mx-3 h-px"
          style={{
            background: `linear-gradient(to right, transparent, ${branding.primary_color}4D, transparent)`,
          }}
        />

        {/* Navigation */}
        {navContent(!collapsed)}

        {/* Bottom section */}
        <div className="mt-auto">
          {/* Security status indicator */}
          {!collapsed && securityBadge}

          {/* Gradient separator */}
          <div className="mx-3 h-px bg-gradient-to-r from-transparent via-slate-700/60 to-transparent" />

          {/* Collapse toggle (desktop only) */}
          <div className="p-3">
            <button
              onClick={() => setCollapsed(!collapsed)}
              className={`flex w-full items-center rounded-lg px-3 py-2 text-sidebar-text transition-all duration-200 hover:bg-sidebar-hover hover:text-sidebar-text-active ${
                collapsed ? "justify-center" : "gap-3"
              }`}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? (
                <ChevronRight size={18} />
              ) : (
                <>
                  <ChevronLeft size={18} />
                  <span className="text-[13px] font-medium">Collapse</span>
                </>
              )}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
