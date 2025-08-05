"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { ShieldAlert } from "lucide-react";
import { ChartTooltip } from "@/components/dashboard/chart-section";
import WidgetWrapper from "./widget-wrapper";

const SEVERITY_COLORS: Record<string, string> = {
  high: "#ef4444",
  medium: "#f59e0b",
  low: "#3b82f6",
};

interface SeverityBreakdownWidgetProps {
  data: Record<string, number> | null;
  colSpan?: number;
  rowSpan?: number;
  editing?: boolean;
  onRemove?: () => void;
  onResize?: (larger: boolean) => void;
}

export default function SeverityBreakdownWidget({
  data,
  colSpan,
  rowSpan,
  editing,
  onRemove,
  onResize,
}: SeverityBreakdownWidgetProps) {
  const entries = data
    ? Object.entries(data).map(([severity, count]) => ({
        name: severity.charAt(0).toUpperCase() + severity.slice(1),
        severity,
        value: count,
        fill: SEVERITY_COLORS[severity] ?? "#6b7280",
      }))
    : [];

  const total = entries.reduce((sum, e) => sum + e.value, 0);

  return (
    <WidgetWrapper
      title="Findings by Severity"
      colSpan={colSpan}
      rowSpan={rowSpan}
      editing={editing}
      onRemove={onRemove}
      onResize={onResize}
    >
      <div className="flex items-center gap-2 mb-3">
        <ShieldAlert className="h-4 w-4 text-indigo-500" />
        <span className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Severity Breakdown
        </span>
      </div>
      {entries.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-400">No data</p>
      ) : (
        <div className="flex items-center gap-4">
          <div className="w-28">
            <ResponsiveContainer width="100%" height={110}>
              <PieChart>
                <Pie
                  data={entries}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={48}
                  innerRadius={30}
                  strokeWidth={0}
                  paddingAngle={3}
                >
                  {entries.map((entry) => (
                    <Cell key={entry.severity} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip content={<ChartTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex-1 space-y-1.5">
            {entries.map((entry) => {
              const pct =
                total > 0 ? Math.round((entry.value / total) * 100) : 0;
              return (
                <div key={entry.severity} className="flex items-center gap-2">
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ backgroundColor: entry.fill }}
                  />
                  <span className="flex-1 text-xs text-gray-600 dark:text-gray-300">
                    {entry.name}
                  </span>
                  <span className="text-xs font-bold tabular-nums text-gray-900 dark:text-white">
                    {entry.value}
                  </span>
                  <span className="w-8 text-right text-[10px] tabular-nums text-gray-500">
                    {pct}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </WidgetWrapper>
  );
}
