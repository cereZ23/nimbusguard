"use client";

/**
 * FindingTrend -- stacked area chart showing 30-day severity trend.
 */

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Activity } from "lucide-react";
import { GlassCard, SectionHeader, ChartTooltip } from "./chart-section";
import type { TrendPoint } from "@/types";

const PERIOD_LABELS: Record<string, string> = {
  "7d": "7-day",
  "14d": "14-day",
  "30d": "30-day",
  "90d": "90-day",
};

interface FindingTrendProps {
  data: TrendPoint[];
  period?: string;
}

export default function FindingTrend({
  data,
  period = "30d",
}: FindingTrendProps) {
  if (data.length === 0) return null;

  const periodLabel = PERIOD_LABELS[period] ?? period;

  const latestPoint = data[data.length - 1];
  const trendAriaLabel = `Finding trend over ${periodLabel}: latest data point has ${latestPoint?.high ?? 0} high, ${latestPoint?.medium ?? 0} medium, ${latestPoint?.low ?? 0} low findings`;

  return (
    <GlassCard>
      <SectionHeader
        icon={<Activity className="h-5 w-5 text-indigo-500" />}
        title="Finding Trend"
        subtitle={`${periodLabel} severity distribution`}
      />
      <div role="img" aria-label={trendAriaLabel} className="mt-6">
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart
            data={data}
            margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
          >
            <defs>
              <linearGradient id="gradHigh" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ef4444" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#ef4444" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="gradMedium" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="gradLow" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="currentColor"
              className="text-gray-200 dark:text-gray-700"
              opacity={0.5}
            />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickFormatter={(v: string) => v.slice(5)}
              stroke="currentColor"
              className="text-gray-400 dark:text-gray-500"
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              stroke="currentColor"
              className="text-gray-400 dark:text-gray-500"
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<ChartTooltip />} />
            <Area
              type="monotone"
              dataKey="high"
              stroke="#ef4444"
              strokeWidth={2.5}
              fill="url(#gradHigh)"
              dot={false}
              activeDot={{
                r: 4,
                strokeWidth: 2,
                fill: "#fff",
                stroke: "#ef4444",
              }}
            />
            <Area
              type="monotone"
              dataKey="medium"
              stroke="#f59e0b"
              strokeWidth={2}
              fill="url(#gradMedium)"
              dot={false}
              activeDot={{
                r: 4,
                strokeWidth: 2,
                fill: "#fff",
                stroke: "#f59e0b",
              }}
            />
            <Area
              type="monotone"
              dataKey="low"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#gradLow)"
              dot={false}
              activeDot={{
                r: 4,
                strokeWidth: 2,
                fill: "#fff",
                stroke: "#3b82f6",
              }}
            />
          </AreaChart>
        </ResponsiveContainer>

        {/* Inline legend */}
        <div className="mt-4 flex items-center justify-center gap-6">
          {[
            { label: "High", color: "#ef4444" },
            { label: "Medium", color: "#f59e0b" },
            { label: "Low", color: "#3b82f6" },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-1.5">
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>
      <table className="sr-only" aria-label="Finding trend data">
        <thead>
          <tr>
            <th>Date</th>
            <th>High</th>
            <th>Medium</th>
            <th>Low</th>
          </tr>
        </thead>
        <tbody>
          {data.map((point) => (
            <tr key={point.date}>
              <td>{point.date}</td>
              <td>{point.high}</td>
              <td>{point.medium}</td>
              <td>{point.low}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </GlassCard>
  );
}
