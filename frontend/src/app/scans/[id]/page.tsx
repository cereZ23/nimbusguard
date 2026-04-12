"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  BarChart3,
  Clock,
  AlertTriangle,
  CheckCircle,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import PriorityBadge from "@/components/ui/priority-badge";
import ErrorState from "@/components/ui/error-state";
import api from "@/lib/api";
import { extractApiError } from "@/lib/errors";
import { formatDateTime } from "@/lib/dates";
import type { Priority } from "@/types";

interface ScanDetail {
  id: string;
  cloud_account_id: string;
  cloud_account_name: string | null;
  cloud_account_provider: string | null;
  scan_type: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  duration_seconds: number | null;
  findings_count: number | null;
  findings_fail_count: number | null;
  findings_pass_count: number | null;
  priority_breakdown: Record<string, number>;
  delta_new: number;
  delta_fixed: number;
  delta_unchanged: number;
  previous_scan_id: string | null;
}

const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  completed: {
    bg: "bg-green-100 dark:bg-green-900/30",
    text: "text-green-700 dark:text-green-400",
  },
  running: {
    bg: "bg-blue-100 dark:bg-blue-900/30",
    text: "text-blue-700 dark:text-blue-400",
  },
  pending: {
    bg: "bg-amber-100 dark:bg-amber-900/30",
    text: "text-amber-700 dark:text-amber-400",
  },
  failed: {
    bg: "bg-red-100 dark:bg-red-900/30",
    text: "text-red-700 dark:text-red-400",
  },
};

function formatDuration(seconds: number | null): string {
  if (seconds == null || seconds < 0) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function ScanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchScan = useCallback(() => {
    if (!id) return;
    setIsLoading(true);
    setError(null);

    api
      .get(`/scans/${id}`)
      .then((res) => setScan(res.data?.data as ScanDetail))
      .catch((err: unknown) => setError(extractApiError(err)))
      .finally(() => setIsLoading(false));
  }, [id]);

  useEffect(() => {
    fetchScan();
  }, [fetchScan]);

  if (isLoading) {
    return (
      <AppShell>
        <div className="flex h-96 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
        </div>
      </AppShell>
    );
  }

  if (error || !scan) {
    return (
      <AppShell>
        <ErrorState
          message={error ?? "Scan not found"}
          onRetry={error ? fetchScan : undefined}
        />
      </AppShell>
    );
  }

  const statusStyle = STATUS_STYLES[scan.status] ?? STATUS_STYLES.pending;
  const totalFail = scan.findings_fail_count ?? 0;
  const totalPass = scan.findings_pass_count ?? 0;
  const totalFindings = scan.findings_count ?? 0;
  const passPercent =
    totalFindings > 0 ? Math.round((totalPass / totalFindings) * 100) : 0;
  const failPercent = totalFindings > 0 ? 100 - passPercent : 0;
  const hasDelta = scan.previous_scan_id != null;
  const tiers: Priority[] = ["P0", "P1", "P2", "P3"];

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        {/* Back + header */}
        <div>
          <button
            onClick={() => router.push("/scans")}
            className="mb-3 flex items-center gap-1.5 text-sm text-gray-500 transition-colors hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Scans
          </button>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Scan Detail
            </h1>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase ${statusStyle.bg} ${statusStyle.text}`}
            >
              {scan.status}
            </span>
          </div>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {scan.cloud_account_name ?? "Unknown account"}
            {scan.cloud_account_provider && (
              <span className="ml-1.5 uppercase">
                ({scan.cloud_account_provider})
              </span>
            )}
            {" · "}
            {scan.started_at
              ? formatDateTime(scan.started_at)
              : formatDateTime(scan.created_at)}
            {scan.duration_seconds != null && (
              <span className="ml-1.5">
                · Duration: {formatDuration(scan.duration_seconds)}
              </span>
            )}
          </p>
        </div>

        {/* KPI cards row */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* Findings total */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
              Total Findings
            </div>
            <div className="mt-1 text-3xl font-bold text-gray-900 dark:text-white">
              {totalFindings}
            </div>
          </div>

          {/* Pass / Fail */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
              Pass / Fail
            </div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-green-600 dark:text-green-400">
                {totalPass}
              </span>
              <span className="text-gray-400">/</span>
              <span className="text-3xl font-bold text-red-600 dark:text-red-400">
                {totalFail}
              </span>
            </div>
          </div>

          {/* Pass rate donut-like bar */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
              Pass Rate
            </div>
            <div className="mt-1 text-3xl font-bold text-gray-900 dark:text-white">
              {passPercent}%
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
              <div
                className="h-full bg-green-500 transition-all"
                style={{ width: `${passPercent}%` }}
              />
            </div>
            <div className="mt-1 flex justify-between text-[10px] text-gray-400">
              <span>{totalPass} pass</span>
              <span>{totalFail} fail</span>
            </div>
          </div>

          {/* Duration */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
              <Clock className="h-3.5 w-3.5" />
              Duration
            </div>
            <div className="mt-1 text-3xl font-bold text-gray-900 dark:text-white">
              {formatDuration(scan.duration_seconds)}
            </div>
          </div>
        </div>

        {/* Priority breakdown + Delta row */}
        <div className="grid gap-4 lg:grid-cols-2">
          {/* Priority distribution */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
              <BarChart3 className="h-4 w-4" />
              Priority Distribution
            </h2>
            {totalFail > 0 ? (
              <div className="space-y-3">
                {tiers.map((tier) => {
                  const count = scan.priority_breakdown[tier] ?? 0;
                  const pct = totalFail > 0 ? (count / totalFail) * 100 : 0;
                  return (
                    <div key={tier} className="flex items-center gap-3">
                      <PriorityBadge value={tier} />
                      <div className="flex-1">
                        <div className="h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700">
                          <div
                            className="h-full rounded-full bg-current transition-all"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          router.push(
                            `/findings?priority=${tier}&status=fail&scan_id=${scan.id}`,
                          )
                        }
                        className="min-w-[3rem] text-right text-sm font-semibold text-gray-900 hover:text-blue-600 dark:text-white dark:hover:text-blue-400"
                      >
                        {count}
                      </button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="py-6 text-center text-sm text-gray-400">
                No failing findings in this scan
              </p>
            )}
          </div>

          {/* Delta vs previous scan */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
              <TrendingUp className="h-4 w-4" />
              Delta vs Previous Scan
            </h2>
            {hasDelta ? (
              <div className="space-y-4">
                <div className="flex items-center gap-3 rounded-lg bg-red-50 px-4 py-3 dark:bg-red-900/20">
                  <AlertTriangle className="h-5 w-5 text-red-500" />
                  <div>
                    <div className="text-sm font-semibold text-red-700 dark:text-red-400">
                      {scan.delta_new} new finding
                      {scan.delta_new !== 1 ? "s" : ""}
                    </div>
                    <div className="text-xs text-red-600/70 dark:text-red-400/70">
                      Appeared since last scan
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-lg bg-green-50 px-4 py-3 dark:bg-green-900/20">
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  <div>
                    <div className="text-sm font-semibold text-green-700 dark:text-green-400">
                      {scan.delta_fixed} fixed
                    </div>
                    <div className="text-xs text-green-600/70 dark:text-green-400/70">
                      Resolved since last scan
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-lg bg-gray-50 px-4 py-3 dark:bg-gray-700/30">
                  <Minus className="h-5 w-5 text-gray-400" />
                  <div>
                    <div className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                      {scan.delta_unchanged} unchanged
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      Still failing from last scan
                    </div>
                  </div>
                </div>
                {scan.previous_scan_id && (
                  <button
                    onClick={() =>
                      router.push(`/scans/${scan.previous_scan_id}`)
                    }
                    className="mt-1 text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
                  >
                    <TrendingDown className="mr-1 inline h-3.5 w-3.5" />
                    View previous scan
                  </button>
                )}
              </div>
            ) : (
              <div className="py-6 text-center text-sm text-gray-400">
                This is the first scan for this account — no delta available
                yet.
              </div>
            )}
          </div>
        </div>

        {/* Quick action — jump to findings */}
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() =>
              router.push(`/findings?status=fail&scan_id=${scan.id}`)
            }
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-red-700"
          >
            View {totalFail} Failing Findings
          </button>
          <button
            onClick={() => router.push(`/findings?scan_id=${scan.id}`)}
            className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-gray-700 shadow-sm transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
          >
            View All {totalFindings} Findings
          </button>
        </div>
      </div>
    </AppShell>
  );
}
