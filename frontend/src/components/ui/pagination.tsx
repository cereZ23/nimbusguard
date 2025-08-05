"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

interface PaginationProps {
  page: number;
  size: number;
  total: number;
  onPageChange: (page: number) => void;
  onSizeChange: (size: number) => void;
}

const PAGE_SIZE_OPTIONS = [10, 20, 50];

/**
 * Build a list of page numbers to display, with ellipsis markers (represented
 * as `null`).  The algorithm always shows the first page, last page, the
 * current page and its immediate neighbours, keeping the total number of
 * slots <= 7.
 */
function buildPageNumbers(
  current: number,
  totalPages: number,
): (number | null)[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const pages: (number | null)[] = [];

  // Always show page 1
  pages.push(1);

  if (current > 3) {
    pages.push(null); // left ellipsis
  }

  // Pages around current
  const start = Math.max(2, current - 1);
  const end = Math.min(totalPages - 1, current + 1);

  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  if (current < totalPages - 2) {
    pages.push(null); // right ellipsis
  }

  // Always show last page
  pages.push(totalPages);

  return pages;
}

const btnBase =
  "inline-flex items-center justify-center rounded-lg border text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 dark:focus:ring-offset-gray-900";
const btnNav = `${btnBase} border-gray-300 bg-white px-3 py-1.5 text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700`;
const btnPage = `${btnBase} min-w-[2.25rem] border-gray-300 bg-white px-2 py-1.5 text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700`;
const btnPageActive = `${btnBase} min-w-[2.25rem] border-blue-600 bg-blue-600 px-2 py-1.5 text-white dark:border-blue-500 dark:bg-blue-500`;

export default function Pagination({
  page,
  size,
  total,
  onPageChange,
  onSizeChange,
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / size));
  const startItem = total === 0 ? 0 : (page - 1) * size + 1;
  const endItem = Math.min(page * size, total);
  const pageNumbers = buildPageNumbers(page, totalPages);

  return (
    <div className="flex flex-col gap-3 border-t border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/50 sm:flex-row sm:items-center sm:justify-between">
      {/* Left: showing X-Y of Z + page size selector */}
      <div className="flex items-center gap-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Showing{" "}
          <span className="font-medium text-gray-700 dark:text-gray-200">
            {startItem}
          </span>
          {"-"}
          <span className="font-medium text-gray-700 dark:text-gray-200">
            {endItem}
          </span>{" "}
          of{" "}
          <span className="font-medium text-gray-700 dark:text-gray-200">
            {total.toLocaleString()}
          </span>{" "}
          results
        </p>
        <div className="flex items-center gap-1.5">
          <label
            htmlFor="page-size"
            className="text-sm text-gray-500 dark:text-gray-400"
          >
            Rows:
          </label>
          <select
            id="page-size"
            value={size}
            onChange={(e) => onSizeChange(Number(e.target.value))}
            className="rounded-lg border border-gray-300 bg-white px-2 py-1 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
          >
            {PAGE_SIZE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Right: page numbers + prev/next */}
      <div className="flex items-center gap-1.5">
        {/* Previous */}
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className={btnNav}
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
          <span className="ml-1 hidden sm:inline">Previous</span>
        </button>

        {/* Page numbers */}
        {pageNumbers.map((p, idx) =>
          p === null ? (
            <span
              key={`ellipsis-${idx}`}
              className="px-1.5 text-sm text-gray-400 dark:text-gray-500"
              aria-hidden="true"
            >
              ...
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              className={p === page ? btnPageActive : btnPage}
              aria-current={p === page ? "page" : undefined}
              aria-label={`Page ${p}`}
            >
              {p}
            </button>
          ),
        )}

        {/* Next */}
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className={btnNav}
          aria-label="Next page"
        >
          <span className="mr-1 hidden sm:inline">Next</span>
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
