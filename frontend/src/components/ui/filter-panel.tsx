"use client";

import { ChevronDown, Filter, X } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

export interface FilterOption {
  value: string;
  label: string;
}

export interface FilterConfig {
  key: string;
  label: string;
  type: "select" | "preset";
  options: FilterOption[];
  placeholder?: string;
}

interface ActiveFilter {
  key: string;
  label: string;
  value: string;
  valueLabel: string;
}

interface FilterPanelProps {
  filters: FilterConfig[];
  values: Record<string, string>;
  onChange: (key: string, value: string | null) => void;
  onClearAll: () => void;
}

export default function FilterPanel({
  filters,
  values,
  onChange,
  onClearAll,
}: FilterPanelProps) {
  const [expanded, setExpanded] = useState(true);

  const activeFilters: ActiveFilter[] = useMemo(() => {
    const result: ActiveFilter[] = [];
    for (const filter of filters) {
      const val = values[filter.key];
      if (val) {
        const option = filter.options.find((o) => o.value === val);
        result.push({
          key: filter.key,
          label: filter.label,
          value: val,
          valueLabel: option?.label ?? val,
        });
      }
    }
    return result;
  }, [filters, values]);

  const activeCount = activeFilters.length;

  const handleSelectChange = useCallback(
    (key: string, value: string) => {
      onChange(key, value === "" ? null : value);
    },
    [onChange],
  );

  const handlePresetToggle = useCallback(
    (key: string, value: string) => {
      const current = values[key];
      onChange(key, current === value ? null : value);
    },
    [values, onChange],
  );

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex items-center gap-2 text-sm font-medium text-gray-700 transition-colors hover:text-gray-900 dark:text-gray-300 dark:hover:text-gray-100"
      >
        <Filter className="h-4 w-4" />
        Filters
        {activeCount > 0 && (
          <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-blue-500 px-1.5 text-xs font-semibold text-white">
            {activeCount}
          </span>
        )}
        <ChevronDown
          className={`h-4 w-4 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
        />
      </button>

      <div
        className={`overflow-hidden transition-all duration-200 ${
          expanded ? "max-h-[500px] opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="flex flex-wrap items-end gap-4 rounded-lg border border-gray-200 bg-gray-50/50 p-4 dark:border-gray-700 dark:bg-gray-800/50">
          {filters.map((filter) =>
            filter.type === "select" ? (
              <div key={filter.key} className="flex flex-col gap-1.5">
                <label
                  htmlFor={`filter-${filter.key}`}
                  className="text-xs font-medium text-gray-500 dark:text-gray-400"
                >
                  {filter.label}
                </label>
                <div className="relative">
                  <select
                    id={`filter-${filter.key}`}
                    value={values[filter.key] ?? ""}
                    onChange={(e) =>
                      handleSelectChange(filter.key, e.target.value)
                    }
                    className="min-w-[140px] appearance-none rounded-lg border border-gray-300 bg-white px-3 py-2 pr-8 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
                  >
                    <option value="">
                      {filter.placeholder ?? `All ${filter.label}`}
                    </option>
                    {filter.options.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                </div>
              </div>
            ) : (
              <div key={filter.key} className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                  {filter.label}
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {filter.options.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => handlePresetToggle(filter.key, opt.value)}
                      className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors duration-150 ${
                        values[filter.key] === opt.value
                          ? "border-blue-500 bg-blue-50 text-blue-700 dark:border-blue-400 dark:bg-blue-900/30 dark:text-blue-300"
                          : "border-gray-300 bg-white text-gray-600 hover:border-gray-400 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300 dark:hover:border-gray-500 dark:hover:bg-gray-700"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            ),
          )}

          {activeCount > 0 && (
            <button
              type="button"
              onClick={onClearAll}
              className="ml-auto self-end rounded-lg px-3 py-2 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
            >
              Clear all
            </button>
          )}
        </div>
      </div>

      {activeCount > 0 && (
        <div className="flex flex-wrap gap-2">
          {activeFilters.map((af) => (
            <span
              key={af.key}
              className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 dark:border-blue-700 dark:bg-blue-900/20 dark:text-blue-300"
            >
              {af.label}: {af.valueLabel}
              <button
                type="button"
                onClick={() => onChange(af.key, null)}
                className="rounded-full p-0.5 transition-colors hover:bg-blue-100 dark:hover:bg-blue-800"
                aria-label={`Remove ${af.label} filter`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
