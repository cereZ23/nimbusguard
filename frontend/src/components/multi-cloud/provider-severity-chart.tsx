"use client";

/**
 * ProviderSeverityChart -- stacked bar chart comparing findings by severity
 * per cloud provider. Uses Recharts BarChart with stacked bars.
 */

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { BarChart3 } from "lucide-react";
import { GlassCard, SectionHeader, ChartTooltip } from "@/components/dashboard";
import type { ProviderSummary } from "@/types";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#dc2626",
  high: "#ef4444",
  medium: "#f59e0b",
  low: "#3b82f6",
};

interface ProviderSeverityChartProps {
  providers: ProviderSummary[];
}

export default function ProviderSeverityChart({
  providers,
}: ProviderSeverityChartProps) {
  // Transform data for Recharts: one object per provider
  const chartData = providers.map((p) => ({
    name: p.display_name,
    critical: p.findings_by_severity.critical ?? 0,
    high: p.findings_by_severity.high ?? 0,
    medium: p.findings_by_severity.medium ?? 0,
    low: p.findings_by_severity.low ?? 0,
  }));

  // Determine which severities have data
  const hasCritical = chartData.some((d) => d.critical > 0);
  const hasHigh = chartData.some((d) => d.high > 0);
  const hasMedium = chartData.some((d) => d.medium > 0);
  const hasLow = chartData.some((d) => d.low > 0);
  const hasAnyData = hasCritical || hasHigh || hasMedium || hasLow;

  if (!hasAnyData) {
    return (
      <GlassCard>
        <SectionHeader
          icon={<BarChart3 className="h-5 w-5 text-indigo-500" />}
          title="Findings by Severity"
          subtitle="Per-provider breakdown"
        />
        <div className="mt-4 flex h-[200px] items-center justify-center text-sm text-gray-400 dark:text-gray-500">
          No findings data available
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard>
      <SectionHeader
        icon={<BarChart3 className="h-5 w-5 text-indigo-500" />}
        title="Findings by Severity"
        subtitle="Stacked comparison across providers"
      />
      <div className="mt-4" style={{ height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 5, right: 5, left: -10, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
              stroke="currentColor"
              className="text-gray-200 dark:text-gray-700"
            />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 12 }}
              className="text-gray-600 dark:text-gray-400"
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              className="text-gray-500 dark:text-gray-400"
              axisLine={false}
              tickLine={false}
              allowDecimals={false}
            />
            <Tooltip content={<ChartTooltip />} />
            <Legend
              iconType="circle"
              iconSize={8}
              wrapperStyle={{ fontSize: "12px", paddingTop: 8 }}
            />
            {hasCritical && (
              <Bar
                dataKey="critical"
                stackId="severity"
                fill={SEVERITY_COLORS.critical}
                radius={[0, 0, 0, 0]}
                name="Critical"
              />
            )}
            {hasHigh && (
              <Bar
                dataKey="high"
                stackId="severity"
                fill={SEVERITY_COLORS.high}
                name="High"
              />
            )}
            {hasMedium && (
              <Bar
                dataKey="medium"
                stackId="severity"
                fill={SEVERITY_COLORS.medium}
                name="Medium"
              />
            )}
            {hasLow && (
              <Bar
                dataKey="low"
                stackId="severity"
                fill={SEVERITY_COLORS.low}
                radius={[4, 4, 0, 0]}
                name="Low"
              />
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </GlassCard>
  );
}
