"use client";

import { useRouter } from "next/navigation";
import { ShieldAlert } from "lucide-react";
import WidgetWrapper from "./widget-wrapper";

interface ControlItem {
  code: string;
  name: string;
  severity: string;
  fail_count: number;
  total_count: number;
}

const SEVERITY_COLOR: Record<string, string> = {
  high: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  medium:
    "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  low: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
};

interface TopControlsWidgetProps {
  data: ControlItem[] | null;
  colSpan?: number;
  rowSpan?: number;
  editing?: boolean;
  onRemove?: () => void;
  onResize?: (larger: boolean) => void;
}

export default function TopControlsWidget({
  data,
  colSpan,
  rowSpan,
  editing,
  onRemove,
  onResize,
}: TopControlsWidgetProps) {
  const router = useRouter();
  const controls = data ?? [];

  return (
    <WidgetWrapper
      title="Top Failing Controls"
      colSpan={colSpan}
      rowSpan={rowSpan}
      editing={editing}
      onRemove={onRemove}
      onResize={onResize}
    >
      <div className="flex items-center gap-2 mb-3">
        <ShieldAlert className="h-4 w-4 text-indigo-500" />
        <span className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Top Failing Controls
        </span>
      </div>
      {controls.length === 0 ? (
        <p className="py-4 text-center text-sm text-gray-400">
          No failing controls
        </p>
      ) : (
        <div className="space-y-2">
          {controls.map((control) => {
            const pct =
              control.total_count > 0
                ? Math.round(
                    ((control.total_count - control.fail_count) /
                      control.total_count) *
                      100,
                  )
                : 0;
            return (
              <button
                type="button"
                key={control.code}
                onClick={() =>
                  router.push(
                    `/findings?control_id=${encodeURIComponent(control.code)}`,
                  )
                }
                className="group flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/40"
              >
                <span className="inline-flex shrink-0 rounded bg-indigo-50 px-1.5 py-0.5 font-mono text-[10px] font-bold text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">
                  {control.code}
                </span>
                <span className="min-w-0 flex-1 truncate text-xs text-gray-700 dark:text-gray-300">
                  {control.name}
                </span>
                <span
                  className={`shrink-0 rounded px-1 py-0.5 text-[9px] font-bold uppercase ${
                    SEVERITY_COLOR[control.severity] ??
                    "bg-gray-100 text-gray-600"
                  }`}
                >
                  {control.severity}
                </span>
                <span className="shrink-0 text-xs font-bold tabular-nums text-red-500">
                  {control.fail_count}
                </span>
                <div className="hidden shrink-0 sm:flex items-center gap-1">
                  <div className="h-1.5 w-12 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        pct >= 80
                          ? "bg-green-500"
                          : pct >= 50
                            ? "bg-amber-500"
                            : "bg-red-500"
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="w-7 text-right text-[9px] tabular-nums text-gray-500">
                    {pct}%
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </WidgetWrapper>
  );
}
