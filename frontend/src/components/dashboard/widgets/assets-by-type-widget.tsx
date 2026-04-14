"use client";

import { Layers } from "lucide-react";
import WidgetWrapper from "./widget-wrapper";

interface AssetsByTypeWidgetProps {
  data: Record<string, number> | null;
  colSpan?: number;
  rowSpan?: number;
  editing?: boolean;
  onRemove?: () => void;
  onResize?: (larger: boolean) => void;
}

const COLORS = [
  "#6366f1",
  "#8b5cf6",
  "#a78bfa",
  "#c084fc",
  "#d946ef",
  "#f472b6",
  "#fb923c",
  "#facc15",
  "#4ade80",
  "#22d3ee",
];

export default function AssetsByTypeWidget({
  data,
  colSpan,
  rowSpan,
  editing,
  onRemove,
  onResize,
}: AssetsByTypeWidgetProps) {
  const entries = data ? Object.entries(data) : [];
  const total = entries.reduce((sum, [, count]) => sum + count, 0);

  return (
    <WidgetWrapper
      title="Assets by Type"
      colSpan={colSpan}
      rowSpan={rowSpan}
      editing={editing}
      onRemove={onRemove}
      onResize={onResize}
    >
      <div className="flex items-center gap-2 mb-3">
        <Layers className="h-4 w-4 text-indigo-500" />
        <span className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Assets by Type
        </span>
      </div>
      {entries.length === 0 ? (
        <p className="py-4 text-center text-sm text-gray-400">No asset data</p>
      ) : (
        <div className="space-y-2">
          {entries.slice(0, 8).map(([resourceType, count], idx) => {
            const pct = total > 0 ? Math.round((count / total) * 100) : 0;
            const color = COLORS[idx % COLORS.length];
            // Shorten long resource type names
            const shortName = resourceType.includes("/")
              ? (resourceType.split("/").pop() ?? resourceType)
              : resourceType;
            return (
              <div key={resourceType} className="flex items-center gap-2">
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: color }}
                />
                <span
                  className="min-w-0 flex-1 truncate text-xs text-gray-600 dark:text-gray-300"
                  title={resourceType}
                >
                  {shortName}
                </span>
                <span className="shrink-0 text-xs font-bold tabular-nums text-gray-900 dark:text-white">
                  {count.toLocaleString()}
                </span>
                <div className="hidden shrink-0 sm:block">
                  <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${pct}%`, backgroundColor: color }}
                    />
                  </div>
                </div>
                <span className="w-7 shrink-0 text-right text-[10px] tabular-nums text-gray-500">
                  {pct}%
                </span>
              </div>
            );
          })}
        </div>
      )}
    </WidgetWrapper>
  );
}
