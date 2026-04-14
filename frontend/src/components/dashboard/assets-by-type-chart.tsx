"use client";

/**
 * AssetsByTypeChart -- horizontal bar chart showing resource counts per type.
 * Clicking a bar navigates to /assets?resource_type=<full_type>.
 */

import { useRouter } from "next/navigation";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Layers } from "lucide-react";
import { GlassCard, SectionHeader, ChartTooltip } from "./chart-section";

interface AssetTypeDataPoint {
  type: string;
  fullType: string;
  count: number;
}

interface AssetsByTypeChartProps {
  assetsByType: Record<string, number>;
  totalAssets: number;
}

export default function AssetsByTypeChart({
  assetsByType,
  totalAssets,
}: AssetsByTypeChartProps) {
  const router = useRouter();

  const data: AssetTypeDataPoint[] = Object.entries(assetsByType)
    .map(([type, count]) => {
      const shortType = type.split("/").pop() ?? type;
      return { type: shortType, fullType: type, count };
    })
    .sort((a, b) => b.count - a.count);

  if (data.length === 0) return null;

  const handleBarClick = (entry: AssetTypeDataPoint) => {
    router.push(`/assets?resource_type=${encodeURIComponent(entry.fullType)}`);
  };

  const assetsAriaLabel = `Assets by type: ${data.map((d) => `${d.count} ${d.type}`).join(", ")}`;

  return (
    <GlassCard>
      <SectionHeader
        icon={<Layers className="h-5 w-5 text-indigo-500" />}
        title="Assets by Type"
        subtitle={`${totalAssets.toLocaleString()} resources across ${data.length} types -- click a bar to filter`}
      />
      <div role="img" aria-label={assetsAriaLabel} className="mt-6">
        <ResponsiveContainer
          width="100%"
          height={Math.max(180, data.length * 40)}
        >
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 24, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="barGrad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#6366f1" stopOpacity={0.9} />
                <stop offset="100%" stopColor="#a78bfa" stopOpacity={0.9} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              horizontal={false}
              stroke="currentColor"
              className="text-gray-200 dark:text-gray-700"
              opacity={0.4}
            />
            <XAxis
              type="number"
              tick={{ fontSize: 11 }}
              stroke="currentColor"
              className="text-gray-400 dark:text-gray-500"
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              dataKey="type"
              type="category"
              width={160}
              tick={{ fontSize: 12 }}
              stroke="currentColor"
              className="text-gray-500 dark:text-gray-400"
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<ChartTooltip />} />
            <Bar
              dataKey="count"
              fill="url(#barGrad)"
              radius={[0, 8, 8, 0]}
              maxBarSize={28}
              className="cursor-pointer"
              onClick={(_data: Record<string, unknown>, index: number) => {
                if (data[index]) {
                  handleBarClick(data[index]);
                }
              }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only" aria-label="Assets by type">
        <thead>
          <tr>
            <th>Resource Type</th>
            <th>Count</th>
          </tr>
        </thead>
        <tbody>
          {data.map((entry) => (
            <tr key={entry.fullType}>
              <td>{entry.type}</td>
              <td>{entry.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </GlassCard>
  );
}
