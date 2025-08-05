"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import useSWR from "swr";
import {
  Cloud,
  Shield,
  Server,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowRight,
  BarChart3,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import ErrorState from "@/components/ui/error-state";
import { DashboardSkeleton } from "@/components/ui/skeleton";
import { GlassCard, SectionHeader } from "@/components/dashboard";
import type { CrossCloudSummary, ProviderSummary } from "@/types";

// Lazy load chart components to reduce initial bundle
const ProviderSeverityChart = dynamic(
  () => import("@/components/multi-cloud/provider-severity-chart"),
  {
    ssr: false,
    loading: () => (
      <div className="h-[350px] animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
    ),
  },
);

// ---------------------------------------------------------------------------
// Provider color and icon mappings
// ---------------------------------------------------------------------------

const PROVIDER_COLORS: Record<string, string> = {
  azure: "#0078d4",
  aws: "#ff9900",
  gcp: "#4285f4",
};

const PROVIDER_GRADIENTS: Record<string, { from: string; to: string }> = {
  azure: { from: "#0078d4", to: "#50b0ff" },
  aws: { from: "#ff9900", to: "#ffbf60" },
  gcp: { from: "#4285f4", to: "#82b1ff" },
};

const TREND_CONFIG: Record<
  string,
  { icon: typeof TrendingUp; label: string; color: string }
> = {
  improving: {
    icon: TrendingDown,
    label: "Improving",
    color: "text-green-500",
  },
  declining: { icon: TrendingUp, label: "Declining", color: "text-red-500" },
  stable: { icon: Minus, label: "Stable", color: "text-gray-400" },
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function OverallScoreCard({ score }: { score: number | null }) {
  const value = score ?? 0;
  const getColor = (v: number) => {
    if (v >= 80) return "text-green-500";
    if (v >= 50) return "text-amber-500";
    return "text-red-500";
  };
  const getLabel = (v: number) => {
    if (v >= 90) return "Excellent";
    if (v >= 80) return "Good";
    if (v >= 60) return "Fair";
    if (v >= 40) return "Needs Work";
    return "Critical";
  };

  return (
    <GlassCard className="flex flex-col items-center justify-center py-8">
      <div className="mb-3 flex items-center gap-2">
        <Shield className="h-5 w-5 text-indigo-500" />
        <h2 className="text-sm font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Overall Score
        </h2>
      </div>
      <div
        className={`text-5xl font-extrabold tracking-tight ${score != null ? getColor(value) : "text-gray-300 dark:text-gray-600"}`}
      >
        {score != null ? `${score}%` : "N/A"}
      </div>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
        {score != null ? getLabel(value) : "No data available"}
      </p>
      <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">
        Weighted average across all providers
      </p>
    </GlassCard>
  );
}

function TotalsSummaryCards({
  accounts,
  assets,
  findings,
  findings_by_severity,
}: {
  accounts: number;
  assets: number;
  findings: number;
  findings_by_severity: Record<string, number>;
}) {
  const criticalCount = findings_by_severity.critical ?? 0;
  const highCount = findings_by_severity.high ?? 0;

  return (
    <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
      <div className="rounded-xl border border-gray-200/80 bg-white/70 p-4 shadow-sm backdrop-blur-sm dark:border-gray-700/60 dark:bg-gray-800/70">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
          Accounts
        </p>
        <p className="mt-1 text-2xl font-extrabold text-gray-900 dark:text-white">
          {accounts}
        </p>
      </div>
      <div className="rounded-xl border border-gray-200/80 bg-white/70 p-4 shadow-sm backdrop-blur-sm dark:border-gray-700/60 dark:bg-gray-800/70">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
          Assets
        </p>
        <p className="mt-1 text-2xl font-extrabold text-gray-900 dark:text-white">
          {assets.toLocaleString()}
        </p>
      </div>
      <div className="rounded-xl border border-gray-200/80 bg-white/70 p-4 shadow-sm backdrop-blur-sm dark:border-gray-700/60 dark:bg-gray-800/70">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
          Findings
        </p>
        <p className="mt-1 text-2xl font-extrabold text-gray-900 dark:text-white">
          {findings.toLocaleString()}
        </p>
      </div>
      <div className="rounded-xl border border-gray-200/80 bg-white/70 p-4 shadow-sm backdrop-blur-sm dark:border-gray-700/60 dark:bg-gray-800/70">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
          Critical + High
        </p>
        <p className="mt-1 text-2xl font-extrabold text-red-600 dark:text-red-400">
          {(criticalCount + highCount).toLocaleString()}
        </p>
      </div>
    </div>
  );
}

function ProviderCard({ provider }: { provider: ProviderSummary }) {
  const gradient = PROVIDER_GRADIENTS[provider.provider] ?? {
    from: "#6366f1",
    to: "#818cf8",
  };
  const trendInfo = TREND_CONFIG[provider.trend] ?? TREND_CONFIG.stable;
  const TrendIcon = trendInfo.icon;

  const totalSeverity = Object.values(provider.findings_by_severity).reduce(
    (a, b) => a + b,
    0,
  );

  return (
    <GlassCard className="relative overflow-hidden">
      {/* Gradient top accent */}
      <div
        className="absolute inset-x-0 top-0 h-1 rounded-t-2xl"
        style={{
          background: `linear-gradient(90deg, ${gradient.from}, ${gradient.to})`,
        }}
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg"
            style={{
              backgroundColor: `${PROVIDER_COLORS[provider.provider] ?? "#6366f1"}15`,
            }}
          >
            <Cloud
              className="h-5 w-5"
              style={{ color: PROVIDER_COLORS[provider.provider] ?? "#6366f1" }}
            />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">
              {provider.display_name}
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {provider.accounts_count} account
              {provider.accounts_count !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
        <div
          className={`flex items-center gap-1 text-xs font-semibold ${trendInfo.color}`}
        >
          <TrendIcon className="h-3.5 w-3.5" />
          {trendInfo.label}
        </div>
      </div>

      {/* Score */}
      <div className="mt-5 flex items-baseline gap-2">
        <span className="text-3xl font-extrabold text-gray-900 dark:text-white">
          {provider.secure_score != null ? `${provider.secure_score}%` : "N/A"}
        </span>
        <span className="text-sm text-gray-500 dark:text-gray-400">
          secure score
        </span>
      </div>

      {/* Stats grid */}
      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/50">
          <div className="flex items-center gap-1.5">
            <Server className="h-3.5 w-3.5 text-gray-400" />
            <span className="text-xs text-gray-500 dark:text-gray-400">
              Assets
            </span>
          </div>
          <p className="mt-1 text-lg font-bold text-gray-900 dark:text-white">
            {provider.total_assets.toLocaleString()}
          </p>
        </div>
        <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/50">
          <div className="flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-gray-400" />
            <span className="text-xs text-gray-500 dark:text-gray-400">
              Findings
            </span>
          </div>
          <p className="mt-1 text-lg font-bold text-gray-900 dark:text-white">
            {provider.total_findings.toLocaleString()}
          </p>
        </div>
      </div>

      {/* Severity mini-bars */}
      {totalSeverity > 0 && (
        <div className="mt-4 space-y-1.5">
          {(["critical", "high", "medium", "low"] as const).map((sev) => {
            const count = provider.findings_by_severity[sev] ?? 0;
            if (count === 0) return null;
            const pct = Math.round((count / totalSeverity) * 100);
            const colors: Record<string, string> = {
              critical: "bg-red-600",
              high: "bg-red-400",
              medium: "bg-amber-400",
              low: "bg-blue-400",
            };
            return (
              <div key={sev} className="flex items-center gap-2">
                <span className="w-14 text-right text-[11px] font-medium capitalize text-gray-500 dark:text-gray-400">
                  {sev}
                </span>
                <div className="flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700">
                  <div
                    className={`h-1.5 rounded-full ${colors[sev]}`}
                    style={{ width: `${Math.max(pct, 2)}%` }}
                  />
                </div>
                <span className="w-8 text-right text-[11px] font-bold tabular-nums text-gray-700 dark:text-gray-300">
                  {count}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Link to drill-down */}
      <Link
        href="/dashboard"
        className="mt-4 flex items-center gap-1 text-sm font-medium text-indigo-600 transition-colors hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300"
      >
        View details
        <ArrowRight className="h-4 w-4" />
      </Link>
    </GlassCard>
  );
}

function ComparisonTable({ providers }: { providers: ProviderSummary[] }) {
  if (providers.length === 0) return null;

  return (
    <GlassCard>
      <SectionHeader
        icon={<BarChart3 className="h-5 w-5 text-indigo-500" />}
        title="Provider Comparison"
        subtitle="Side-by-side metrics across all connected providers"
      />
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              <th className="pb-3 text-left font-medium text-gray-500 dark:text-gray-400">
                Metric
              </th>
              {providers.map((p) => (
                <th
                  key={p.provider}
                  className="pb-3 text-right font-medium"
                  style={{ color: PROVIDER_COLORS[p.provider] ?? "#6366f1" }}
                >
                  {p.display_name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            <tr>
              <td className="py-3 text-gray-600 dark:text-gray-300">
                Accounts
              </td>
              {providers.map((p) => (
                <td
                  key={p.provider}
                  className="py-3 text-right font-semibold text-gray-900 dark:text-white"
                >
                  {p.accounts_count}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-3 text-gray-600 dark:text-gray-300">Assets</td>
              {providers.map((p) => (
                <td
                  key={p.provider}
                  className="py-3 text-right font-semibold text-gray-900 dark:text-white"
                >
                  {p.total_assets.toLocaleString()}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-3 text-gray-600 dark:text-gray-300">
                Findings
              </td>
              {providers.map((p) => (
                <td
                  key={p.provider}
                  className="py-3 text-right font-semibold text-gray-900 dark:text-white"
                >
                  {p.total_findings.toLocaleString()}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-3 text-gray-600 dark:text-gray-300">
                Critical
              </td>
              {providers.map((p) => (
                <td
                  key={p.provider}
                  className="py-3 text-right font-semibold text-red-600 dark:text-red-400"
                >
                  {p.findings_by_severity.critical ?? 0}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-3 text-gray-600 dark:text-gray-300">High</td>
              {providers.map((p) => (
                <td
                  key={p.provider}
                  className="py-3 text-right font-semibold text-red-500 dark:text-red-400"
                >
                  {p.findings_by_severity.high ?? 0}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-3 text-gray-600 dark:text-gray-300">Medium</td>
              {providers.map((p) => (
                <td
                  key={p.provider}
                  className="py-3 text-right font-semibold text-amber-500 dark:text-amber-400"
                >
                  {p.findings_by_severity.medium ?? 0}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-3 text-gray-600 dark:text-gray-300">Low</td>
              {providers.map((p) => (
                <td
                  key={p.provider}
                  className="py-3 text-right font-semibold text-blue-500 dark:text-blue-400"
                >
                  {p.findings_by_severity.low ?? 0}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-3 text-gray-600 dark:text-gray-300">
                Secure Score
              </td>
              {providers.map((p) => (
                <td
                  key={p.provider}
                  className="py-3 text-right font-bold text-gray-900 dark:text-white"
                >
                  {p.secure_score != null ? `${p.secure_score}%` : "N/A"}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-3 text-gray-600 dark:text-gray-300">Trend</td>
              {providers.map((p) => {
                const trendInfo = TREND_CONFIG[p.trend] ?? TREND_CONFIG.stable;
                const TrendIcon = trendInfo.icon;
                return (
                  <td key={p.provider} className="py-3 text-right">
                    <span
                      className={`inline-flex items-center gap-1 text-xs font-semibold ${trendInfo.color}`}
                    >
                      <TrendIcon className="h-3.5 w-3.5" />
                      {trendInfo.label}
                    </span>
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>
    </GlassCard>
  );
}

function ComparisonBanner({
  comparison,
  providers,
}: {
  comparison: CrossCloudSummary["comparison"];
  providers: ProviderSummary[];
}) {
  if (!comparison.best_provider || !comparison.worst_provider) return null;
  if (comparison.best_provider === comparison.worst_provider) return null;

  const bestName =
    providers.find((p) => p.provider === comparison.best_provider)
      ?.display_name ?? comparison.best_provider;
  const worstName =
    providers.find((p) => p.provider === comparison.worst_provider)
      ?.display_name ?? comparison.worst_provider;

  return (
    <div className="rounded-xl border border-indigo-200/60 bg-indigo-50/50 p-4 dark:border-indigo-800/40 dark:bg-indigo-950/30">
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-green-100 text-green-600 dark:bg-green-900/40 dark:text-green-400">
            <TrendingDown className="h-3.5 w-3.5" />
          </span>
          <span className="text-gray-600 dark:text-gray-300">
            <span className="font-semibold text-gray-900 dark:text-white">
              {bestName}
            </span>{" "}
            has the highest score
          </span>
        </div>
        <div className="hidden h-4 w-px bg-gray-300 dark:bg-gray-600 sm:block" />
        <div className="flex items-center gap-2">
          <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-amber-100 text-amber-600 dark:bg-amber-900/40 dark:text-amber-400">
            <TrendingUp className="h-3.5 w-3.5" />
          </span>
          <span className="text-gray-600 dark:text-gray-300">
            <span className="font-semibold text-gray-900 dark:text-white">
              {worstName}
            </span>{" "}
            needs attention
          </span>
        </div>
        <div className="hidden h-4 w-px bg-gray-300 dark:bg-gray-600 sm:block" />
        <div className="text-gray-600 dark:text-gray-300">
          Score gap:{" "}
          <span className="font-bold text-indigo-600 dark:text-indigo-400">
            {comparison.score_gap} pts
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function MultiCloudPage() {
  const {
    data: envelope,
    error: fetchError,
    isLoading,
    mutate,
  } = useSWR("/dashboard/cross-cloud");

  const summary = (envelope?.data ?? null) as CrossCloudSummary | null;

  const error = useMemo(() => {
    return fetchError?.message ?? envelope?.error ?? null;
  }, [fetchError, envelope]);

  const handleRetry = () => {
    mutate();
  };

  return (
    <AppShell>
      <div className="space-y-8">
        {/* Page Header */}
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-100 dark:bg-indigo-900/40">
              <Cloud className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
            </div>
            <div>
              <h1 className="text-3xl font-extrabold tracking-tight text-gray-900 dark:text-white">
                Multi-Cloud Overview
              </h1>
              <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
                Aggregated security posture across all connected cloud providers
              </p>
            </div>
          </div>
        </div>

        {/* Loading */}
        {isLoading ? (
          <DashboardSkeleton />
        ) : error ? (
          <ErrorState message={error} onRetry={handleRetry} />
        ) : summary && summary.providers.length > 0 ? (
          <>
            {/* Totals summary cards */}
            <TotalsSummaryCards
              accounts={summary.totals.accounts}
              assets={summary.totals.assets}
              findings={summary.totals.findings}
              findings_by_severity={summary.totals.findings_by_severity}
            />

            {/* Overall score + comparison banner */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <OverallScoreCard score={summary.totals.overall_score} />
              <div className="space-y-6 lg:col-span-2">
                <ComparisonBanner
                  comparison={summary.comparison}
                  providers={summary.providers}
                />
                {/* Stacked bar chart */}
                <ProviderSeverityChart providers={summary.providers} />
              </div>
            </div>

            {/* Provider cards */}
            <div>
              <SectionHeader
                icon={<Cloud className="h-5 w-5 text-indigo-500" />}
                title="Providers"
                subtitle={`${summary.providers.length} provider${summary.providers.length !== 1 ? "s" : ""} connected`}
              />
              <div
                className={`mt-4 grid gap-6 ${summary.providers.length === 1 ? "grid-cols-1 max-w-lg" : "grid-cols-1 md:grid-cols-2 xl:grid-cols-3"}`}
              >
                {summary.providers.map((p) => (
                  <ProviderCard key={p.provider} provider={p} />
                ))}
              </div>
            </div>

            {/* Comparison table */}
            {summary.providers.length > 1 && (
              <ComparisonTable providers={summary.providers} />
            )}
          </>
        ) : (
          /* Empty state */
          <div className="flex h-96 flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-gray-300 bg-white/50 dark:border-gray-700 dark:bg-gray-800/50">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-50 dark:bg-indigo-900/30">
              <Cloud className="h-8 w-8 text-indigo-400" />
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-gray-600 dark:text-gray-300">
                No cloud providers connected
              </p>
              <p className="mt-1 max-w-sm text-sm text-gray-400 dark:text-gray-500">
                Connect a cloud account to see your multi-cloud security posture
                overview.
              </p>
            </div>
            <Link
              href="/onboarding"
              className="mt-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-indigo-500"
            >
              Connect Account
            </Link>
          </div>
        )}
      </div>
    </AppShell>
  );
}
