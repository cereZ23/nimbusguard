"use client";

/**
 * KpiCard -- stat card with gradient accent, icon, optional trend indicator
 * and glassmorphism styling. Used in the dashboard hero row.
 */

import { TrendingUp, TrendingDown, Minus } from "lucide-react";

export interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  trend?: "up" | "down" | "flat";
  trendValue?: string;
  accentFrom: string;
  accentTo: string;
  iconBg: string;
}

export default function KpiCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  trendValue,
  accentFrom,
  accentTo,
  iconBg,
}: KpiCardProps) {
  return (
    <div className="group relative min-w-0 overflow-hidden rounded-2xl border border-gray-200/80 bg-white/70 p-4 shadow-lg backdrop-blur-sm transition-all duration-300 hover:shadow-xl hover:-translate-y-0.5 dark:border-gray-700/60 dark:bg-gray-800/70 xl:p-5">
      {/* Gradient top accent line */}
      <div
        className="absolute inset-x-0 top-0 h-1 rounded-t-2xl"
        style={{
          background: `linear-gradient(90deg, ${accentFrom}, ${accentTo})`,
        }}
      />

      {/* Subtle background glow */}
      <div
        className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full opacity-[0.07] blur-2xl transition-opacity duration-300 group-hover:opacity-[0.12]"
        style={{ background: accentFrom }}
      />

      <div className="relative flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium tracking-wide text-gray-500 dark:text-gray-400">
            {title}
          </p>
          <p className="text-3xl font-extrabold tracking-tight text-gray-900 dark:text-white">
            {value}
          </p>
          <div className="flex items-center gap-2">
            {subtitle && (
              <p className="text-xs text-gray-400 dark:text-gray-500">
                {subtitle}
              </p>
            )}
            {trend && trendValue && (
              <span
                className={`inline-flex items-center gap-0.5 text-xs font-semibold ${
                  trend === "up"
                    ? "text-red-500"
                    : trend === "down"
                      ? "text-green-500"
                      : "text-gray-400"
                }`}
              >
                {trend === "up" ? (
                  <TrendingUp className="h-3 w-3" />
                ) : trend === "down" ? (
                  <TrendingDown className="h-3 w-3" />
                ) : (
                  <Minus className="h-3 w-3" />
                )}
                {trendValue}
              </span>
            )}
          </div>
        </div>

        <div
          className={`flex h-12 w-12 items-center justify-center rounded-xl ${iconBg} shadow-sm transition-transform duration-300 group-hover:scale-110`}
        >
          {icon}
        </div>
      </div>
    </div>
  );
}
