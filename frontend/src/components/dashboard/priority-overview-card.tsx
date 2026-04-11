"use client";

import { useRouter } from "next/navigation";
import type { Priority, PrioritySummary } from "@/types";

const TIER_STYLES: Record<
  Priority,
  { dot: string; bg: string; text: string; subtitle: string; label: string }
> = {
  P0: {
    dot: "bg-red-500",
    bg: "bg-red-50 dark:bg-red-900/30",
    text: "text-red-700 dark:text-red-400",
    subtitle: "Fix now",
    label: "P0",
  },
  P1: {
    dot: "bg-orange-500",
    bg: "bg-orange-50 dark:bg-orange-900/30",
    text: "text-orange-700 dark:text-orange-400",
    subtitle: "Fix this week",
    label: "P1",
  },
  P2: {
    dot: "bg-amber-500",
    bg: "bg-amber-50 dark:bg-amber-900/30",
    text: "text-amber-700 dark:text-amber-400",
    subtitle: "Fix this sprint",
    label: "P2",
  },
  P3: {
    dot: "bg-green-500",
    bg: "bg-green-50 dark:bg-green-900/30",
    text: "text-green-700 dark:text-green-400",
    subtitle: "Best practice",
    label: "P3",
  },
};

export default function PriorityOverviewCard({
  summary,
}: {
  summary: PrioritySummary;
}) {
  const router = useRouter();
  const tiers: Priority[] = ["P0", "P1", "P2", "P3"];

  const currentScore = summary.current_secure_score;
  const projectedP0 = summary.projected_after_p0;
  const projectedP0P1 = summary.projected_after_p0_p1;

  const p0Delta = Math.max(
    0,
    Math.round((projectedP0 - currentScore) * 10) / 10,
  );
  const p1Delta = Math.max(
    0,
    Math.round((projectedP0P1 - projectedP0) * 10) / 10,
  );

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            Priority Overview
          </h2>
          <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">
            Failing findings ranked by severity, effort and exposure
          </p>
        </div>
        <div className="text-right">
          <div className="text-xs uppercase tracking-wide text-gray-400 dark:text-gray-500">
            Secure Score
          </div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white">
            {currentScore.toFixed(1)}%
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {tiers.map((tier) => {
          const styles = TIER_STYLES[tier];
          const count = summary.priority_counts[tier] ?? 0;
          return (
            <button
              key={tier}
              type="button"
              onClick={() =>
                router.push(`/findings?priority=${tier}&status=fail`)
              }
              className={`group flex flex-col items-start gap-1 rounded-xl border border-gray-200 p-4 text-left transition-all hover:-translate-y-0.5 hover:shadow-md dark:border-gray-700 ${styles.bg}`}
              aria-label={`${count} ${tier} findings, ${styles.subtitle}`}
            >
              <div className="flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${styles.dot}`} />
                <span
                  className={`text-xs font-bold uppercase tracking-wide ${styles.text}`}
                >
                  {styles.label}
                </span>
              </div>
              <div className={`text-3xl font-extrabold ${styles.text}`}>
                {count.toLocaleString()}
              </div>
              <div className={`text-xs ${styles.text}`}>{styles.subtitle}</div>
            </button>
          );
        })}
      </div>

      {/* Secure Score projection bar */}
      {summary.total_fail + summary.total_pass > 0 && (
        <div className="mt-5 space-y-2">
          <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
            <span>Projected Secure Score after fixing priorities</span>
            <span className="font-semibold">
              {projectedP0P1.toFixed(1)}%{" "}
              <span className="text-gray-400">(potential)</span>
            </span>
          </div>
          <div className="relative h-3 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
            {/* Current score bar */}
            <div
              className="absolute left-0 top-0 h-full bg-gradient-to-r from-indigo-500 to-indigo-400"
              style={{ width: `${currentScore}%` }}
            />
            {/* P0 projected segment */}
            <div
              className="absolute top-0 h-full bg-gradient-to-r from-red-400/70 to-red-300/70"
              style={{
                left: `${currentScore}%`,
                width: `${Math.max(0, projectedP0 - currentScore)}%`,
              }}
            />
            {/* P1 projected segment */}
            <div
              className="absolute top-0 h-full bg-gradient-to-r from-orange-400/70 to-orange-300/70"
              style={{
                left: `${projectedP0}%`,
                width: `${Math.max(0, projectedP0P1 - projectedP0)}%`,
              }}
            />
          </div>
          <div className="flex items-center justify-between text-[11px] text-gray-400 dark:text-gray-500">
            <span>
              Now:{" "}
              <span className="font-semibold text-gray-600 dark:text-gray-300">
                {currentScore.toFixed(1)}%
              </span>
            </span>
            <span>
              Fix P0:{" "}
              <span className="font-semibold text-red-600 dark:text-red-400">
                +{p0Delta.toFixed(1)}
              </span>
            </span>
            <span>
              Fix P0+P1:{" "}
              <span className="font-semibold text-orange-600 dark:text-orange-400">
                +{p1Delta.toFixed(1)}
              </span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
