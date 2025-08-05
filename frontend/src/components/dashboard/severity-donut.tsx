"use client";

/**
 * SeverityDonut -- donut chart showing findings distribution by severity.
 * Clicking a segment navigates to /findings?severity=<level>.
 */

import { useRouter } from "next/navigation";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { ShieldAlert } from "lucide-react";
import { GlassCard, SectionHeader, ChartTooltip } from "./chart-section";

const SEVERITY_COLORS: Record<string, string> = {
  high: "#ef4444",
  medium: "#f59e0b",
  low: "#3b82f6",
};

const SEVERITY_LABELS: Record<string, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

interface SeverityDataPoint {
  severity: string;
  label: string;
  count: number;
  fill: string;
}

interface SeverityDonutProps {
  findingsBySeverity: Record<string, number>;
}

export default function SeverityDonut({
  findingsBySeverity,
}: SeverityDonutProps) {
  const router = useRouter();

  const data: SeverityDataPoint[] = Object.entries(findingsBySeverity).map(
    ([severity, count]) => ({
      severity,
      label: SEVERITY_LABELS[severity] ?? severity,
      count,
      fill: SEVERITY_COLORS[severity] ?? "#6b7280",
    }),
  );

  const totalFindings = data.reduce((sum, d) => sum + d.count, 0);

  if (data.length === 0) return null;

  const handleSegmentClick = (entry: SeverityDataPoint) => {
    router.push(`/findings?severity=${entry.severity}`);
  };

  const ariaLabel = `Findings by severity: ${data.map((d) => `${d.count} ${d.label.toLowerCase()}`).join(", ")}`;

  return (
    <GlassCard>
      <SectionHeader
        icon={<ShieldAlert className="h-5 w-5 text-indigo-500" />}
        title="Findings by Severity"
        subtitle="Click a segment to filter findings"
      />
      <div
        role="img"
        aria-label={ariaLabel}
        className="mt-4 flex justify-center"
      >
        <div className="w-40">
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie
                data={data}
                dataKey="count"
                nameKey="label"
                cx="50%"
                cy="50%"
                outerRadius={68}
                innerRadius={44}
                strokeWidth={0}
                paddingAngle={3}
                className="cursor-pointer"
              >
                {data.map((entry) => (
                  <Cell
                    key={entry.severity}
                    fill={entry.fill}
                    className="cursor-pointer transition-opacity duration-150 hover:opacity-80"
                    onClick={() => handleSegmentClick(entry)}
                  />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltip />} />
              <text
                x="50%"
                y="45%"
                textAnchor="middle"
                dominantBaseline="central"
                className="fill-gray-900 dark:fill-white"
                style={{ fontSize: "22px", fontWeight: 800 }}
              >
                {totalFindings.toLocaleString()}
              </text>
              <text
                x="50%"
                y="60%"
                textAnchor="middle"
                dominantBaseline="central"
                className="fill-gray-500 dark:fill-gray-400"
                style={{ fontSize: "9px", fontWeight: 500 }}
              >
                findings
              </text>
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
      <table className="sr-only" aria-label="Findings by severity">
        <thead>
          <tr>
            <th>Severity</th>
            <th>Count</th>
          </tr>
        </thead>
        <tbody>
          {data.map((entry) => (
            <tr key={entry.severity}>
              <td>{entry.label}</td>
              <td>{entry.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {/* Legend -- each row is also clickable */}
      <div className="mt-3 space-y-2">
        {data.map((entry) => {
          const pct =
            totalFindings > 0
              ? Math.round((entry.count / totalFindings) * 100)
              : 0;
          return (
            <button
              type="button"
              key={entry.severity}
              onClick={() => handleSegmentClick(entry)}
              className="flex w-full items-center gap-2 rounded-lg px-1 py-0.5 transition-colors duration-150 hover:bg-gray-100 dark:hover:bg-gray-700/50 cursor-pointer"
            >
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: entry.fill }}
              />
              <span className="min-w-0 flex-1 truncate text-left text-xs font-medium capitalize text-gray-600 dark:text-gray-300">
                {entry.label}
              </span>
              <span className="shrink-0 text-xs font-bold tabular-nums text-gray-900 dark:text-white">
                {entry.count}
              </span>
              <span className="shrink-0 w-8 text-right text-[10px] tabular-nums text-gray-500">
                {pct}%
              </span>
            </button>
          );
        })}
      </div>
    </GlassCard>
  );
}
