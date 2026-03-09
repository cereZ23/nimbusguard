"use client";

import { useState, useMemo, useEffect } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import {
  Shield,
  Server,
  AlertTriangle,
  AlertOctagon,
  Clock,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import ErrorState from "@/components/ui/error-state";
import { DashboardSkeleton } from "@/components/ui/skeleton";
import {
  SecureScoreGauge,
  KpiCard,
  GlassCard,
  TopFailingControls,
  RecentFindings,
  TimeRangeSelector,
  AccountBreakdown,
} from "@/components/dashboard";

// Lazy load Recharts-heavy components to reduce initial bundle size (~160KB)
const SeverityDonut = dynamic(
  () => import("@/components/dashboard/severity-donut"),
  {
    ssr: false,
    loading: () => (
      <div className="h-[300px] animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
    ),
  },
);

const FindingTrend = dynamic(
  () => import("@/components/dashboard/finding-trend"),
  {
    ssr: false,
    loading: () => (
      <div className="h-[300px] animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
    ),
  },
);

const AssetsByTypeChart = dynamic(
  () => import("@/components/dashboard/assets-by-type-chart"),
  {
    ssr: false,
    loading: () => (
      <div className="h-[350px] animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
    ),
  },
);
import type {
  CloudAccount,
  DashboardSummary,
  Finding,
  TimeRange,
  TrendPoint,
  TrendResponse,
} from "@/types";

// ---------------------------------------------------------------------------
// Main Dashboard Page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const router = useRouter();
  const [timeRange, setTimeRange] = useState<TimeRange>("30d");

  // -- SWR: dashboard summary --
  const {
    data: summaryEnvelope,
    error: summaryError,
    isLoading: summaryLoading,
    mutate: mutateSummary,
  } = useSWR("/dashboard/summary");

  // -- SWR: findings trend (re-fetches when timeRange changes) --
  const {
    data: trendEnvelope,
    error: trendError,
    isLoading: trendLoading,
  } = useSWR(`/dashboard/trend?period=${timeRange}`);

  // -- SWR: recent findings --
  const {
    data: findingsEnvelope,
    error: findingsError,
    isLoading: findingsLoading,
  } = useSWR("/findings?size=5&sort_by=first_detected_at&sort_order=desc");

  // -- SWR: accounts --
  const { data: accountsEnvelope, isLoading: accountsLoading } =
    useSWR("/accounts?size=50");

  // Unwrap API envelope data
  const summary = (summaryEnvelope?.data ?? null) as DashboardSummary | null;
  const trendResponse = (trendEnvelope?.data ?? null) as TrendResponse | null;
  const trendData: TrendPoint[] = trendResponse?.data ?? [];
  const recentFindings = (findingsEnvelope?.data ?? []) as Finding[];
  const accounts = (accountsEnvelope?.data ?? []) as CloudAccount[];

  // Redirect to onboarding if user has no cloud accounts
  useEffect(() => {
    if (!accountsLoading && accountsEnvelope && accounts.length === 0) {
      router.push("/onboarding");
    }
  }, [accountsLoading, accountsEnvelope, accounts.length, router]);

  // Combined loading / error state for initial page load
  const isLoading = summaryLoading || trendLoading || findingsLoading;
  const error =
    summaryError?.message ??
    trendError?.message ??
    findingsError?.message ??
    summaryEnvelope?.error ??
    trendEnvelope?.error ??
    findingsEnvelope?.error ??
    null;

  // Derive a "last updated" timestamp from when SWR data arrived
  const lastUpdated = useMemo(() => {
    if (isLoading || !summary) return "";
    return new Date().toLocaleTimeString();
    // Re-compute when summary reference changes (i.e. fresh data arrived)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [summary, isLoading]);

  const handleTimeRangeChange = (newRange: TimeRange) => {
    setTimeRange(newRange);
    // SWR key changes automatically since it depends on timeRange state
  };

  const handleRetry = () => {
    mutateSummary();
  };

  // Compute a simple "trend" for high-severity findings
  // (compare first half vs second half of the 30-day window)
  const highTrend = useMemo(() => {
    if (trendData.length < 4) return { direction: "flat" as const, label: "" };
    const mid = Math.floor(trendData.length / 2);
    const firstHalf = trendData.slice(0, mid);
    const secondHalf = trendData.slice(mid);
    const avg1 = firstHalf.reduce((s, p) => s + p.high, 0) / firstHalf.length;
    const avg2 = secondHalf.reduce((s, p) => s + p.high, 0) / secondHalf.length;
    const diff = avg2 - avg1;
    if (Math.abs(diff) < 0.5)
      return { direction: "flat" as const, label: "Stable" };
    if (diff > 0)
      return {
        direction: "up" as const,
        label: `+${Math.round(diff)} avg`,
      };
    return {
      direction: "down" as const,
      label: `${Math.round(diff)} avg`,
    };
  }, [trendData]);

  return (
    <AppShell>
      <div className="animate-page-in space-y-8">
        {/* Page Header */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-gray-900 dark:text-white">
              Security Dashboard
            </h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Real-time overview of your cloud security posture
            </p>
          </div>
          <div className="flex items-center gap-4">
            <TimeRangeSelector
              value={timeRange}
              onChange={handleTimeRangeChange}
            />
            <div className="flex items-center gap-2 text-xs text-gray-400 dark:text-gray-500">
              <Clock className="h-3.5 w-3.5" />
              Last updated: {lastUpdated || "\u2014"}
            </div>
          </div>
        </div>

        {/* Loading State */}
        {isLoading ? (
          <DashboardSkeleton />
        ) : error ? (
          <ErrorState message={error} onRetry={handleRetry} />
        ) : summary ? (
          <>
            {/* Hero: KPI Cards row */}
            <div
              data-tour="kpi-cards"
              className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
            >
              <KpiCard
                title="Secure Score"
                value={
                  summary.secure_score != null
                    ? `${summary.secure_score}%`
                    : "N/A"
                }
                subtitle="Overall compliance"
                icon={
                  <Shield className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
                }
                accentFrom="#6366f1"
                accentTo="#818cf8"
                iconBg="bg-indigo-100 dark:bg-indigo-900/40"
              />
              <KpiCard
                title="Total Assets"
                value={summary.total_assets.toLocaleString()}
                subtitle="Across all accounts"
                icon={
                  <Server className="h-6 w-6 text-violet-600 dark:text-violet-400" />
                }
                accentFrom="#7c3aed"
                accentTo="#a78bfa"
                iconBg="bg-violet-100 dark:bg-violet-900/40"
              />
              <KpiCard
                title="Total Findings"
                value={summary.total_findings.toLocaleString()}
                subtitle="Open issues"
                icon={
                  <AlertTriangle className="h-6 w-6 text-amber-600 dark:text-amber-400" />
                }
                trend={highTrend.direction}
                trendValue={highTrend.label}
                accentFrom="#f59e0b"
                accentTo="#fbbf24"
                iconBg="bg-amber-100 dark:bg-amber-900/40"
              />
              <KpiCard
                title="High Severity"
                value={(
                  summary.findings_by_severity?.high ?? 0
                ).toLocaleString()}
                subtitle="Requires immediate attention"
                icon={
                  <AlertOctagon className="h-6 w-6 text-red-600 dark:text-red-400" />
                }
                accentFrom="#ef4444"
                accentTo="#f87171"
                iconBg="bg-red-100 dark:bg-red-900/40"
              />
            </div>

            {/* Charts Row: Gauge + Donut + Trend */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              {/* Secure Score Gauge */}
              <div data-tour="secure-score">
                <GlassCard className="flex flex-col items-center justify-center">
                  <div className="mb-2 flex items-center gap-2">
                    <Shield className="h-5 w-5 text-indigo-500" />
                    <h2 className="text-sm font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                      Secure Score
                    </h2>
                  </div>
                  <SecureScoreGauge score={summary.secure_score} />
                  <p className="mt-1 text-center text-xs text-gray-400 dark:text-gray-500">
                    Based on{" "}
                    {summary.top_failing_controls.length > 0
                      ? `${summary.top_failing_controls.length}+ controls`
                      : "all controls"}{" "}
                    across your cloud accounts
                  </p>
                </GlassCard>
              </div>

              {/* Severity Donut (click-through to /findings?severity=...) */}
              <div data-tour="severity-donut">
                <SeverityDonut
                  findingsBySeverity={summary.findings_by_severity}
                />
              </div>

              {/* Trend Area Chart */}
              <div data-tour="trend-chart">
                <FindingTrend data={trendData} period={timeRange} />
              </div>
            </div>

            {/* Account-Level Breakdown */}
            <AccountBreakdown accounts={accounts} isLoading={accountsLoading} />

            {/* Assets by Type (click-through to /assets?resource_type=...) */}
            <AssetsByTypeChart
              assetsByType={summary.assets_by_type}
              totalAssets={summary.total_assets}
            />

            {/* Top Failing Controls (click-through to /findings?control_id=...) */}
            <div data-tour="top-controls">
              <TopFailingControls controls={summary.top_failing_controls} />
            </div>

            {/* Recent Findings */}
            <RecentFindings findings={recentFindings} />
          </>
        ) : (
          /* Empty state */
          <div className="flex h-96 flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-gray-300 bg-white/50 dark:border-gray-700 dark:bg-gray-800/50">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-50 dark:bg-indigo-900/30">
              <Shield className="h-8 w-8 text-indigo-400" />
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-gray-600 dark:text-gray-300">
                No data available
              </p>
              <p className="mt-1 max-w-sm text-sm text-gray-400 dark:text-gray-500">
                Connect a cloud account and run your first security scan to see
                results here.
              </p>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
