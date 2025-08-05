"use client";

import { useRouter } from "next/navigation";
import { Building2, ChevronRight } from "lucide-react";
import { GlassCard, SectionHeader } from "./chart-section";
import type { CloudAccount } from "@/types";

interface AccountBreakdownProps {
  accounts: CloudAccount[];
  isLoading?: boolean;
}

function ProviderBadge({ provider }: { provider: string }) {
  const isAzure = provider === "azure";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-bold ${
        isAzure
          ? "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
          : "bg-orange-50 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
      }`}
    >
      {isAzure ? "Azure" : "AWS"}
    </span>
  );
}

export default function AccountBreakdown({
  accounts,
  isLoading,
}: AccountBreakdownProps) {
  const router = useRouter();

  if (isLoading) {
    return (
      <GlassCard>
        <SectionHeader
          icon={<Building2 className="h-5 w-5 text-indigo-500" />}
          title="Account Scores"
          subtitle="Per-account security posture"
        />
        <div className="mt-6 space-y-3">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-16 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-700/50"
            />
          ))}
        </div>
      </GlassCard>
    );
  }

  if (accounts.length === 0) return null;

  return (
    <GlassCard>
      <SectionHeader
        icon={<Building2 className="h-5 w-5 text-indigo-500" />}
        title="Account Scores"
        subtitle="Click an account to view its findings"
      />
      <div className="mt-6 space-y-3">
        {accounts.map((account) => {
          const meta = account.metadata_ as Record<string, unknown> | null;
          const secureScore =
            meta && typeof meta.secure_score === "number"
              ? (meta.secure_score as number)
              : null;
          const clamped =
            secureScore !== null
              ? Math.max(0, Math.min(100, secureScore))
              : null;

          const barColor =
            clamped !== null && clamped >= 80
              ? "from-green-400 to-green-500"
              : clamped !== null && clamped >= 50
                ? "from-amber-400 to-amber-500"
                : "from-red-400 to-red-500";

          const textColor =
            clamped !== null && clamped >= 80
              ? "text-green-600 dark:text-green-400"
              : clamped !== null && clamped >= 50
                ? "text-amber-600 dark:text-amber-400"
                : "text-red-600 dark:text-red-400";

          const lastScan = account.last_scan_at
            ? new Date(account.last_scan_at).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })
            : "Never";

          return (
            <button
              type="button"
              key={account.id}
              onClick={() =>
                router.push(
                  `/findings?account_id=${encodeURIComponent(account.id)}`,
                )
              }
              className="group relative w-full overflow-hidden rounded-xl border border-gray-100 bg-gray-50/50 p-4 text-left transition-all duration-200 hover:border-indigo-200 hover:bg-indigo-50/30 dark:border-gray-700/50 dark:bg-gray-800/50 dark:hover:border-indigo-700/50 dark:hover:bg-indigo-900/20"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-center gap-3">
                  <ProviderBadge provider={account.provider} />
                  <span className="truncate text-sm font-medium text-gray-800 dark:text-gray-200">
                    {account.display_name}
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  {clamped !== null ? (
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-32 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                        <div
                          className={`h-full rounded-full bg-gradient-to-r ${barColor} transition-all duration-700`}
                          style={{ width: `${clamped}%` }}
                        />
                      </div>
                      <span
                        className={`min-w-[3rem] text-right text-xs font-bold ${textColor}`}
                      >
                        {Math.round(clamped)}%
                      </span>
                    </div>
                  ) : (
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      No score
                    </span>
                  )}
                  <span className="hidden text-xs text-gray-400 sm:inline dark:text-gray-500">
                    {lastScan}
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-300 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-indigo-500 dark:text-gray-600 dark:group-hover:text-indigo-400" />
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </GlassCard>
  );
}
