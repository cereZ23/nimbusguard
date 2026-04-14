"use client";

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
import { ChartTooltip } from "@/components/dashboard/chart-section";
import WidgetWrapper from "./widget-wrapper";

interface TrendDataPoint {
  date: string;
  high: number;
  medium: number;
  low: number;
}

interface TrendWidgetProps {
  data: TrendDataPoint[] | null;
  colSpan?: number;
  rowSpan?: number;
  editing?: boolean;
  onRemove?: () => void;
  onResize?: (larger: boolean) => void;
}

export default function TrendWidget({
  data,
  colSpan,
  rowSpan,
  editing,
  onRemove,
  onResize,
}: TrendWidgetProps) {
  const points = data ?? [];

  return (
    <WidgetWrapper
      title="Findings Trend"
      colSpan={colSpan}
      rowSpan={rowSpan}
      editing={editing}
      onRemove={onRemove}
      onResize={onResize}
    >
      <div className="flex items-center gap-2 mb-3">
        <Activity className="h-4 w-4 text-indigo-500" />
        <span className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Findings Trend
        </span>
      </div>
      {points.length === 0 ? (
        <p className="py-8 text-center text-sm text-gray-400">
          No trend data available
        </p>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart
              data={points}
              margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
            >
              <defs>
                <linearGradient id="cw-gradH" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#ef4444" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="cw-gradM" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="cw-gradL" x1="0" y1="0" x2="0" y2="1">
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
                tick={{ fontSize: 10 }}
                tickFormatter={(v: string) => v.slice(5)}
                stroke="currentColor"
                className="text-gray-400 dark:text-gray-500"
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fontSize: 10 }}
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
                strokeWidth={2}
                fill="url(#cw-gradH)"
                dot={false}
              />
              <Area
                type="monotone"
                dataKey="medium"
                stroke="#f59e0b"
                strokeWidth={1.5}
                fill="url(#cw-gradM)"
                dot={false}
              />
              <Area
                type="monotone"
                dataKey="low"
                stroke="#3b82f6"
                strokeWidth={1.5}
                fill="url(#cw-gradL)"
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
          <div className="mt-2 flex items-center justify-center gap-4">
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
                <span className="text-[10px] font-medium text-gray-500 dark:text-gray-400">
                  {item.label}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </WidgetWrapper>
  );
}
