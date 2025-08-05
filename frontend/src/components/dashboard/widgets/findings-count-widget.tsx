"use client";

import { AlertTriangle, Server } from "lucide-react";
import WidgetWrapper from "./widget-wrapper";

interface FindingsCountWidgetProps {
  widgetType: "total_findings" | "total_assets";
  data: { count: number } | null;
  colSpan?: number;
  rowSpan?: number;
  editing?: boolean;
  onRemove?: () => void;
  onResize?: (larger: boolean) => void;
}

const WIDGET_CONFIG = {
  total_findings: {
    title: "Total Findings",
    subtitle: "Open issues",
    icon: AlertTriangle,
    color: "text-amber-600 dark:text-amber-400",
    bg: "bg-amber-100 dark:bg-amber-900/40",
    accentFrom: "#f59e0b",
    accentTo: "#fbbf24",
  },
  total_assets: {
    title: "Total Assets",
    subtitle: "Across all accounts",
    icon: Server,
    color: "text-violet-600 dark:text-violet-400",
    bg: "bg-violet-100 dark:bg-violet-900/40",
    accentFrom: "#7c3aed",
    accentTo: "#a78bfa",
  },
};

export default function FindingsCountWidget({
  widgetType,
  data,
  colSpan,
  rowSpan,
  editing,
  onRemove,
  onResize,
}: FindingsCountWidgetProps) {
  const config = WIDGET_CONFIG[widgetType];
  const Icon = config.icon;
  const count = data?.count ?? 0;

  return (
    <WidgetWrapper
      title={config.title}
      colSpan={colSpan}
      rowSpan={rowSpan}
      editing={editing}
      onRemove={onRemove}
      onResize={onResize}
    >
      <div className="relative">
        {/* Gradient accent */}
        <div
          className="absolute inset-x-0 top-0 h-0.5 rounded-t"
          style={{
            background: `linear-gradient(90deg, ${config.accentFrom}, ${config.accentTo})`,
          }}
        />
        <div className="flex items-start justify-between pt-2">
          <div className="space-y-1">
            <p className="text-sm font-medium tracking-wide text-gray-500 dark:text-gray-400">
              {config.title}
            </p>
            <p className="text-3xl font-extrabold tracking-tight text-gray-900 dark:text-white">
              {count.toLocaleString()}
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              {config.subtitle}
            </p>
          </div>
          <div
            className={`flex h-10 w-10 items-center justify-center rounded-xl ${config.bg} shadow-sm`}
          >
            <Icon className={`h-5 w-5 ${config.color}`} />
          </div>
        </div>
      </div>
    </WidgetWrapper>
  );
}
