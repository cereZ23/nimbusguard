"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import {
  ChevronUp,
  ChevronDown,
  X,
  Search,
  ShieldCheck,
  CheckSquare,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import SeverityBadge from "@/components/ui/severity-badge";
import StatusBadge from "@/components/ui/status-badge";
import ErrorState from "@/components/ui/error-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import Pagination from "@/components/ui/pagination";
import FilterPanel from "@/components/ui/filter-panel";
import type { FilterConfig } from "@/components/ui/filter-panel";
import api from "@/lib/api";
import type { Finding, CloudAccount } from "@/types";

type FindingsSortColumn =
  | "title"
  | "severity"
  | "status"
  | "first_detected_at"
  | "last_evaluated_at";

type SortOrder = "asc" | "desc";

const DEFAULT_SORT_BY: FindingsSortColumn = "last_evaluated_at";
const DEFAULT_SORT_ORDER: SortOrder = "desc";
const DEFAULT_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 300;

// Filter keys that should be cleared on "Clear all"
const FILTER_KEYS = ["severity", "status", "account_id"] as const;

function SortIndicator({
  column,
  active,
  order,
}: {
  column: FindingsSortColumn;
  active: FindingsSortColumn;
  order: SortOrder;
}) {
  if (column !== active) {
    return (
      <span className="ml-1 inline-flex flex-col opacity-30" aria-hidden="true">
        <ChevronUp className="h-3 w-3 -mb-1" />
        <ChevronDown className="h-3 w-3" />
      </span>
    );
  }
  return order === "asc" ? (
    <ChevronUp
      className="ml-1 inline h-3.5 w-3.5 text-blue-500"
      aria-hidden="true"
    />
  ) : (
    <ChevronDown
      className="ml-1 inline h-3.5 w-3.5 text-blue-500"
      aria-hidden="true"
    />
  );
}

export default function FindingsPage() {
  return (
    <Suspense>
      <FindingsContent />
    </Suspense>
  );
}

function FindingsContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // -- URL-derived state --
  const severityFilter = searchParams.get("severity") ?? "";
  const statusFilter = searchParams.get("status") ?? "";
  const accountIdFilter = searchParams.get("account_id") ?? "";
  const searchQuery = searchParams.get("search") ?? "";
  const sortBy = (searchParams.get("sort_by") ??
    DEFAULT_SORT_BY) as FindingsSortColumn;
  const sortOrder = (searchParams.get("sort_order") ??
    DEFAULT_SORT_ORDER) as SortOrder;
  const page = parseInt(searchParams.get("page") ?? "1", 10);
  const size = parseInt(searchParams.get("size") ?? String(DEFAULT_SIZE), 10);
  const controlId = searchParams.get("control_id");

  // -- Data state --
  const [findings, setFindings] = useState<Finding[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // -- Accounts for filter --
  const [accounts, setAccounts] = useState<CloudAccount[]>([]);

  // -- Search input (local for debounce) --
  const [searchInput, setSearchInput] = useState(searchQuery);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // -- Bulk selection state --
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // -- Bulk waive modal state --
  const [showWaiveModal, setShowWaiveModal] = useState(false);
  const [waiveReason, setWaiveReason] = useState("");
  const [waiveSubmitting, setWaiveSubmitting] = useState(false);
  const [waiveError, setWaiveError] = useState<string | null>(null);
  const [waiveSuccess, setWaiveSuccess] = useState<string | null>(null);

  // -- Fetch accounts on mount --
  useEffect(() => {
    api
      .get("/accounts")
      .then((res) => {
        const data = res.data?.data as CloudAccount[] | null;
        setAccounts(data ?? []);
      })
      .catch(() => {
        // Accounts filter will simply be empty if the fetch fails
      });
  }, []);

  // -- Sync local search input when URL changes externally --
  useEffect(() => {
    setSearchInput(searchQuery);
  }, [searchQuery]);

  /**
   * Update URL search params without full navigation. Default values are
   * removed from the URL to keep it clean.
   */
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
      // Remove default values from URL
      if (params.get("severity") === "all") params.delete("severity");
      if (params.get("status") === "all") params.delete("status");
      if (params.get("sort_by") === DEFAULT_SORT_BY) params.delete("sort_by");
      if (params.get("sort_order") === DEFAULT_SORT_ORDER)
        params.delete("sort_order");
      if (params.get("page") === "1") params.delete("page");
      if (params.get("size") === String(DEFAULT_SIZE)) params.delete("size");

      const qs = params.toString();
      router.replace(`${pathname}${qs ? `?${qs}` : ""}`);
    },
    [searchParams, pathname, router],
  );

  // -- Debounced search --
  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchInput(value);
      if (searchTimerRef.current) {
        clearTimeout(searchTimerRef.current);
      }
      searchTimerRef.current = setTimeout(() => {
        updateParams({ search: value || null, page: "1" });
      }, SEARCH_DEBOUNCE_MS);
    },
    [updateParams],
  );

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (searchTimerRef.current) {
        clearTimeout(searchTimerRef.current);
      }
    };
  }, []);

  const handleSort = (column: FindingsSortColumn) => {
    if (column === sortBy) {
      updateParams({
        sort_order: sortOrder === "asc" ? "desc" : "asc",
        page: "1",
      });
    } else {
      updateParams({ sort_by: column, sort_order: "desc", page: "1" });
    }
  };

  // -- FilterPanel config --
  const filterConfigs: FilterConfig[] = useMemo(() => {
    const configs: FilterConfig[] = [
      {
        key: "severity",
        label: "Severity",
        type: "select",
        options: [
          { value: "high", label: "High" },
          { value: "medium", label: "Medium" },
          { value: "low", label: "Low" },
        ],
        placeholder: "All Severities",
      },
      {
        key: "status",
        label: "Status",
        type: "select",
        options: [
          { value: "fail", label: "Fail" },
          { value: "pass", label: "Pass" },
          { value: "error", label: "Error" },
          { value: "not_applicable", label: "N/A" },
        ],
        placeholder: "All Statuses",
      },
    ];

    if (accounts.length > 0) {
      configs.push({
        key: "account_id",
        label: "Account",
        type: "select",
        options: accounts.map((a) => ({
          value: a.id,
          label: a.display_name,
        })),
        placeholder: "All Accounts",
      });
    }

    return configs;
  }, [accounts]);

  const filterValues: Record<string, string> = useMemo(() => {
    const values: Record<string, string> = {};
    if (severityFilter) values.severity = severityFilter;
    if (statusFilter) values.status = statusFilter;
    if (accountIdFilter) values.account_id = accountIdFilter;
    return values;
  }, [severityFilter, statusFilter, accountIdFilter]);

  const handleFilterChange = useCallback(
    (key: string, value: string | null) => {
      updateParams({ [key]: value, page: "1" });
    },
    [updateParams],
  );

  const handleClearAllFilters = useCallback(() => {
    const updates: Record<string, string | null> = { page: "1" };
    for (const key of FILTER_KEYS) {
      updates[key] = null;
    }
    updateParams(updates);
  }, [updateParams]);

  // -- Fetch findings --
  const fetchFindings = useCallback(() => {
    setError(null);
    setIsLoading(true);
    const params: Record<string, string | number> = {
      page,
      size,
      sort_by: sortBy,
      sort_order: sortOrder,
    };
    if (severityFilter) {
      params.severity = severityFilter;
    }
    if (statusFilter) {
      params.status = statusFilter;
    }
    if (accountIdFilter) {
      params.account_id = accountIdFilter;
    }
    if (searchQuery) {
      params.search = searchQuery;
    }
    if (controlId) {
      params.control_id = controlId;
    }

    api
      .get("/findings", { params })
      .then((res) => {
        const data = res.data?.data as Finding[] | null;
        setFindings(data ?? []);
        if (res.data?.meta) {
          setTotal(res.data.meta.total ?? 0);
        }
      })
      .catch((err) =>
        setError(err?.response?.data?.error || "Failed to load findings"),
      )
      .finally(() => setIsLoading(false));
  }, [
    page,
    size,
    severityFilter,
    statusFilter,
    accountIdFilter,
    searchQuery,
    sortBy,
    sortOrder,
    controlId,
  ]);

  useEffect(() => {
    fetchFindings();
  }, [fetchFindings]);

  // Clear selection when findings data changes (e.g. page change, filter change)
  useEffect(() => {
    setSelectedIds(new Set());
  }, [findings]);

  // -- Selection handlers --
  const allOnPageSelected =
    findings.length > 0 && findings.every((f) => selectedIds.has(f.id));

  const someOnPageSelected =
    findings.some((f) => selectedIds.has(f.id)) && !allOnPageSelected;

  const toggleSelectAll = () => {
    if (allOnPageSelected) {
      // Deselect all on current page
      setSelectedIds((prev) => {
        const next = new Set(Array.from(prev));
        findings.forEach((f) => next.delete(f.id));
        return next;
      });
    } else {
      // Select all on current page
      setSelectedIds((prev) => {
        const next = new Set(Array.from(prev));
        findings.forEach((f) => next.add(f.id));
        return next;
      });
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(Array.from(prev));
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // -- Bulk waive --
  const handleBulkWaiveSubmit = async () => {
    if (!waiveReason.trim() || selectedIds.size === 0) return;
    setWaiveSubmitting(true);
    setWaiveError(null);

    try {
      await api.post("/findings/bulk-waive", {
        finding_ids: Array.from(selectedIds),
        reason: waiveReason,
      });
      setWaiveSuccess(
        `Waiver requested for ${selectedIds.size} finding${selectedIds.size > 1 ? "s" : ""}.`,
      );
      setShowWaiveModal(false);
      setWaiveReason("");
      setSelectedIds(new Set());
      fetchFindings();
      // Auto-dismiss success message
      setTimeout(() => setWaiveSuccess(null), 5000);
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { data?: { detail?: string; error?: string } };
      };
      setWaiveError(
        axiosErr.response?.data?.detail ??
          axiosErr.response?.data?.error ??
          "Failed to submit bulk waiver request",
      );
    } finally {
      setWaiveSubmitting(false);
    }
  };

  const sortableThClass =
    "px-4 py-3 font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-200";

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Findings
            </h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Security findings across all connected cloud accounts
            </p>
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            {total.toLocaleString()} total findings
          </div>
        </div>

        {/* Search input */}
        <div data-tour="findings-search" className="relative max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search findings by title..."
            className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-10 pr-10 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:placeholder:text-gray-500"
          />
          {searchInput && (
            <button
              onClick={() => handleSearchChange("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-0.5 text-gray-400 transition-colors hover:text-gray-600 dark:hover:text-gray-300"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* FilterPanel */}
        <div data-tour="findings-filters">
          <FilterPanel
            filters={filterConfigs}
            values={filterValues}
            onChange={handleFilterChange}
            onClearAll={handleClearAllFilters}
          />
        </div>

        {/* Control ID chip (shown separately when active) */}
        <div className="flex flex-wrap items-center gap-2">
          {controlId && (
            <span className="flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm text-blue-700 dark:border-blue-700 dark:bg-blue-900/20 dark:text-blue-300">
              Filtered by control
              <button
                onClick={() => router.push("/findings")}
                className="ml-1 rounded p-0.5 hover:bg-blue-100 dark:hover:bg-blue-800"
                aria-label="Clear control filter"
              >
                <X size={14} />
              </button>
            </span>
          )}
          {findings.some((f) => f.waived) && (
            <span className="text-xs text-gray-400 dark:text-gray-500">
              Some findings are waived
            </span>
          )}
        </div>

        {/* Success message */}
        {waiveSuccess && (
          <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm font-medium text-green-700 dark:border-green-800 dark:bg-green-900/20 dark:text-green-300">
            <CheckSquare className="h-4 w-4 flex-shrink-0" />
            {waiveSuccess}
            <button
              onClick={() => setWaiveSuccess(null)}
              className="ml-auto rounded p-0.5 transition-colors hover:bg-green-100 dark:hover:bg-green-800"
              aria-label="Dismiss"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Error state */}
        {error && <ErrorState message={error} onRetry={fetchFindings} />}

        {/* Table */}
        {!error && (
          <div
            data-tour="findings-table"
            className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800"
          >
            {isLoading ? (
              <TableSkeleton rows={8} cols={7} />
            ) : findings.length === 0 ? (
              <div className="flex h-64 flex-col items-center justify-center">
                <p className="text-lg font-medium text-gray-500 dark:text-gray-400">
                  No findings found
                </p>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Run a scan to evaluate your cloud security posture.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table
                  className="w-full text-left text-sm"
                  aria-label="Findings list"
                >
                  <thead>
                    <tr className="border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/50">
                      {/* Checkbox header */}
                      <th className="w-10 px-4 py-3">
                        <input
                          type="checkbox"
                          checked={allOnPageSelected}
                          ref={(el) => {
                            if (el) el.indeterminate = someOnPageSelected;
                          }}
                          onChange={toggleSelectAll}
                          className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800"
                          aria-label="Select all findings on this page"
                        />
                      </th>
                      <th
                        className={sortableThClass}
                        onClick={() => handleSort("title")}
                        aria-sort={
                          sortBy === "title"
                            ? sortOrder === "asc"
                              ? "ascending"
                              : "descending"
                            : "none"
                        }
                      >
                        Title
                        <SortIndicator
                          column="title"
                          active={sortBy}
                          order={sortOrder}
                        />
                      </th>
                      <th
                        className={sortableThClass}
                        onClick={() => handleSort("severity")}
                        aria-sort={
                          sortBy === "severity"
                            ? sortOrder === "asc"
                              ? "ascending"
                              : "descending"
                            : "none"
                        }
                      >
                        Severity
                        <SortIndicator
                          column="severity"
                          active={sortBy}
                          order={sortOrder}
                        />
                      </th>
                      <th
                        className={sortableThClass}
                        onClick={() => handleSort("status")}
                        aria-sort={
                          sortBy === "status"
                            ? sortOrder === "asc"
                              ? "ascending"
                              : "descending"
                            : "none"
                        }
                      >
                        Status
                        <SortIndicator
                          column="status"
                          active={sortBy}
                          order={sortOrder}
                        />
                      </th>
                      <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                        Waived
                      </th>
                      <th
                        className={sortableThClass}
                        onClick={() => handleSort("first_detected_at")}
                        aria-sort={
                          sortBy === "first_detected_at"
                            ? sortOrder === "asc"
                              ? "ascending"
                              : "descending"
                            : "none"
                        }
                      >
                        Detected
                        <SortIndicator
                          column="first_detected_at"
                          active={sortBy}
                          order={sortOrder}
                        />
                      </th>
                      <th
                        className={sortableThClass}
                        onClick={() => handleSort("last_evaluated_at")}
                        aria-sort={
                          sortBy === "last_evaluated_at"
                            ? sortOrder === "asc"
                              ? "ascending"
                              : "descending"
                            : "none"
                        }
                      >
                        Last Evaluated
                        <SortIndicator
                          column="last_evaluated_at"
                          active={sortBy}
                          order={sortOrder}
                        />
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {findings.map((finding, idx) => (
                      <tr
                        key={finding.id}
                        onClick={() => router.push(`/findings/${finding.id}`)}
                        aria-label={`View finding: ${finding.title}`}
                        className={`cursor-pointer border-b border-gray-100 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/50 ${
                          finding.waived ? "opacity-60" : ""
                        } ${idx % 2 === 1 ? "bg-gray-50/50 dark:bg-gray-800/50" : ""}`}
                      >
                        {/* Checkbox cell */}
                        <td className="w-10 px-4 py-3">
                          <input
                            type="checkbox"
                            checked={selectedIds.has(finding.id)}
                            onChange={() => toggleSelect(finding.id)}
                            onClick={(e) => e.stopPropagation()}
                            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800"
                            aria-label={`Select finding: ${finding.title}`}
                          />
                        </td>
                        <td className="max-w-xs truncate px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                          {finding.title}
                        </td>
                        <td className="px-4 py-3">
                          <SeverityBadge severity={finding.severity} />
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={finding.status} />
                        </td>
                        <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                          {finding.waived ? "Yes" : "No"}
                        </td>
                        <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                          {new Date(
                            finding.first_detected_at,
                          ).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                          {new Date(
                            finding.last_evaluated_at,
                          ).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            {findings.length > 0 && (
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

      {/* Bulk action bar (fixed bottom) */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-gray-200 bg-white px-6 py-3 shadow-lg dark:border-gray-700 dark:bg-gray-800">
          <div className="mx-auto flex max-w-7xl items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="flex h-6 min-w-[24px] items-center justify-center rounded-full bg-blue-500 px-2 text-xs font-semibold text-white">
                {selectedIds.size}
              </span>
              <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
                finding{selectedIds.size > 1 ? "s" : ""} selected
              </span>
              <button
                onClick={() => setSelectedIds(new Set())}
                className="text-sm text-gray-500 transition-colors hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                Clear
              </button>
            </div>
            <button
              onClick={() => {
                setShowWaiveModal(true);
                setWaiveError(null);
                setWaiveReason("");
              }}
              className="inline-flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-purple-700 dark:bg-purple-700 dark:hover:bg-purple-600"
            >
              <ShieldCheck className="h-4 w-4" />
              Request Waiver
            </button>
          </div>
        </div>
      )}

      {/* Bulk waive modal */}
      {showWaiveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Request Waiver
              </h2>
              <button
                onClick={() => {
                  setShowWaiveModal(false);
                  setWaiveReason("");
                  setWaiveError(null);
                }}
                className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-300"
              >
                <X size={20} />
              </button>
            </div>

            <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
              Request a waiver for{" "}
              <span className="font-semibold text-gray-700 dark:text-gray-200">
                {selectedIds.size}
              </span>{" "}
              selected finding{selectedIds.size > 1 ? "s" : ""}. An admin will
              review your request.
            </p>

            <label
              htmlFor="waive-reason"
              className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Reason
            </label>
            <textarea
              id="waive-reason"
              value={waiveReason}
              onChange={(e) => setWaiveReason(e.target.value)}
              placeholder="Provide a reason for the waiver request..."
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white dark:placeholder:text-gray-500"
              rows={4}
            />

            {waiveError && (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                {waiveError}
              </p>
            )}

            <div className="mt-4 flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowWaiveModal(false);
                  setWaiveReason("");
                  setWaiveError(null);
                }}
                className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
              >
                Cancel
              </button>
              <button
                onClick={handleBulkWaiveSubmit}
                disabled={!waiveReason.trim() || waiveSubmitting}
                className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-purple-700 disabled:opacity-50 dark:bg-purple-700 dark:hover:bg-purple-600"
              >
                {waiveSubmitting ? "Submitting..." : "Submit Request"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
