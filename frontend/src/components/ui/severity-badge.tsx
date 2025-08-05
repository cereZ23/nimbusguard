import type { Severity } from "@/types";

const config: Record<
  Severity,
  { dot: string; bg: string; text: string; darkBg: string; darkText: string }
> = {
  high: {
    dot: "bg-red-500",
    bg: "bg-red-50",
    text: "text-red-700",
    darkBg: "dark:bg-red-900/30",
    darkText: "dark:text-red-400",
  },
  medium: {
    dot: "bg-amber-500",
    bg: "bg-amber-50",
    text: "text-amber-700",
    darkBg: "dark:bg-amber-900/30",
    darkText: "dark:text-amber-400",
  },
  low: {
    dot: "bg-blue-500",
    bg: "bg-blue-50",
    text: "text-blue-700",
    darkBg: "dark:bg-blue-900/30",
    darkText: "dark:text-blue-400",
  },
};

export default function SeverityBadge({
  severity,
}: {
  severity: Severity | string;
}) {
  const c = config[severity as Severity] ?? {
    dot: "bg-gray-400",
    bg: "bg-gray-100",
    text: "text-gray-600",
    darkBg: "dark:bg-gray-700",
    darkText: "dark:text-gray-300",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${c.bg} ${c.text} ${c.darkBg} ${c.darkText}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {severity}
    </span>
  );
}
