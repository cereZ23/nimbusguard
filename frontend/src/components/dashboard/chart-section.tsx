"use client";

/**
 * Shared layout primitives for dashboard chart areas:
 *
 *   GlassCard    -- glassmorphism container (rounded, blurred, bordered)
 *   SectionHeader -- icon + title + optional subtitle + optional action slot
 *   ChartTooltip  -- styled tooltip for Recharts charts
 */

// ---------------------------------------------------------------------------
// GlassCard
// ---------------------------------------------------------------------------

export function GlassCard({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl border border-gray-200/80 bg-white/70 p-6 shadow-lg backdrop-blur-sm dark:border-gray-700/60 dark:bg-gray-800/70 ${className}`}
    >
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SectionHeader
// ---------------------------------------------------------------------------

export function SectionHeader({
  icon,
  title,
  subtitle,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 dark:bg-indigo-900/30">
          {icon}
        </div>
        <div>
          <h2 className="text-lg font-bold text-gray-900 dark:text-white">
            {title}
          </h2>
          {subtitle && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {subtitle}
            </p>
          )}
        </div>
      </div>
      {action}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ChartTooltip  (for Recharts <Tooltip content={...} />)
// ---------------------------------------------------------------------------

export function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-gray-200/80 bg-white/95 px-4 py-3 shadow-xl backdrop-blur-sm dark:border-gray-700/80 dark:bg-gray-800/95">
      {label && (
        <p className="mb-1.5 text-xs font-medium text-gray-500 dark:text-gray-400">
          {label}
        </p>
      )}
      {payload.map((entry) => (
        <div
          key={entry.name}
          className="flex items-center gap-2 text-sm font-semibold"
        >
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="capitalize text-gray-600 dark:text-gray-300">
            {entry.name}:
          </span>
          <span className="text-gray-900 dark:text-white">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}
