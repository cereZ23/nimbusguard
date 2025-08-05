"use client";

/**
 * ComplianceTrendChart -- line chart showing compliance score over time.
 */

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { ComplianceTrendPoint } from "@/types";

interface ComplianceTrendChartProps {
  data: ComplianceTrendPoint[];
  framework: string;
  period: string;
}

const FRAMEWORK_LABELS: Record<string, string> = {
  cis_azure: "CIS Azure",
  soc2: "SOC 2",
  nist: "NIST 800-53",
  iso27001: "ISO 27001",
};

function TrendTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{
    name: string;
    value: number;
    color: string;
    payload?: Record<string, unknown>;
  }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload as ComplianceTrendPoint | undefined;
  if (!point) return null;

  return (
    <div className="rounded-xl border border-gray-200/80 bg-white/95 px-4 py-3 shadow-xl backdrop-blur-sm dark:border-gray-700/80 dark:bg-gray-800/95">
      {label && (
        <p className="mb-2 text-xs font-medium text-gray-500 dark:text-gray-400">
          {label}
        </p>
      )}
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <span className="h-2.5 w-2.5 rounded-full bg-indigo-500" />
          <span className="text-gray-600 dark:text-gray-300">Score:</span>
          <span className="text-gray-900 dark:text-white">{point.score}%</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="h-2.5 w-2.5 rounded-full bg-green-500" />
          <span className="text-gray-600 dark:text-gray-300">Passing:</span>
          <span className="text-gray-900 dark:text-white">{point.passing}</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
          <span className="text-gray-600 dark:text-gray-300">Failing:</span>
          <span className="text-gray-900 dark:text-white">{point.failing}</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="h-2.5 w-2.5 rounded-full bg-gray-400" />
          <span className="text-gray-600 dark:text-gray-300">Total:</span>
          <span className="text-gray-900 dark:text-white">{point.total}</span>
        </div>
      </div>
    </div>
  );
}

export default function ComplianceTrendChart({
  data,
  framework,
  period,
}: ComplianceTrendChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex h-[280px] items-center justify-center">
        <p className="text-sm text-gray-400 dark:text-gray-500">
          No compliance trend data yet. Run scans to start tracking your score
          over time.
        </p>
      </div>
    );
  }

  const frameworkLabel = FRAMEWORK_LABELS[framework] ?? framework;

  // Calculate score change
  const firstScore = data[0].score;
  const lastScore = data[data.length - 1].score;
  const scoreDiff = lastScore - firstScore;

  return (
    <div>
      {/* Summary stats */}
      <div className="mb-4 flex items-center gap-6">
        <div>
          <span className="text-2xl font-bold text-gray-900 dark:text-white">
            {lastScore}%
          </span>
          <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">
            current
          </span>
        </div>
        {data.length > 1 && (
          <div
            className={`flex items-center gap-1 text-sm font-medium ${
              scoreDiff > 0
                ? "text-green-600 dark:text-green-400"
                : scoreDiff < 0
                  ? "text-red-600 dark:text-red-400"
                  : "text-gray-500 dark:text-gray-400"
            }`}
          >
            {scoreDiff > 0 ? (
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25"
                />
              </svg>
            ) : scoreDiff < 0 ? (
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4.5 4.5l15 15m0 0V8.25m0 11.25H8.25"
                />
              </svg>
            ) : null}
            {scoreDiff > 0 ? "+" : ""}
            {scoreDiff.toFixed(1)}%
          </div>
        )}
      </div>

      {/* Chart */}
      <div
        role="img"
        aria-label={`${frameworkLabel} compliance trend over ${period}`}
      >
        <ResponsiveContainer width="100%" height={220}>
          <LineChart
            data={data}
            margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
          >
            <defs>
              <linearGradient id="gradScore" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6366f1" stopOpacity={0.15} />
                <stop offset="100%" stopColor="#6366f1" stopOpacity={0.02} />
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
              domain={[0, 100]}
              tick={{ fontSize: 11 }}
              tickFormatter={(v: number) => `${v}%`}
              stroke="currentColor"
              className="text-gray-400 dark:text-gray-500"
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<TrendTooltip />} />
            <ReferenceLine
              y={80}
              stroke="#22c55e"
              strokeDasharray="4 4"
              opacity={0.5}
            />
            <Line
              type="monotone"
              dataKey="score"
              stroke="#6366f1"
              strokeWidth={2.5}
              dot={false}
              activeDot={{
                r: 5,
                strokeWidth: 2,
                fill: "#fff",
                stroke: "#6366f1",
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="mt-3 flex items-center justify-center gap-6">
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-indigo-500" />
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
            Compliance Score
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 border-t-2 border-dashed border-green-500" />
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
            80% Target
          </span>
        </div>
      </div>

      {/* Accessible data table */}
      <table
        className="sr-only"
        aria-label={`${frameworkLabel} compliance trend data`}
      >
        <thead>
          <tr>
            <th>Date</th>
            <th>Score</th>
            <th>Passing</th>
            <th>Failing</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {data.map((point) => (
            <tr key={point.date}>
              <td>{point.date}</td>
              <td>{point.score}%</td>
              <td>{point.passing}</td>
              <td>{point.failing}</td>
              <td>{point.total}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
