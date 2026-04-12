import React from "react";
import type { Priority } from "@/types";

const config: Record<
  Priority,
  {
    dot: string;
    bg: string;
    text: string;
    darkBg: string;
    darkText: string;
    label: string;
    tooltip: string;
  }
> = {
  P0: {
    dot: "bg-red-500",
    bg: "bg-red-50",
    text: "text-red-700",
    darkBg: "dark:bg-red-900/50",
    darkText: "dark:text-red-400",
    label: "P0",
    tooltip: "Fix now — high severity, internet-exposed or quick fix",
  },
  P1: {
    dot: "bg-orange-500",
    bg: "bg-orange-50",
    text: "text-orange-700",
    darkBg: "dark:bg-orange-900/50",
    darkText: "dark:text-orange-400",
    label: "P1",
    tooltip: "Fix this week — structural hardening",
  },
  P2: {
    dot: "bg-amber-500",
    bg: "bg-amber-50",
    text: "text-amber-700",
    darkBg: "dark:bg-amber-900/50",
    darkText: "dark:text-amber-400",
    label: "P2",
    tooltip: "Fix this sprint — governance & resilience",
  },
  P3: {
    dot: "bg-green-500",
    bg: "bg-green-50",
    text: "text-green-700",
    darkBg: "dark:bg-green-900/50",
    darkText: "dark:text-green-400",
    label: "P3",
    tooltip: "Polish / best practice — when you have time",
  },
};

interface PriorityBadgeProps {
  value: Priority | null | undefined;
  /** If true, render as a dash placeholder when value is null. */
  placeholder?: boolean;
  /** Optional formula inputs — when provided the tooltip shows the
   *  specific reason this finding was bucketed as P0/P1/P2/P3. */
  severity?: string | null;
  effort?: string | null;
  exposure?: string | null;
}

function buildFormulaTooltip(
  value: Priority,
  severity?: string | null,
  effort?: string | null,
  exposure?: string | null,
): string {
  const base = config[value].tooltip;
  if (!severity) return base;
  const parts = [`Severity: ${severity}`];
  if (effort) parts.push(`Effort: ${effort}`);
  if (exposure) parts.push(`Exposure: ${exposure}`);
  const isExposed = exposure === "internet";
  const formula = parts.join(" · ");
  return isExposed
    ? `${formula} (internet-exposed bump) → ${value}\n${base}`
    : `${formula} → ${value}\n${base}`;
}

function PriorityBadge({
  value,
  placeholder = true,
  severity,
  effort,
  exposure,
}: PriorityBadgeProps) {
  if (!value) {
    if (!placeholder) return null;
    return (
      <span className="inline-flex items-center text-xs text-gray-400 dark:text-gray-600">
        &mdash;
      </span>
    );
  }
  const c = config[value];
  const tooltip = buildFormulaTooltip(value, severity, effort, exposure);
  return (
    <span
      title={tooltip}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${c.bg} ${c.text} ${c.darkBg} ${c.darkText}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
}

export default React.memo(PriorityBadge);
