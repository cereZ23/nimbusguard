"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { AxiosError } from "axios";
import { Play, RefreshCw } from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import ErrorState from "@/components/ui/error-state";
import Pagination from "@/components/ui/pagination";
import { TableSkeleton } from "@/components/ui/skeleton";
import api from "@/lib/api";
import { formatDateTime, formatRelative } from "@/lib/dates";
import { extractApiError } from "@/lib/errors";
import type { CloudAccount, Scan, ScanStatus } from "@/types";

const DEFAULT_SIZE = 20;
const POLL_INTERVAL_MS = 5000;

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "pending", label: "Pending" },
  { value: "running", label: "Running" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "\u2014";
  if (seconds < 1) return "<1s";
  if (seconds < 60) return `${seconds}s`;
  const min = Math.floor(seconds / 60);
  const rem = seconds % 60;
  return rem ? `${min}m ${rem}s` : `${min}m`;
}

const STATUS_STYLES: Record<
  ScanStatus,
  { bg: string; text: string; dot: string; label: string }
> = {
  pending: {
    bg: "bg-slate-100 dark:bg-slate-800",
    text: "text-slate-700 dark:text-slate-300",
    dot: "bg-slate-400",
    label: "Pending",
  },
  running: {
    bg: "bg-blue-50 dark:bg-blue-900/30",
    text: "text-blue-700 dark:text-blue-300",
    dot: "bg-blue-500 animate-pulse",
    label: "Running",
  },
  completed: {
    bg: "bg-green-50 dark:bg-green-900/30",
    text: "text-green-700 dark:text-green-300",
    dot: "bg-green-500",
    label: "Completed",
  },
  failed: {
    bg: "bg-red-50 dark:bg-red-900/30",
    text: "text-red-700 dark:text-red-300",
    dot: "bg-red-500",
    label: "Failed",
  },
};

function ScanStatusBadge({ status }: { status: ScanStatus }) {
  const styles = STATUS_STYLES[status] ?? STATUS_STYLES.pending;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${styles.bg} ${styles.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${styles.dot}`} />
      {styles.label}
    </span>
  );
}

export default function ScansPage() {
  return (
    <Suspense>
      <ScansContent />
    </Suspense>
  );
}

function ScansContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const accountFilter = searchParams.get("cloud_account_id") ?? "";
  const statusFilter = searchParams.get("status") ?? "";
  const page = parseInt(searchParams.get("page") ?? "1", 10);
  const size = parseInt(searchParams.get("size") ?? String(DEFAULT_SIZE), 10);

  const [scans, setScans] = useState<Scan[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<CloudAccount[]>([]);

  const [triggerAccountId, setTriggerAccountId] = useState<string>("");
  const [triggering, setTriggering] = useState(false);
  const [triggerMessage, setTriggerMessage] = useState<string | null>(null);

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const updateParams = useCallback(
    (updates: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === "") {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      }
      if (params.get("page") === "1") params.delete("page");
      if (params.get("size") === String(DEFAULT_SIZE)) params.delete("size");
      const qs = params.toString();
      router.replace(`${pathname}${qs ? `?${qs}` : ""}`);
    },
    [searchParams, pathname, router],
  );

  // Load cloud accounts once — needed for both the filter and the run-scan selector.
  useEffect(() => {
    api
      .get("/accounts", { params: { size: 100 } })
      .then((res) => {
        const list = (res.data?.data ?? []) as CloudAccount[];
        setAccounts(list);
        // Default trigger target: first account if none already selected.
        setTriggerAccountId((current) => current || (list[0]?.id ?? ""));
      })
      .catch(() => {
        // Non-critical; the filter + trigger will show empty state.
      });
  }, []);

  const fetchScans = useCallback(async () => {
    setError(null);
    try {
      const params: Record<string, string | number> = { page, size };
      if (accountFilter) params.cloud_account_id = accountFilter;
      if (statusFilter) params.status = statusFilter;
      const res = await api.get("/scans", { params });
      const data = (res.data?.data ?? []) as Scan[];
      setScans(data);
      if (res.data?.meta) {
        setTotal(res.data.meta.total ?? 0);
      }
    } catch (err: unknown) {
      setError(extractApiError(err));
    } finally {
      setIsLoading(false);
    }
  }, [page, size, accountFilter, statusFilter]);

  // Initial + filter-change fetch.
  useEffect(() => {
    setIsLoading(true);
    fetchScans();
  }, [fetchScans]);

  // Poll every POLL_INTERVAL_MS while at least one visible scan is pending/running.
  const hasInFlight = useMemo(
    () => scans.some((s) => s.status === "pending" || s.status === "running"),
    [scans],
  );

  useEffect(() => {
    if (!hasInFlight) {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      return;
    }
    pollTimerRef.current = setTimeout(() => {
      fetchScans();
    }, POLL_INTERVAL_MS);
    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [hasInFlight, fetchScans, scans]);

  const handleTriggerScan = useCallback(async () => {
    if (!triggerAccountId) return;
    setTriggering(true);
    setTriggerMessage(null);
    try {
      await api.post("/scans", { cloud_account_id: triggerAccountId });
      setTriggerMessage("Scan started successfully");
      // Reload immediately so the new scan shows up at the top.
      await fetchScans();
    } catch (err: unknown) {
      const axiosErr = err as AxiosError<{ detail?: string }>;
      const statusCode = axiosErr.response?.status;
      if (statusCode === 409) {
        setTriggerMessage("A scan is already running for this account.");
      } else if (statusCode === 429) {
        setTriggerMessage("Rate limit reached — try again later.");
      } else {
        setTriggerMessage(extractApiError(err));
      }
    } finally {
      setTriggering(false);
      setTimeout(() => setTriggerMessage(null), 5000);
    }
  }, [triggerAccountId, fetchScans]);

  const activeAccounts = useMemo(
    () => accounts.filter((a) => a.status === "active"),
    [accounts],
  );

  const accountName = (id: string) =>
    accounts.find((a) => a.id === id)?.display_name ?? id.slice(0, 8);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Scans
            </h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Scan history and manual triggers for all connected cloud accounts
            </p>
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            {total.toLocaleString()} total scan{total === 1 ? "" : "s"}
          </div>
        </div>

        {/* Run scan bar */}
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:gap-3">
              <label
                htmlFor="trigger-account"
                className="text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Run a new scan
              </label>
              <select
                id="trigger-account"
                value={triggerAccountId}
                onChange={(e) => setTriggerAccountId(e.target.value)}
                disabled={activeAccounts.length === 0 || triggering}
                className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-100 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-200 dark:disabled:bg-gray-800"
              >
                {activeAccounts.length === 0 ? (
                  <option value="">No active account</option>
                ) : (
                  activeAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.display_name} ({a.provider.toUpperCase()})
                    </option>
                  ))
                )}
              </select>
            </div>
            <div className="flex items-center gap-3">
              {triggerMessage && (
                <span
                  className={`text-xs font-medium ${
                    triggerMessage.includes("success")
                      ? "text-green-600 dark:text-green-400"
                      : "text-red-600 dark:text-red-400"
                  }`}
                >
                  {triggerMessage}
                </span>
              )}
              <button
                type="button"
                onClick={handleTriggerScan}
                disabled={triggering || !triggerAccountId}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-blue-600 dark:hover:bg-blue-500"
              >
                {triggering ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                {triggering ? "Starting..." : "Run scan"}
              </button>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <label
              htmlFor="filter-account"
              className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400"
            >
              Account
            </label>
            <select
              id="filter-account"
              value={accountFilter}
              onChange={(e) =>
                updateParams({
                  cloud_account_id: e.target.value || null,
                  page: "1",
                })
              }
              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-200"
            >
              <option value="">All accounts</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.display_name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label
              htmlFor="filter-status"
              className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400"
            >
              Status
            </label>
            <select
              id="filter-status"
              value={statusFilter}
              onChange={(e) =>
                updateParams({ status: e.target.value || null, page: "1" })
              }
              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-200"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          {(accountFilter || statusFilter) && (
            <button
              type="button"
              onClick={() =>
                updateParams({
                  cloud_account_id: null,
                  status: null,
                  page: "1",
                })
              }
              className="text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
            >
              Clear filters
            </button>
          )}
          <div className="ml-auto flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
            {hasInFlight && (
              <span className="inline-flex items-center gap-1">
                <RefreshCw className="h-3 w-3 animate-spin" /> Live updating...
              </span>
            )}
          </div>
        </div>

        {error && <ErrorState message={error} onRetry={() => fetchScans()} />}

        {!error && (
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
            {isLoading ? (
              <TableSkeleton rows={8} cols={6} />
            ) : scans.length === 0 ? (
              <div className="flex h-64 flex-col items-center justify-center px-6 text-center">
                <p className="text-lg font-medium text-gray-700 dark:text-gray-300">
                  No scans yet
                </p>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  {accountFilter || statusFilter
                    ? "Try clearing the filters."
                    : "Click Run scan above to trigger your first scan."}
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table
                  className="w-full text-left text-sm"
                  aria-label="Scans history"
                >
                  <thead>
                    <tr className="border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/50">
                      <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                        Started
                      </th>
                      <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                        Account
                      </th>
                      <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                        Status
                      </th>
                      <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                        Duration
                      </th>
                      <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                        Findings
                      </th>
                      <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                        Type
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {scans.map((scan, idx) => {
                      const when = scan.started_at ?? scan.created_at;
                      return (
                        <tr
                          key={scan.id}
                          onClick={() => router.push(`/scans/${scan.id}`)}
                          className={`cursor-pointer border-b border-gray-100 transition-colors hover:bg-blue-50/50 dark:border-gray-700 dark:hover:bg-blue-900/10 ${
                            idx % 2 === 1
                              ? "bg-gray-50/50 dark:bg-gray-800/70"
                              : ""
                          }`}
                        >
                          <td className="px-4 py-3">
                            <div className="font-medium text-gray-900 dark:text-gray-100">
                              {formatRelative(when)}
                            </div>
                            <div className="text-xs text-gray-500 dark:text-gray-400">
                              {formatDateTime(when)}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                            <div className="font-medium">
                              {scan.cloud_account_name ??
                                accountName(scan.cloud_account_id)}
                            </div>
                            {scan.cloud_account_provider && (
                              <div className="text-xs uppercase text-gray-500 dark:text-gray-400">
                                {scan.cloud_account_provider}
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <ScanStatusBadge status={scan.status} />
                          </td>
                          <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                            {formatDuration(scan.duration_seconds)}
                          </td>
                          <td className="px-4 py-3">
                            {scan.findings_count === null ||
                            scan.findings_count === 0 ? (
                              <span className="text-gray-500 dark:text-gray-400">
                                —
                              </span>
                            ) : (
                              <div className="flex items-center gap-3">
                                <span className="font-medium text-gray-900 dark:text-gray-100">
                                  {scan.findings_count}
                                </span>
                                {(scan.findings_fail_count ?? 0) > 0 && (
                                  <span className="text-xs font-medium text-red-600 dark:text-red-400">
                                    {scan.findings_fail_count} fail
                                  </span>
                                )}
                                {(scan.findings_pass_count ?? 0) > 0 && (
                                  <span className="text-xs font-medium text-green-600 dark:text-green-400">
                                    {scan.findings_pass_count} pass
                                  </span>
                                )}
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3 text-xs uppercase text-gray-500 dark:text-gray-400">
                            {scan.scan_type}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {scans.length > 0 && (
              <Pagination
                page={page}
                size={size}
                total={total}
                onPageChange={(p) => updateParams({ page: String(p) })}
                onSizeChange={(s) =>
                  updateParams({ size: String(s), page: "1" })
                }
              />
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
