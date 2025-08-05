"use client";

import { useRouter } from "next/navigation";
import { Eye, ChevronRight } from "lucide-react";
import WidgetWrapper from "./widget-wrapper";

interface FindingItem {
  id: string;
  title: string;
  severity: string;
  status: string;
  first_detected_at: string | null;
}

const SEVERITY_COLOR: Record<string, string> = {
  high: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  medium:
    "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  low: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
};

interface RecentFindingsWidgetProps {
  data: FindingItem[] | null;
  colSpan?: number;
  rowSpan?: number;
  editing?: boolean;
  onRemove?: () => void;
  onResize?: (larger: boolean) => void;
}

export default function RecentFindingsWidget({
  data,
  colSpan,
  rowSpan,
  editing,
  onRemove,
  onResize,
}: RecentFindingsWidgetProps) {
  const router = useRouter();
  const findings = data ?? [];

  return (
    <WidgetWrapper
      title="Recent Findings"
      colSpan={colSpan}
      rowSpan={rowSpan}
      editing={editing}
      onRemove={onRemove}
      onResize={onResize}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Eye className="h-4 w-4 text-indigo-500" />
          <span className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            Recent Findings
          </span>
        </div>
        <button
          type="button"
          onClick={() => router.push("/findings")}
          className="flex items-center gap-1 text-xs font-medium text-indigo-600 transition-colors hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300"
        >
          View all
          <ChevronRight className="h-3 w-3" />
        </button>
      </div>
      {findings.length === 0 ? (
        <p className="py-4 text-center text-sm text-gray-400">
          No recent findings
        </p>
      ) : (
        <div className="space-y-2">
          {findings.map((finding) => (
            <button
              type="button"
              key={finding.id}
              onClick={() => router.push(`/findings/${finding.id}`)}
              className="group flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/40"
            >
              <span
                className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                  SEVERITY_COLOR[finding.severity] ??
                  "bg-gray-100 text-gray-600"
                }`}
              >
                {finding.severity}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm text-gray-800 dark:text-gray-200">
                {finding.title}
              </span>
              {finding.first_detected_at && (
                <span className="shrink-0 text-[10px] tabular-nums text-gray-400">
                  {new Date(finding.first_detected_at).toLocaleDateString()}
                </span>
              )}
              <ChevronRight className="h-3 w-3 shrink-0 text-gray-300 transition-transform group-hover:translate-x-0.5 group-hover:text-indigo-500 dark:text-gray-600" />
            </button>
          ))}
        </div>
      )}
    </WidgetWrapper>
  );
}
