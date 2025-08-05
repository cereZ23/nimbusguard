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
import { ChevronUp, ChevronDown, Search } from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import ErrorState from "@/components/ui/error-state";
import FilterPanel, { type FilterConfig } from "@/components/ui/filter-panel";
import { TableSkeleton } from "@/components/ui/skeleton";
import Pagination from "@/components/ui/pagination";
import api from "@/lib/api";
import type { Asset, CloudAccount } from "@/types";

type AssetsSortColumn = "name" | "resource_type" | "region" | "last_seen_at";

type SortOrder = "asc" | "desc";

const DEFAULT_SORT_BY: AssetsSortColumn = "last_seen_at";
const DEFAULT_SORT_ORDER: SortOrder = "desc";
const DEFAULT_SIZE = 20;

function SortIndicator({
  column,
  active,
  order,
}: {
  column: AssetsSortColumn;
  active: AssetsSortColumn;
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

export default function AssetsPage() {
  return (
    <Suspense>
      <AssetsContent />
    </Suspense>
  );
}

function AssetsContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Derive ALL filter/sort/pagination state from URL search params
  const resourceTypeFilter = searchParams.get("resource_type") ?? "";
  const regionFilter = searchParams.get("region") ?? "";
  const accountFilter = searchParams.get("account_id") ?? "";
  const searchQuery = searchParams.get("search") ?? "";
  const sortBy = (searchParams.get("sort_by") ??
    DEFAULT_SORT_BY) as AssetsSortColumn;
  const sortOrder = (searchParams.get("sort_order") ??
    DEFAULT_SORT_ORDER) as SortOrder;
  const page = parseInt(searchParams.get("page") ?? "1", 10);
  const size = parseInt(searchParams.get("size") ?? String(DEFAULT_SIZE), 10);

  // Local state for data, loading, and filter options
  const [assets, setAssets] = useState<Asset[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resourceTypes, setResourceTypes] = useState<string[]>([]);
  const [regions, setRegions] = useState<string[]>([]);
  const [accounts, setAccounts] = useState<CloudAccount[]>([]);

  // Search input local state for debouncing
  const [searchInput, setSearchInput] = useState(searchQuery);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep search input in sync when URL param changes externally
  useEffect(() => {
    setSearchInput(searchQuery);
  }, [searchQuery]);

  /**
   * Update URL search params without a full navigation. Default values are
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

  // Debounced search handler
  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchInput(value);
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      debounceTimerRef.current = setTimeout(() => {
        updateParams({ search: value || null, page: "1" });
      }, 300);
    },
    [updateParams],
  );

  // Search on Enter key
  const handleSearchKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        if (debounceTimerRef.current) {
          clearTimeout(debounceTimerRef.current);
        }
        updateParams({ search: searchInput || null, page: "1" });
      }
    },
    [searchInput, updateParams],
  );

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  const handleSort = (column: AssetsSortColumn) => {
    if (column === sortBy) {
      updateParams({
        sort_order: sortOrder === "asc" ? "desc" : "asc",
        page: "1",
      });
    } else {
      updateParams({ sort_by: column, sort_order: "desc", page: "1" });
    }
  };

  // Fetch cloud accounts on mount for the Account filter
  useEffect(() => {
    api
      .get("/accounts")
      .then((res) => {
        const data = res.data?.data as CloudAccount[] | null;
        setAccounts(data ?? []);
      })
      .catch(() => {
        // Non-critical: account filter will simply be empty
      });
  }, []);

  const fetchAssets = useCallback(() => {
    setError(null);
    setIsLoading(true);
    const params: Record<string, string | number> = {
      page,
      size,
      sort_by: sortBy,
      sort_order: sortOrder,
    };
    if (resourceTypeFilter) {
      params.resource_type = resourceTypeFilter;
    }
    if (regionFilter) {
      params.region = regionFilter;
    }
    if (accountFilter) {
      params.account_id = accountFilter;
    }
    if (searchQuery) {
      params.search = searchQuery;
    }

    api
      .get("/assets", { params })
      .then((res) => {
        const data = res.data?.data as Asset[] | null;
        const items = data ?? [];
        setAssets(items);

        // Collect unique resource types and regions for filter dropdowns.
        // Accumulate rather than replace to keep options stable across pages.
        const types = Array.from(new Set(items.map((a) => a.resource_type)));
        setResourceTypes((prev) => {
          const merged = new Set([...prev, ...types]);
          return merged.size > prev.length ? Array.from(merged).sort() : prev;
        });

        const itemRegions = items
          .map((a) => a.region)
          .filter((r): r is string => r !== null);
        const uniqueRegions = Array.from(new Set(itemRegions));
        setRegions((prev) => {
          const merged = new Set([...prev, ...uniqueRegions]);
          return merged.size > prev.length ? Array.from(merged).sort() : prev;
        });

        if (res.data?.meta) {
          setTotal(res.data.meta.total ?? 0);
        }
      })
      .catch((err) =>
        setError(err?.response?.data?.error || "Failed to load assets"),
      )
      .finally(() => setIsLoading(false));
  }, [
    page,
    size,
    resourceTypeFilter,
    regionFilter,
    accountFilter,
    searchQuery,
    sortBy,
    sortOrder,
  ]);

  useEffect(() => {
    fetchAssets();
  }, [fetchAssets]);

  const formatResourceType = (type: string) =>
    type
      .replace(/\//g, " / ")
      .split("/")
      .pop()
      ?.replace(/([A-Z])/g, " $1")
      .trim() ?? type;

  // Build FilterPanel configuration
  const filterConfigs: FilterConfig[] = useMemo(() => {
    const configs: FilterConfig[] = [
      {
        key: "resource_type",
        label: "Resource Type",
        type: "select",
        options: resourceTypes.map((t) => ({
          value: t,
          label: formatResourceType(t),
        })),
        placeholder: "All Types",
      },
      {
        key: "region",
        label: "Region",
        type: "select",
        options: regions.map((r) => ({
          value: r,
          label: r,
        })),
        placeholder: "All Regions",
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
  }, [resourceTypes, regions, accounts]);

  // Derive FilterPanel values from URL params
  const filterValues: Record<string, string> = useMemo(() => {
    const values: Record<string, string> = {};
    if (resourceTypeFilter) values.resource_type = resourceTypeFilter;
    if (regionFilter) values.region = regionFilter;
    if (accountFilter) values.account_id = accountFilter;
    return values;
  }, [resourceTypeFilter, regionFilter, accountFilter]);

  const handleFilterChange = useCallback(
    (key: string, value: string | null) => {
      updateParams({ [key]: value, page: "1" });
    },
    [updateParams],
  );

  const handleClearAllFilters = useCallback(() => {
    updateParams({
      resource_type: null,
      region: null,
      account_id: null,
      search: null,
      page: "1",
    });
    setSearchInput("");
  }, [updateParams]);

  const sortableThClass =
    "px-4 py-3 font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-200";

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Assets
            </h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Cloud resources discovered across all connected accounts
            </p>
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            {total.toLocaleString()} total assets
          </div>
        </div>

        {/* Search input */}
        <div data-tour="assets-search" className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => handleSearchChange(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            placeholder="Search assets by name..."
            className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-10 pr-4 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:placeholder:text-gray-500"
          />
        </div>

        {/* FilterPanel */}
        <div data-tour="assets-filters">
          <FilterPanel
            filters={filterConfigs}
            values={filterValues}
            onChange={handleFilterChange}
            onClearAll={handleClearAllFilters}
          />
        </div>

        {/* Error state */}
        {error && <ErrorState message={error} onRetry={fetchAssets} />}

        {/* Table */}
        {!error && (
          <div
            data-tour="assets-table"
            className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800"
          >
            {isLoading ? (
              <TableSkeleton rows={8} cols={4} />
            ) : assets.length === 0 ? (
              <div className="flex h-64 flex-col items-center justify-center">
                <p className="text-lg font-medium text-gray-500 dark:text-gray-400">
                  No assets found
                </p>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  {searchQuery ||
                  resourceTypeFilter ||
                  regionFilter ||
                  accountFilter
                    ? "Try adjusting your search or filters."
                    : "Connect a cloud account and run a scan to discover resources."}
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table
                  className="w-full text-left text-sm"
                  aria-label="Assets list"
                >
                  <thead>
                    <tr className="border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/50">
                      <th
                        className={sortableThClass}
                        onClick={() => handleSort("name")}
                        aria-sort={
                          sortBy === "name"
                            ? sortOrder === "asc"
                              ? "ascending"
                              : "descending"
                            : "none"
                        }
                      >
                        Name
                        <SortIndicator
                          column="name"
                          active={sortBy}
                          order={sortOrder}
                        />
                      </th>
                      <th
                        className={sortableThClass}
                        onClick={() => handleSort("resource_type")}
                        aria-sort={
                          sortBy === "resource_type"
                            ? sortOrder === "asc"
                              ? "ascending"
                              : "descending"
                            : "none"
                        }
                      >
                        Type
                        <SortIndicator
                          column="resource_type"
                          active={sortBy}
                          order={sortOrder}
                        />
                      </th>
                      <th
                        className={sortableThClass}
                        onClick={() => handleSort("region")}
                        aria-sort={
                          sortBy === "region"
                            ? sortOrder === "asc"
                              ? "ascending"
                              : "descending"
                            : "none"
                        }
                      >
                        Region
                        <SortIndicator
                          column="region"
                          active={sortBy}
                          order={sortOrder}
                        />
                      </th>
                      <th
                        className={sortableThClass}
                        onClick={() => handleSort("last_seen_at")}
                        aria-sort={
                          sortBy === "last_seen_at"
                            ? sortOrder === "asc"
                              ? "ascending"
                              : "descending"
                            : "none"
                        }
                      >
                        Last Seen
                        <SortIndicator
                          column="last_seen_at"
                          active={sortBy}
                          order={sortOrder}
                        />
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {assets.map((asset, idx) => (
                      <tr
                        key={asset.id}
                        onClick={() => router.push(`/assets/${asset.id}`)}
                        aria-label={`View asset: ${asset.name}`}
                        className={`cursor-pointer border-b border-gray-100 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/50 ${
                          idx % 2 === 1
                            ? "bg-gray-50/50 dark:bg-gray-800/50"
                            : ""
                        }`}
                      >
                        <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                          {asset.name}
                        </td>
                        <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                          {formatResourceType(asset.resource_type)}
                        </td>
                        <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                          {asset.region ?? "\u2014"}
                        </td>
                        <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                          {new Date(asset.last_seen_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            {assets.length > 0 && (
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
