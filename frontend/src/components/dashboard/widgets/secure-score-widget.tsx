"use client";

import { Shield } from "lucide-react";
import WidgetWrapper from "./widget-wrapper";

interface SecureScoreWidgetProps {
  data: { score: number | null } | null;
  colSpan?: number;
  rowSpan?: number;
  editing?: boolean;
  onRemove?: () => void;
  onResize?: (larger: boolean) => void;
}

export default function SecureScoreWidget({
  data,
  colSpan,
  rowSpan,
  editing,
  onRemove,
  onResize,
}: SecureScoreWidgetProps) {
  const score = data?.score;
  const clampedValue = score != null ? Math.max(0, Math.min(100, score)) : 0;

  const getColor = (v: number): string => {
    if (v >= 80) return "#22c55e";
    if (v >= 50) return "#f59e0b";
    return "#ef4444";
  };

  const getLabel = (v: number): string => {
    if (v >= 90) return "Excellent";
    if (v >= 80) return "Good";
    if (v >= 60) return "Fair";
    if (v >= 40) return "Needs Work";
    return "Critical";
  };

  const color = getColor(clampedValue);

  // Simple circular progress
  const size = 120;
  const strokeWidth = 10;
  const r = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (clampedValue / 100) * circumference;

  return (
    <WidgetWrapper
      title="Secure Score"
      colSpan={colSpan}
      rowSpan={rowSpan}
      editing={editing}
      onRemove={onRemove}
      onResize={onResize}
    >
      <div className="flex flex-col items-center gap-2">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-indigo-500" />
          <span className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            Secure Score
          </span>
        </div>
        <div className="relative">
          <svg width={size} height={size} className="drop-shadow-sm">
            <circle
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke="currentColor"
              className="text-gray-200 dark:text-gray-700"
              strokeWidth={strokeWidth}
            />
            {score != null && (
              <circle
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={color}
                strokeWidth={strokeWidth}
                strokeDasharray={circumference}
                strokeDashoffset={offset}
                strokeLinecap="round"
                transform={`rotate(-90 ${size / 2} ${size / 2})`}
                className="transition-all duration-700"
              />
            )}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-extrabold text-gray-900 dark:text-white">
              {score != null ? `${score}%` : "N/A"}
            </span>
            {score != null && (
              <span className="text-[10px] font-medium text-gray-500 dark:text-gray-400">
                {getLabel(clampedValue)}
              </span>
            )}
          </div>
        </div>
      </div>
    </WidgetWrapper>
  );
}
