"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { Cloud, Users, Shield, Plug, Key, Lock, FileText } from "lucide-react";
import AppShell from "@/components/layout/app-shell";

const TABS = [
  { label: "Accounts", href: "/settings/accounts", icon: Cloud },
  { label: "Users", href: "/settings/users", icon: Users },
  { label: "Roles", href: "/settings/roles", icon: Shield },
  { label: "Integrations", href: "/settings/integrations", icon: Plug },
  { label: "API Keys", href: "/settings/api-keys", icon: Key },
  { label: "Security", href: "/settings/security", icon: Lock },
  { label: "Reports", href: "/settings/reports", icon: FileText },
];

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Settings
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Manage connected cloud accounts and scan configurations
          </p>
        </div>

        {/* Tab navigation */}
        <div className="border-b border-gray-200 dark:border-gray-700">
          <nav
            className="-mb-px flex space-x-6 overflow-x-auto"
            aria-label="Settings tabs"
          >
            {TABS.map((tab) => {
              const isActive = pathname.startsWith(tab.href);
              const Icon = tab.icon;
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`flex items-center gap-2 whitespace-nowrap border-b-2 px-1 py-3 text-sm font-medium transition-colors ${
                    isActive
                      ? "border-blue-500 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                      : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 dark:text-gray-400 dark:hover:border-gray-600 dark:hover:text-gray-300"
                  }`}
                >
                  <Icon size={16} />
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Tab content */}
        {children}
      </div>
    </AppShell>
  );
}
