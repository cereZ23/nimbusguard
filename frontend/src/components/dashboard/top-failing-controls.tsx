"use client";

/**
 * TopFailingControls -- list of controls with the most non-compliant resources.
 * Clicking a row navigates to /findings?control_id=<code>.
 *
 * NOTE: The findings page filters by `control_id` from URL search params.
 * The backend resolves the control code to its UUID internally, so we pass
 * the control `code` (e.g. "CIS-AZ-01") here as a readable identifier.
 */

import { useRouter } from "next/navigation";
import { ShieldAlert, ChevronRight } from "lucide-react";
import SeverityBadge from "@/components/ui/severity-badge";
import { GlassCard, SectionHeader } from "./chart-section";
import type { FailingControl } from "@/types";

interface TopFailingControlsProps {
  controls: FailingControl[];
}

export default function TopFailingControls({
  controls,
}: TopFailingControlsProps) {
  const router = useRouter();

  if (controls.length === 0) return null;

  const handleControlClick = (control: FailingControl) => {
    router.push(`/findings?control_id=${encodeURIComponent(control.code)}`);
  };

  return (
    <GlassCard>
      <SectionHeader
        icon={<ShieldAlert className="h-5 w-5 text-indigo-500" />}
        title="Top Failing Controls"
        subtitle="Click a control to view its findings"
      />
      <div className="mt-6 space-y-3">
        {controls.map((control) => {
          const compliancePercent =
            control.total_count > 0
              ? Math.round(
                  ((control.total_count - control.fail_count) /
                    control.total_count) *
                    100,
                )
              : 0;

          const barColorClass =
            compliancePercent >= 80
              ? "from-green-400 to-green-500"
              : compliancePercent >= 50
                ? "from-amber-400 to-amber-500"
                : "from-red-400 to-red-500";

          return (
            <button
              type="button"
              key={control.code}
              onClick={() => handleControlClick(control)}
              className="group relative w-full overflow-hidden rounded-xl border border-gray-100 bg-gray-50/50 p-4 text-left transition-all duration-200 hover:border-indigo-200 hover:bg-indigo-50/30 dark:border-gray-700/50 dark:bg-gray-800/50 dark:hover:border-indigo-700/50 dark:hover:bg-indigo-900/20 cursor-pointer"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="inline-flex items-center rounded-lg bg-indigo-50 px-2.5 py-1 font-mono text-xs font-bold text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">
                    {control.code}
                  </span>
                  <span className="truncate text-sm font-medium text-gray-800 dark:text-gray-200">
                    {control.name}
                  </span>
                  <SeverityBadge severity={control.severity} />
                </div>

                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <span className="text-sm font-bold text-red-500 dark:text-red-400">
                      {control.fail_count}
                    </span>
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {" "}
                      / {control.total_count} failing
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <div className="h-2 w-28 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                      <div
                        className={`h-full rounded-full bg-gradient-to-r ${barColorClass} transition-all duration-700`}
                        style={{
                          width: `${compliancePercent}%`,
                        }}
                      />
                    </div>
                    <span
                      className={`min-w-[3rem] text-right text-xs font-bold ${
                        compliancePercent >= 80
                          ? "text-green-600 dark:text-green-400"
                          : compliancePercent >= 50
                            ? "text-amber-600 dark:text-amber-400"
                            : "text-red-600 dark:text-red-400"
                      }`}
                    >
                      {compliancePercent}%
                    </span>
                  </div>

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
