"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  Shield,
  Server,
  AlertTriangle,
  FileText,
  ArrowRight,
  Loader2,
} from "lucide-react";
import api from "@/lib/api";
import type { Finding, Asset, Control } from "@/types";

type ResultCategory = "findings" | "assets" | "controls";

interface SearchResult {
  id: string;
  category: ResultCategory;
  title: string;
  subtitle: string;
  href: string;
  severity?: string;
  status?: string;
}

function categoryIcon(category: ResultCategory) {
  switch (category) {
    case "findings":
      return <AlertTriangle size={16} className="shrink-0 text-amber-500" />;
    case "assets":
      return <Server size={16} className="shrink-0 text-blue-500" />;
    case "controls":
      return <Shield size={16} className="shrink-0 text-indigo-500" />;
  }
}

function categoryLabel(category: ResultCategory) {
  switch (category) {
    case "findings":
      return "Findings";
    case "assets":
      return "Assets";
    case "controls":
      return "Controls";
  }
}

export default function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Open/close
  const openPalette = useCallback(() => {
    setOpen(true);
    setQuery("");
    setResults([]);
    setActiveIndex(0);
  }, []);

  const closePalette = useCallback(() => {
    setOpen(false);
    setQuery("");
    setResults([]);
  }, []);

  // Cmd+K listener
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        if (open) {
          closePalette();
        } else {
          openPalette();
        }
      }
      if (e.key === "Escape" && open) {
        closePalette();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, openPalette, closePalette]);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Search with debounce
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!query.trim()) {
      setResults([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);

    debounceRef.current = setTimeout(async () => {
      try {
        const [findingsRes, assetsRes, controlsRes] = await Promise.all([
          api
            .get("/findings", { params: { size: 5, search: query } })
            .catch(() => null),
          api
            .get("/assets", { params: { size: 5, search: query } })
            .catch(() => null),
          api
            .get("/controls", { params: { size: 5, search: query } })
            .catch(() => null),
        ]);

        const items: SearchResult[] = [];

        const findings = (findingsRes?.data?.data as Finding[] | null) ?? [];
        for (const f of findings) {
          items.push({
            id: f.id,
            category: "findings",
            title: f.title,
            subtitle: `${f.severity.toUpperCase()} · ${f.status}`,
            href: `/findings/${f.id}`,
            severity: f.severity,
            status: f.status,
          });
        }

        const assets = (assetsRes?.data?.data as Asset[] | null) ?? [];
        for (const a of assets) {
          items.push({
            id: a.id,
            category: "assets",
            title: a.name,
            subtitle: `${a.resource_type} · ${a.region ?? "global"}`,
            href: `/assets/${a.id}`,
          });
        }

        const controls = (controlsRes?.data?.data as Control[] | null) ?? [];
        for (const c of controls) {
          items.push({
            id: c.id,
            category: "controls",
            title: `${c.code} — ${c.name}`,
            subtitle: `${c.framework} · ${c.severity}`,
            href: `/compliance?control_id=${c.id}`,
          });
        }

        setResults(items);
        setActiveIndex(0);
      } catch {
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 250);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  // Keyboard navigation
  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((prev) => Math.min(prev + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter" && results[activeIndex]) {
      e.preventDefault();
      router.push(results[activeIndex].href);
      closePalette();
    }
  }

  // Scroll active item into view
  useEffect(() => {
    if (!listRef.current) return;
    const active = listRef.current.querySelector(
      `[data-index="${activeIndex}"]`,
    );
    active?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  // Group results by category
  const grouped = results.reduce(
    (acc, r) => {
      if (!acc[r.category]) acc[r.category] = [];
      acc[r.category].push(r);
      return acc;
    },
    {} as Record<ResultCategory, SearchResult[]>,
  );

  if (!open) return null;

  let flatIndex = -1;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
        onClick={closePalette}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
        <div
          className="w-full max-w-xl overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-800"
          role="dialog"
          aria-label="Search"
        >
          {/* Search input */}
          <div className="flex items-center gap-3 border-b border-gray-200 px-4 dark:border-gray-700">
            <Search size={18} className="shrink-0 text-gray-400" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Search findings, assets, controls..."
              className="h-14 w-full bg-transparent text-sm text-gray-900 placeholder-gray-400 outline-none dark:text-gray-100 dark:placeholder-gray-500"
            />
            {isLoading && (
              <Loader2
                size={16}
                className="shrink-0 animate-spin text-gray-400"
              />
            )}
            <kbd className="hidden shrink-0 rounded-md border border-gray-200 bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-400 sm:inline-block dark:border-gray-600 dark:bg-gray-700 dark:text-gray-500">
              ESC
            </kbd>
          </div>

          {/* Results */}
          <div
            ref={listRef}
            className="max-h-80 overflow-y-auto overscroll-contain p-2"
          >
            {!query.trim() && (
              <div className="flex flex-col items-center justify-center py-10 text-center">
                <FileText
                  size={32}
                  className="mb-2 text-gray-300 dark:text-gray-600"
                />
                <p className="text-sm text-gray-400 dark:text-gray-500">
                  Type to search across findings, assets, and controls
                </p>
              </div>
            )}

            {query.trim() && !isLoading && results.length === 0 && (
              <div className="flex flex-col items-center justify-center py-10 text-center">
                <Search
                  size={32}
                  className="mb-2 text-gray-300 dark:text-gray-600"
                />
                <p className="text-sm text-gray-400 dark:text-gray-500">
                  No results for &ldquo;{query}&rdquo;
                </p>
              </div>
            )}

            {(["findings", "assets", "controls"] as ResultCategory[]).map(
              (cat) => {
                const items = grouped[cat];
                if (!items?.length) return null;
                return (
                  <div key={cat} className="mb-1">
                    <div className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                      {categoryLabel(cat)}
                    </div>
                    {items.map((item) => {
                      flatIndex++;
                      const idx = flatIndex;
                      const isActive = idx === activeIndex;
                      return (
                        <button
                          key={item.id}
                          data-index={idx}
                          onClick={() => {
                            router.push(item.href);
                            closePalette();
                          }}
                          onMouseEnter={() => setActiveIndex(idx)}
                          className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                            isActive
                              ? "bg-blue-50 text-blue-900 dark:bg-blue-900/30 dark:text-blue-100"
                              : "text-gray-700 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700/50"
                          }`}
                        >
                          {categoryIcon(item.category)}
                          <div className="min-w-0 flex-1">
                            <div className="truncate font-medium">
                              {item.title}
                            </div>
                            <div className="truncate text-xs text-gray-400 dark:text-gray-500">
                              {item.subtitle}
                            </div>
                          </div>
                          <ArrowRight
                            size={14}
                            className={`shrink-0 ${
                              isActive ? "text-blue-400" : "text-transparent"
                            }`}
                          />
                        </button>
                      );
                    })}
                  </div>
                );
              },
            )}
          </div>

          {/* Footer */}
          {results.length > 0 && (
            <div className="flex items-center justify-between border-t border-gray-200 px-4 py-2 text-[11px] text-gray-400 dark:border-gray-700 dark:text-gray-500">
              <span>{results.length} results</span>
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1">
                  <kbd className="rounded border border-gray-200 bg-gray-100 px-1 py-0.5 font-mono text-[10px] dark:border-gray-600 dark:bg-gray-700">
                    ↑↓
                  </kbd>
                  navigate
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="rounded border border-gray-200 bg-gray-100 px-1 py-0.5 font-mono text-[10px] dark:border-gray-600 dark:bg-gray-700">
                    ↵
                  </kbd>
                  open
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
