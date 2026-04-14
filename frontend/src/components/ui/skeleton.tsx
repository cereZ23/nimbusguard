/**
 * Reusable skeleton loader components for shimmer/loading states.
 *
 * Usage:
 *   <Skeleton className="h-4 w-32" />           // text line
 *   <Skeleton className="h-8 w-8 rounded-full" /> // avatar
 *   <TableSkeleton rows={5} cols={4} />          // table placeholder
 *   <CardSkeleton />                             // KPI card placeholder
 *   <ChartSkeleton />                            // chart placeholder
 */

// Column width patterns for realistic-looking table skeletons.
// Each row cycles through different widths to avoid a uniform grid.
const COL_WIDTHS = ["w-3/4", "w-1/2", "w-2/3", "w-5/6", "w-2/5", "w-3/5"];

function Skeleton({
  className,
  style,
}: {
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={`animate-pulse rounded bg-gray-200 dark:bg-gray-700 ${className ?? ""}`}
      style={style}
    />
  );
}

function TableSkeleton({
  rows = 5,
  cols = 4,
}: {
  rows?: number;
  cols?: number;
}) {
  return (
    <div className="w-full">
      {/* Header row */}
      <div className="flex items-center gap-4 border-b border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/50">
        {Array.from({ length: cols }).map((_, colIdx) => (
          <Skeleton key={`header-${colIdx}`} className="h-3 flex-1" />
        ))}
      </div>

      {/* Body rows */}
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <div
          key={`row-${rowIdx}`}
          className={`flex items-center gap-4 border-b border-gray-100 px-4 py-3.5 dark:border-gray-700 ${
            rowIdx % 2 === 1 ? "bg-gray-50/50 dark:bg-gray-800/50" : ""
          }`}
        >
          {Array.from({ length: cols }).map((_, colIdx) => (
            <Skeleton
              key={`cell-${rowIdx}-${colIdx}`}
              className={`h-3.5 flex-1 ${COL_WIDTHS[(rowIdx + colIdx) % COL_WIDTHS.length]}`}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

function CardSkeleton() {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-8 rounded-lg" />
      </div>
      <Skeleton className="mt-4 h-8 w-20" />
      <Skeleton className="mt-2 h-3 w-32" />
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <Skeleton className="h-4 w-36 mb-4" />
      <div className="flex items-end gap-2 h-48">
        {[40, 65, 45, 80, 55, 70, 50, 75, 60, 85, 48, 72].map((height, idx) => (
          <Skeleton
            key={`bar-${idx}`}
            className="flex-1 rounded-t"
            style={{ height: `${height}%` }}
          />
        ))}
      </div>
      <div className="mt-3 flex justify-between">
        <Skeleton className="h-3 w-12" />
        <Skeleton className="h-3 w-12" />
        <Skeleton className="h-3 w-12" />
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* 4 KPI cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>

      {/* 2 charts side by side */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ChartSkeleton />
        <ChartSkeleton />
      </div>

      {/* Table skeleton below */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
        <TableSkeleton rows={5} cols={4} />
      </div>
    </div>
  );
}

function AssetDetailSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div>
        <Skeleton className="h-4 w-28 mb-4" />
        <Skeleton className="h-7 w-64" />
        <Skeleton className="mt-2 h-4 w-96" />
      </div>

      {/* 4 info cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, idx) => (
          <div
            key={`info-card-${idx}`}
            className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800"
          >
            <Skeleton className="h-3.5 w-16 mb-2" />
            <Skeleton className="h-5 w-24" />
          </div>
        ))}
      </div>

      {/* Table skeleton */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
        <TableSkeleton rows={5} cols={4} />
      </div>
    </div>
  );
}

export {
  Skeleton,
  TableSkeleton,
  CardSkeleton,
  ChartSkeleton,
  DashboardSkeleton,
  AssetDetailSkeleton,
};
