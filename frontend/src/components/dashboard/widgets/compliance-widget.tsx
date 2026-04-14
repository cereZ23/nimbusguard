"use client";

import { CheckCircle } from "lucide-react";
import WidgetWrapper from "./widget-wrapper";

interface ComplianceWidgetProps {
  data: { score: number; total: number; passing: number } | null;
  colSpan?: number;
  rowSpan?: number;
  editing?: boolean;
  onRemove?: () => void;
  onResize?: (larger: boolean) => void;
}

export default function ComplianceWidget({
  data,
  colSpan,
  rowSpan,
  editing,
  onRemove,
  onResize,
}: ComplianceWidgetProps) {
  const score = data?.score ?? 0;
  const total = data?.total ?? 0;
  const passing = data?.passing ?? 0;

  const getColor = (v: number): string => {
    if (v >= 80) return "text-green-600 dark:text-green-400";
    if (v >= 50) return "text-amber-600 dark:text-amber-400";
    return "text-red-600 dark:text-red-400";
  };

  const getBarColor = (v: number): string => {
    if (v >= 80) return "from-green-400 to-green-500";
    if (v >= 50) return "from-amber-400 to-amber-500";
    return "from-red-400 to-red-500";
  };

  return (
    <WidgetWrapper
      title="Compliance Score"
      colSpan={colSpan}
      rowSpan={rowSpan}
      editing={editing}
      onRemove={onRemove}
      onResize={onResize}
    >
      <div className="flex items-center gap-2 mb-4">
        <CheckCircle className="h-4 w-4 text-indigo-500" />
        <span className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Compliance Score
        </span>
      </div>
      <div className="flex flex-col items-center gap-3">
        <span
          className={`text-4xl font-extrabold tracking-tight ${getColor(score)}`}
        >
          {score}%
        </span>
        <div className="w-full">
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
            <div
              className={`h-full rounded-full bg-gradient-to-r ${getBarColor(score)} transition-all duration-700`}
              style={{ width: `${score}%` }}
            />
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {passing.toLocaleString()} / {total.toLocaleString()} checks passing
        </p>
      </div>
    </WidgetWrapper>
  );
}
