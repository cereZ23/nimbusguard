"use client";

import { useRouter } from "next/navigation";
import { ArrowRight, Lightbulb } from "lucide-react";
import PriorityBadge from "@/components/ui/priority-badge";
import type { PrioritySummary } from "@/types";

export default function TopActionsCard({
  summary,
}: {
  summary: PrioritySummary;
}) {
  const router = useRouter();
  const actions = summary.top_remediation_groups.slice(0, 5);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="mb-4 flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100 dark:bg-amber-900/40">
          <Lightbulb className="h-4 w-4 text-amber-600 dark:text-amber-400" />
        </div>
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            Top actions to fix this week
          </h2>
          <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">
            Each action resolves multiple findings at once
          </p>
        </div>
      </div>

      {actions.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
            No grouped remediation suggestions yet
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500">
            Run a scan first, then the top fixes will appear here
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {actions.map((action, idx) => (
            <li key={action.group}>
              <button
                type="button"
                onClick={() =>
                  router.push(
                    `/findings?remediation_group=${encodeURIComponent(
                      action.group,
                    )}&status=fail`,
                  )
                }
                className="group flex w-full items-start gap-3 rounded-xl border border-gray-200 p-3 text-left transition-all hover:border-indigo-300 hover:bg-indigo-50/50 dark:border-gray-700 dark:hover:border-indigo-700 dark:hover:bg-indigo-950/30"
              >
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-xs font-bold text-gray-600 group-hover:bg-indigo-100 group-hover:text-indigo-700 dark:bg-gray-700 dark:text-gray-300 dark:group-hover:bg-indigo-900/50 dark:group-hover:text-indigo-300">
                  {idx + 1}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-semibold text-gray-900 group-hover:text-indigo-700 dark:text-gray-100 dark:group-hover:text-indigo-300">
                      {action.action || action.group}
                    </p>
                    <PriorityBadge
                      value={action.top_priority}
                      placeholder={false}
                    />
                  </div>
                  <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                    Fixes{" "}
                    <span className="font-semibold text-gray-700 dark:text-gray-300">
                      {action.affected_count}
                    </span>{" "}
                    {action.affected_count === 1 ? "finding" : "findings"}
                  </p>
                </div>
                <ArrowRight className="h-4 w-4 shrink-0 text-gray-300 transition-colors group-hover:text-indigo-500 dark:text-gray-600" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {actions.length > 0 && (
        <button
          type="button"
          onClick={() => router.push("/findings?sort_by=priority&status=fail")}
          className="mt-3 inline-flex w-full items-center justify-center gap-1 rounded-lg border border-gray-200 px-3 py-2 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-700/50"
        >
          View all prioritised findings
          <ArrowRight className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}
