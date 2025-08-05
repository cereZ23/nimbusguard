"use client";

/**
 * RecentFindings -- table of the most recently detected findings.
 * Each row navigates to /findings/<id>. "View all" links to /findings.
 */

import { useRouter } from "next/navigation";
import { Eye, ChevronRight } from "lucide-react";
import SeverityBadge from "@/components/ui/severity-badge";
import StatusBadge from "@/components/ui/status-badge";
import { GlassCard, SectionHeader } from "./chart-section";
import type { Finding } from "@/types";

interface RecentFindingsProps {
  findings: Finding[];
}

export default function RecentFindings({ findings }: RecentFindingsProps) {
  const router = useRouter();

  if (findings.length === 0) return null;

  return (
    <GlassCard>
      <SectionHeader
        icon={<Eye className="h-5 w-5 text-indigo-500" />}
        title="Recent Findings"
        subtitle="Latest security issues detected"
        action={
          <button
            type="button"
            onClick={() => router.push("/findings")}
            className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium text-indigo-600 transition-colors hover:bg-indigo-50 dark:text-indigo-400 dark:hover:bg-indigo-900/30"
          >
            View all
            <ChevronRight className="h-4 w-4" />
          </button>
        }
      />
      <div className="mt-6 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              <th className="pb-3 pr-4 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                Finding
              </th>
              <th className="pb-3 pr-4 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                Severity
              </th>
              <th className="pb-3 pr-4 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                Status
              </th>
              <th className="pb-3 pr-4 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                Detected
              </th>
              <th className="pb-3 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                <span className="sr-only">Action</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700/60">
            {findings.map((finding) => (
              <tr
                key={finding.id}
                onClick={() => router.push(`/findings/${finding.id}`)}
                className="group cursor-pointer transition-colors duration-150 hover:bg-indigo-50/50 dark:hover:bg-indigo-900/10"
              >
                <td className="max-w-xs truncate py-3.5 pr-4 font-medium text-gray-800 dark:text-gray-200">
                  {finding.title}
                </td>
                <td className="py-3.5 pr-4">
                  <SeverityBadge severity={finding.severity} />
                </td>
                <td className="py-3.5 pr-4">
                  <StatusBadge status={finding.status} />
                </td>
                <td className="py-3.5 pr-4 text-gray-500 dark:text-gray-400">
                  {new Date(finding.first_detected_at).toLocaleDateString()}
                </td>
                <td className="py-3.5">
                  <ChevronRight className="h-4 w-4 text-gray-300 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-indigo-500 dark:text-gray-600 dark:group-hover:text-indigo-400" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassCard>
  );
}
